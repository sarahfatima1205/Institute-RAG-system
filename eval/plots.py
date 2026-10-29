"""Report tables + plots from eval result files (works on partial runs too).

  python eval/plots.py results/multi_qwen3-8b.jsonl "Multi-agent, Qwen3-8B" \
                       results/single_llama3.1-8b.jsonl "Single agent, Llama-3.1-8B"

Writes results/plots/*.png and results/report_summary.md. Configurations are compared on the prompts that all of
them answered; accuracy intervals are 95% Wilson score intervals.
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "plots"
CORE = [p for p in json.loads((ROOT / "eval" / "prompts.json").read_text(encoding="utf-8")) if p.get("set", "core") == "core"]
CATS = ["policy", "schedule", "email", "out_of_scope"]
CAT_N = {c: sum(p["category"] == c for p in CORE) for c in CATS}
SERIES = ["#2a78d6", "#eb6834"]  # categorical slots 1-2 (validated for colour-blind separation)
PASS, FAIL = "#0ca30c", "#d03b3b"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "font.size": 10, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "legend.frameon": False, "savefig.dpi": 200, "savefig.bbox": "tight",
})


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(rows, key):
    xs = [r[key] for r in rows if r.get(key) is not None]
    return (sum(xs), len(xs))


def stats(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["category"]].append(r)
    s = {"n": len(rows), "cat": {}, "secs": sum(r["secs"] for r in rows) / len(rows) if rows else 0}
    for c in CATS:
        rs = by.get(c, [])
        k, n = rate(rs, "accuracy")
        s["cat"][c] = {"k": k, "n": n, "ci": wilson(k, n), "secs": sum(r["secs"] for r in rs) / n if n else None}
    for m in ("accuracy", "grounded", "refusal_ok", "route_ok"):
        k, n = rate(rows, m)
        s[m] = (k, n, wilson(k, n))
    return s


def label_bars(ax, bars, texts):
    for b, t in zip(bars, texts):
        ax.annotate(t, (b.get_x() + b.get_width() / 2, b.get_height()), xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8, color=INK2)


def grouped(ax, groups, values, errs, texts, names, ylabel, ylim=None):
    w = 0.36
    for i, name in enumerate(names):
        xs = [g + (i - 0.5) * (w + 0.02) for g in range(len(groups))]
        e = None
        if errs:
            e = [[v - lo for v, (lo, _) in zip(values[i], errs[i])], [hi - v for v, (_, hi) in zip(values[i], errs[i])]]
        bars = ax.bar(xs, values[i], w, color=SERIES[i], label=name, yerr=e, ecolor=INK2,
                      error_kw={"elinewidth": 1, "capsize": 3}, edgecolor="#fcfcfb", linewidth=1)
        label_bars(ax, bars, texts[i])
    ax.set_xticks(range(len(groups)), groups)
    ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=len(names))


def main(pairs):
    OUT.mkdir(parents=True, exist_ok=True)
    runs = [(lbl, [json.loads(x) for x in Path(f).read_text(encoding="utf-8").splitlines() if x.strip()], f)
            for f, lbl in pairs]
    # compare configurations on the same prompts: keep only prompts every configuration has answered
    common = set.intersection(*({r["id"] for r in rows} for _, rows, _ in runs))
    runs = [(lbl, [r for r in rows if r["id"] in common], f) for lbl, rows, f in runs]
    names = [r[0] for r in runs]
    S = [stats(r[1]) for r in runs]
    nice = {"policy": "Policy", "schedule": "Time-table", "email": "E-mail", "out_of_scope": "Out of scope"}

    # 1. accuracy by category
    fig, ax = plt.subplots(figsize=(7, 3.8))
    vals = [[s["cat"][c]["k"] / s["cat"][c]["n"] if s["cat"][c]["n"] else 0 for c in CATS] for s in S]
    grouped(ax, [f"{nice[c]}\n(n = {S[0]['cat'][c]['n']})" for c in CATS], vals,
            [[s["cat"][c]["ci"] for c in CATS] for s in S],
            [[f"{s['cat'][c]['k']}/{s['cat'][c]['n']}" if s["cat"][c]["n"] else "" for c in CATS] for s in S],
            names, "Accuracy", (0, 1.15))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Accuracy by question category (bars: 95% Wilson interval)", loc="left", fontsize=11)
    fig.savefig(OUT / "fig1_accuracy_by_category.png")
    plt.close(fig)

    # 2. overall metrics
    mets = [("accuracy", "Accuracy"), ("grounded", "Groundedness\n(valid citation)"), ("refusal_ok", "Correct refusal\n+ logging")]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    vals = [[s[m][0] / s[m][1] if s[m][1] else 0 for m, _ in mets] for s in S]
    grouped(ax, [t for _, t in mets], vals, [[s[m][2] for m, _ in mets] for s in S],
            [[f"{s[m][0]}/{s[m][1]}" for m, _ in mets] for s in S], names, "Share of answers", (0, 1.15))
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title("Overall quality metrics", loc="left", fontsize=11)
    fig.savefig(OUT / "fig2_overall_metrics.png")
    plt.close(fig)

    # 3. latency by category
    fig, ax = plt.subplots(figsize=(7, 3.8))
    vals = [[s["cat"][c]["secs"] or 0 for c in CATS] for s in S]
    grouped(ax, [nice[c] for c in CATS], vals, None,
            [[f"{v:.0f} s" if v else "" for v in row] for row in vals], names, "Mean seconds per answer")
    ax.set_title("Response time by category", loc="left", fontsize=11)
    fig.savefig(OUT / "fig3_latency_by_category.png")
    plt.close(fig)

    # 4. per-question pass/fail grid
    ids = [p["id"] for p in CORE if p["id"] in common]
    fig, ax = plt.subplots(figsize=(max(5, 0.32 * len(ids) + 2.5), 1.0 + 0.45 * len(runs)))
    ax.grid(False)
    for i, (_, rows, _) in enumerate(runs):
        res = {r["id"]: r["accuracy"] for r in rows if r["run"] == 0}
        for j, q in enumerate(ids):
            v = res[q]
            ax.add_patch(plt.Rectangle((j + 0.05, i + 0.08), 0.9, 0.84, color=PASS if v else FAIL))
            ax.text(j + 0.5, i + 0.5, "✓" if v else "✗", ha="center", va="center", color="white", fontsize=9)
    ax.set_xlim(0, len(ids))
    ax.set_ylim(0, len(runs))
    ax.invert_yaxis()
    ax.set_xticks([j + 0.5 for j in range(len(ids))], ids, rotation=90, fontsize=7)
    ax.set_yticks([i + 0.5 for i in range(len(runs))], names, fontsize=8)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("Per-prompt result   (✓ pass   ✗ fail)", loc="left", fontsize=11)
    fig.savefig(OUT / "fig4_per_prompt.png")
    plt.close(fig)

    # summary markdown
    L = ["# Evaluation results", "", f"Prompts answered by every configuration: {len(common)} (core set, run 1).", "",
         "| configuration | answered | accuracy | groundedness | correct refusal | routing | mean s/answer |",
         "|---|---|---|---|---|---|---|"]
    f = lambda t: f"{t[0]}/{t[1]} ({t[0] / t[1]:.0%})" if t[1] else "-"
    for name, s in zip(names, S):
        L.append(f"| {name} | {s['n']} | {f(s['accuracy'])} | {f(s['grounded'])} | {f(s['refusal_ok'])} | "
                 f"{f(s['route_ok'])} | {s['secs']:.0f} |")
    L += ["", "## Accuracy by category", "", "| category | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for c in CATS:
        L.append(f"| {c} | " + " | ".join(
            f"{s['cat'][c]['k']}/{s['cat'][c]['n']} ({s['cat'][c]['k'] / s['cat'][c]['n']:.0%}, CI {s['cat'][c]['ci'][0]:.0%}-{s['cat'][c]['ci'][1]:.0%})"
            if s["cat"][c]["n"] else "-" for s in S) + " |")
    L += ["", "## Failed answers (for error analysis)", ""]
    for name, (_, rows, _) in zip(names, runs):
        bad = [r for r in rows if not r["accuracy"]]
        L.append(f"**{name}**: " + (", ".join(r["id"] for r in bad) if bad else "none"))
        for r in bad:
            L.append(f"- {r['id']} (tools: {', '.join(r['tools']) or 'none'}): {r['answer'][:300].replace(chr(10), ' ')}")
        L.append("")
    L += ["## Figures", "", "- `plots/fig1_accuracy_by_category.png`", "- `plots/fig2_overall_metrics.png`",
          "- `plots/fig3_latency_by_category.png`", "- `plots/fig4_per_prompt.png`"]
    (ROOT / "results" / "report_summary.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    a = sys.argv[1:]
    main(list(zip(a[0::2], a[1::2])))
