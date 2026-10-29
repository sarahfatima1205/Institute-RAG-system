"""Evaluate the helpdesk on eval/prompts.json.

  python eval/evaluate.py --mode multi --model ollama_chat/qwen3:8b --runs 3
  python eval/evaluate.py --mode single --model ollama_chat/llama3.1:8b --runs 3
  python eval/evaluate.py --set core --runs 1 --tag tune1        # quick tuning run, results/<mode>_<model>_tune1.*
  python eval/evaluate.py --ids P01 S02 --runs 1 --tag dbg        # only some questions
  python eval/evaluate.py --resume ...                            # continue an interrupted run (same flags)
  python eval/evaluate.py --compare results/a.jsonl results/b.jsonl     # what changed between models/runs

Prompt items: q (or turns = several user messages in ONE session, judged on the last answer), expect (regex groups,
all must match), reject (regexes that must not match, e.g. a withdrawn rule), sources (files an answer may cite),
should_refuse, route (agent name(s) that must take part, multi mode only; default by category), set ("core"/"extra").

Metrics
  accuracy     in-scope: every expected regex group matches, no "reject" regex matches AND the agent did not refuse
  groundedness in-scope: answer cites "(Source: ...)" a file that (a) is an expected source and
               (b) was actually returned by a tool in that run (so citations can't be invented)
  refusal      out-of-scope / unresolvable: answer says "I don't know" AND the question was logged (by the agent, or
               by the runtime guardrail when the agent forgot: auto_logged; model_logged = the agent did it itself)
               (strict_start additionally records whether the reply STARTS with "I don't know" as the prompts demand)
  route        multi mode: the expected specialist agent(s) took part
  stability    questions whose pass/fail or answer text differ across repeated runs
"""
import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import agents  # noqa: E402
import config  # noqa: E402
from runtime import Helpdesk  # noqa: E402

APOS = "['’]"  # models often emit a typographic apostrophe
REFUSE = re.compile(rf"i don{APOS}?t know|do not know|cannot (find|answer)|can{APOS}?t (find|answer)", re.I)
REFUSE_START = re.compile(rf"\W*i don{APOS}?t know", re.I)
CITE = re.compile(r"\(Source:\s*([^)]+)\)", re.I)
DEFAULT_ROUTE = {"policy": "policy_agent", "schedule": "schedule_agent", "email": "email_agent"}


def judge(item: dict, r: dict, multi: bool = False) -> dict:
    ans = r["answer"]
    refused = bool(REFUSE.search(ans))
    model_logged = any(c["tool"] == "log_unanswered_question" for c in r["tool_calls"])
    logged = model_logged or bool(r.get("auto_logged"))
    need = item.get("route") or DEFAULT_ROUTE.get(item["category"])
    need = [need] if isinstance(need, str) else (need or [])
    route_ok = all(a in r["agents"] for a in need) if (multi and need and not item.get("should_refuse")) else None
    if item.get("should_refuse"):
        ok = refused and logged
        return {"accuracy": ok, "grounded": None, "refusal_ok": ok, "refused": refused, "logged": logged,
                "model_logged": model_logged, "strict_start": bool(REFUSE_START.match(ans)), "route_ok": route_ok}
    correct = (
        (not refused)
        and all(any(re.search(p, ans, re.I) for p in grp) for grp in item["expect"])
        and not any(re.search(p, ans, re.I) for p in item.get("reject", []))
    )
    if item.get("no_cite"):
        grounded = None
    else:
        returned = json.dumps(r["tool_results"], default=str).lower()
        cited = [c.lower() for c in CITE.findall(ans)]
        grounded = bool(cited) and any(
            s.lower() in c and s.lower() in returned for c in cited for s in item["sources"]
        )
    return {"accuracy": correct, "grounded": grounded, "refusal_ok": None, "refused": refused, "logged": logged,
            "model_logged": model_logged, "strict_start": None, "route_ok": route_ok}


async def ask_item(hd: Helpdesk, item: dict) -> dict:
    """One question, or a multi-turn conversation in a single session (tool traces are merged)."""
    turns = item.get("turns") or [item["q"]]
    merged = {"answer": "", "tool_calls": [], "tool_results": [], "agents": [], "auto_logged": False}
    sid = None
    for t in turns:
        r = await hd.ask(t, sid)
        sid = r["session"]
        merged["answer"] = r["answer"]
        merged["tool_calls"] += r["tool_calls"]
        merged["tool_results"] += r["tool_results"]
        merged["agents"] += [a for a in r["agents"] if a not in merged["agents"]]
        merged["auto_logged"] = merged["auto_logged"] or r.get("auto_logged", False)
    return merged


async def run(args):
    multi = args.mode == "multi"
    build = agents.build_multi_agent if multi else agents.build_single_agent
    hd = Helpdesk(build(args.model))
    items = json.loads(Path(args.prompts).read_text(encoding="utf-8"))
    if args.set != "all":
        items = [i for i in items if i.get("set", "core") == args.set]
    if args.ids:
        items = [i for i in items if i["id"] in args.ids]
    tag = f"{args.mode}_{args.model.split('/')[-1].replace(':', '-')}" + (f"_{args.tag}" if args.tag else "")
    config.RESULTS_DIR.mkdir(exist_ok=True)
    out = config.RESULTS_DIR / f"{tag}.jsonl"
    # eval questions must not pollute the real queue of unanswered questions a human reviews
    config.UNANSWERED_LOG = config.RESULTS_DIR / f"{tag}_unanswered.csv"
    rows = []
    if args.resume and out.exists():
        rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        out.write_text("", encoding="utf-8")
        config.UNANSWERED_LOG.unlink(missing_ok=True)
    done = {(r["id"], r["run"]) for r in rows}
    total = len(items) * args.runs
    t_start = time.time()
    for k in range(args.runs):  # run-major order: a partial run still gives one full pass over all questions
        for it in items:
            if (it["id"], k) in done:
                continue
            t0 = time.time()
            try:
                r = await ask_item(hd, it)
            except Exception as e:  # keep going on model/tool errors
                r = {"answer": f"ERROR: {e}", "tool_calls": [], "tool_results": [], "agents": []}
            secs = round(time.time() - t0, 1)
            j = judge(it, r, multi)
            row = {"id": it["id"], "category": it["category"], "run": k, "secs": secs, "answer": r["answer"],
                   "agents": r["agents"], "tools": [c["tool"] for c in r["tool_calls"]],
                   "auto_logged": r.get("auto_logged", False), **j}
            rows.append(row)
            with open(out, "a", encoding="utf-8") as f:  # append immediately: a crash loses at most one answer
                f.write(json.dumps(row) + "\n")
            print(f"[{len(rows)}/{total} {secs:>5.0f}s, elapsed {(time.time() - t_start) / 60:.0f} min] "
                  f"{it['id']} run{k} acc={j['accuracy']} grounded={j['grounded']} route={j['route_ok']} "
                  f"agents={'>'.join(r['agents'])}", flush=True)
    summarize(rows, tag)


def pct(xs):
    xs = [x for x in xs if x is not None]
    return f"{sum(xs) / len(xs):.0%}" if xs else "-"


def summarize(rows, tag):
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    lines = [f"# Results: {tag}", "",
             "| category | n | accuracy | groundedness | correct refusal | route | avg s/answer |", "|---|---|---|---|---|---|---|"]
    for cat, rs in list(by_cat.items()) + [("ALL", rows)]:
        lines.append(f"| {cat} | {len(rs)} | {pct([r['accuracy'] for r in rs])} | {pct([r['grounded'] for r in rs])} | "
                     f"{pct([r['refusal_ok'] for r in rs])} | {pct([r.get('route_ok') for r in rs])} | "
                     f"{sum(r.get('secs', 0) for r in rs) / len(rs):.0f} |")
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["id"]].append(r)
    lines += ["", "## Per question (pass pattern across runs, mean seconds, agents of last run)", "",
              "| id | pass pattern | text identical across runs | mean s | agents |", "|---|---|---|---|---|"]
    for q, rs in by_q.items():
        same = len({x["answer"] for x in rs}) == 1
        lines.append(f"| {q} | {''.join(str(int(x['accuracy'])) for x in rs)} | {'yes' if same else 'NO'} | "
                     f"{sum(x.get('secs', 0) for x in rs) / len(rs):.0f} | {' > '.join(rs[-1]['agents'])} |")
    unstable = [q for q, rs in by_q.items()
                if len({x["accuracy"] for x in rs}) > 1 or len({x["answer"] for x in rs}) > 1]
    auto = [f"{r['id']} run{r['run']}" for r in rows if r.get("auto_logged")]
    lines += ["", f"Refusals the agent did not log itself (logged by the runtime guardrail): {len(auto)}"
              + (f" ({', '.join(auto)})" if auto else "")]
    lines += ["", "## Questions whose answers changed across runs", ""]
    lines += [f"- {q}: pass pattern {[int(x['accuracy']) for x in by_q[q]]}" for q in unstable] or ["- none"]
    md = "\n".join(lines)
    (config.RESULTS_DIR / f"{tag}_summary.md").write_text(md, encoding="utf-8")
    print("\n" + md)


def compare(a, b):
    load = lambda p: {(r["id"], r["run"]): r for r in map(json.loads, Path(p).read_text(encoding="utf-8").splitlines())}
    A, B = load(a), load(b)
    print("Questions whose correctness differs between the two result files:")
    for key in sorted(set(A) & set(B)):
        if A[key]["accuracy"] != B[key]["accuracy"]:
            print(f"- {key[0]} run{key[1]}: {A[key]['accuracy']} -> {B[key]['accuracy']}")
    common = sorted(set(A) & set(B))
    if common:
        print(f"\nOverall accuracy on the {len(common)} shared (question, run) pairs: "
              f"A={pct([A[k]['accuracy'] for k in common])}  B={pct([B[k]['accuracy'] for k in common])}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["single", "multi"], default="multi")
    ap.add_argument("--model", default=config.CHAT_MODEL)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--set", choices=["core", "extra", "all"], default="all", help="core = the original 30 prompts")
    ap.add_argument("--ids", nargs="+", help="only these prompt ids")
    ap.add_argument("--tag", default="", help="suffix for result files (use one per tuning experiment)")
    ap.add_argument("--resume", action="store_true", help="continue an interrupted run with the same tag")
    ap.add_argument("--prompts", default=str(Path(__file__).parent / "prompts.json"))
    ap.add_argument("--compare", nargs=2)
    a = ap.parse_args()
    compare(*a.compare) if a.compare else asyncio.run(run(a))
