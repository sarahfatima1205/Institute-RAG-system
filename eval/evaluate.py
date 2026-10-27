"""Evaluate the helpdesk on eval/prompts.json.

  python eval/evaluate.py --mode multi --model ollama_chat/qwen3:8b --runs 3
  python eval/evaluate.py --mode single --model ollama_chat/llama3.1:8b --runs 3
  python eval/evaluate.py --compare results/a.jsonl results/b.jsonl     # what changed between models/runs

Metrics
  accuracy     in-scope: every expected regex group matches AND the agent did not refuse
  groundedness in-scope: answer cites "(Source: ...)" a file that (a) is an expected source and
               (b) was actually returned by a tool in that run (so citations can't be invented)
  refusal      out-of-scope / unresolvable: answer says "I don't know" AND log_unanswered_question was called
  stability    questions whose pass/fail or answer text differ across repeated runs
"""
import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agents  # noqa: E402
import config  # noqa: E402
from runtime import Helpdesk  # noqa: E402

REFUSE = re.compile(r"i don'?t know|do not know|cannot (find|answer)|can'?t (find|answer)", re.I)
CITE = re.compile(r"\(Source:\s*([^)]+)\)", re.I)


def judge(item: dict, r: dict) -> dict:
    ans = r["answer"]
    refused = bool(REFUSE.search(ans))
    logged = any(c["tool"] == "log_unanswered_question" for c in r["tool_calls"])
    if item.get("should_refuse"):
        ok = refused and logged
        return {"accuracy": ok, "grounded": None, "refusal_ok": ok, "refused": refused, "logged": logged}
    correct = (not refused) and all(any(re.search(p, ans, re.I) for p in grp) for grp in item["expect"])
    returned = json.dumps(r["tool_results"], default=str).lower()
    cited = [c.lower() for c in CITE.findall(ans)]
    grounded = bool(cited) and any(
        s.lower() in c and s.lower() in returned for c in cited for s in item["sources"]
    )
    return {"accuracy": correct, "grounded": grounded, "refusal_ok": None, "refused": refused, "logged": logged}


async def run(args):
    build = agents.build_multi_agent if args.mode == "multi" else agents.build_single_agent
    hd = Helpdesk(build(args.model))
    items = json.loads(Path(args.prompts).read_text())
    tag = f"{args.mode}_{args.model.split('/')[-1].replace(':', '-')}"
    out = config.RESULTS_DIR / f"{tag}.jsonl"
    config.RESULTS_DIR.mkdir(exist_ok=True)
    rows = []
    for it in items:
        for k in range(args.runs):
            try:
                r = await hd.ask(it["q"])
            except Exception as e:  # keep going on model/tool errors
                r = {"answer": f"ERROR: {e}", "tool_calls": [], "tool_results": [], "agents": []}
            j = judge(it, r)
            rows.append({"id": it["id"], "category": it["category"], "run": k, "answer": r["answer"],
                         "agents": r["agents"], "tools": [c["tool"] for c in r["tool_calls"]], **j})
            print(f"{it['id']} run{k} acc={j['accuracy']} grounded={j['grounded']} refused={j['refused']}")
    out.write_text("\n".join(json.dumps(x) for x in rows))
    summarize(rows, tag)


def summarize(rows, tag):
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    lines = [f"# Results: {tag}", "", "| category | n | accuracy | groundedness | correct refusal |", "|---|---|---|---|---|"]
    for cat, rs in by_cat.items():
        acc = sum(r["accuracy"] for r in rs) / len(rs)
        g = [r["grounded"] for r in rs if r["grounded"] is not None]
        rf = [r["refusal_ok"] for r in rs if r["refusal_ok"] is not None]
        lines.append(f"| {cat} | {len(rs)} | {acc:.0%} | {sum(g)/len(g):.0%} |" if g else f"| {cat} | {len(rs)} | {acc:.0%} | - |")
        lines[-1] += f" {sum(rf)/len(rf):.0%} |" if rf else " - |"
    by_q = defaultdict(list)
    for r in rows:
        by_q[r["id"]].append(r)
    unstable = [q for q, rs in by_q.items()
                if len({x["accuracy"] for x in rs}) > 1 or len({x["answer"] for x in rs}) > 1]
    lines += ["", "## Questions whose answers changed across runs", ""]
    lines += [f"- {q}: pass pattern {[int(x['accuracy']) for x in by_q[q]]}" for q in unstable] or ["- none"]
    md = "\n".join(lines)
    (config.RESULTS_DIR / f"{tag}_summary.md").write_text(md)
    print("\n" + md)


def compare(a, b):
    load = lambda p: {(r["id"], r["run"]): r for r in map(json.loads, Path(p).read_text().splitlines())}
    A, B = load(a), load(b)
    print("Questions whose correctness differs between the two result files:")
    for key in sorted(set(A) & set(B)):
        if A[key]["accuracy"] != B[key]["accuracy"]:
            print(f"- {key[0]} run{key[1]}: {A[key]['accuracy']} -> {B[key]['accuracy']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["single", "multi"], default="multi")
    ap.add_argument("--model", default=config.CHAT_MODEL)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--prompts", default=str(Path(__file__).parent / "prompts.json"))
    ap.add_argument("--compare", nargs=2)
    a = ap.parse_args()
    compare(*a.compare) if a.compare else asyncio.run(run(a))
