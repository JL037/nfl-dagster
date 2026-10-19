"""Turn eval runs (evals/results/*.json) into one Markdown report.

    python evals/report.py evals/results/A.json evals/results/B.json ... > report.md

Runs are listed oldest first; full answers and SQL are shown for the last run.
"""

import json
import sys
from pathlib import Path

NAMES = {"haiku": "Claude Haiku 5.5", "glm": "GLM-5.3 Flash"}


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def run_summary(rows: list[dict]) -> list:
    in_scope = [r for r in rows if r["expect"] == "answer"]
    out_scope = [r for r in rows if r["expect"] == "no_data"]
    cost = sum(r["cost"] for r in rows)
    return [f"{sum(r['passed'] for r in in_scope)}/{len(in_scope)}",
            f"{sum(r['passed'] for r in out_scope)}/{len(out_scope)}",
            f"{sum(r['passed'] for r in rows)}/{len(rows)}",
            f"${cost / len(rows):.5f}", f"${cost:.4f}",
            f"{sum(r['seconds'] for r in rows) / len(rows):.1f} s"]


def main(paths: list[str]) -> str:
    runs = [(Path(p).stem, json.loads(Path(p).read_text())) for p in sorted(paths)]
    models = list(runs[-1][1])
    out = []

    out.append("## Results by run\n")
    rows = []
    for stamp, run in runs:
        for m in models:
            rows.append([stamp, NAMES[m], *run_summary(run[m]["rows"])])
    out.append(table(["Run", "Model", "In scope (15)", "Out of scope (10)", "Overall",
                      "Cost / question", "Run cost", "Avg time"], rows))

    out.append("\n## All runs combined\n")
    rows = []
    for m in models:
        every = [r for _, run in runs for r in run[m]["rows"]]
        rows.append([NAMES[m], *run_summary(every)])
    out.append(table(["Model", "In scope", "Out of scope", "Overall", "Cost / question",
                      "Total cost", "Avg time"], rows))

    out.append("\n## Question by question (passes out of runs)\n")
    ids = [r["id"] for r in runs[-1][1][models[0]]["rows"]]
    expect = {r["id"]: r["expect"] for r in runs[-1][1][models[0]]["rows"]}
    rows = []
    for qid in ids:
        cells = []
        for m in models:
            passes = sum(next(r for r in run[m]["rows"] if r["id"] == qid)["passed"] for _, run in runs)
            cells.append(f"{passes}/{len(runs)}" + ("" if passes == len(runs) else " ⚠️"))
        rows.append([qid, "answer" if expect[qid] == "answer" else "no data", *cells])
    out.append(table(["Question", "Expected", *[NAMES[m] for m in models]], rows))

    out.append("\n## Every failure, with its recorded reason\n")
    out.append("(Reasons were recorded from the second run on.)\n")
    rows = []
    for stamp, run in runs:
        for m in models:
            for r in run[m]["rows"]:
                if not r["passed"]:
                    rows.append([stamp, NAMES[m], r["id"], r["status"], ", ".join(r["failures"]),
                                 r.get("reason", "") or "(not recorded)", len(r["queries"])])
    out.append(table(["Run", "Model", "Question", "Status", "Failed check", "Reason", "Queries"], rows))

    out.append("\n## Who served GLM's requests\n")
    out.append("Every request asked OpenRouter for zero-data-retention, no-data-collection providers only.\n")
    for stamp, run in runs:
        providers = run.get("glm", {}).get("providers") or []
        out.append(f"- {stamp}: {', '.join(providers) if providers else '(not recorded)'}")

    stamp, last = runs[-1]
    out.append(f"\n## Full answers and SQL, run {stamp}\n")
    questions = {r["id"]: r for r in last[models[0]]["rows"]}
    for qid in ids:
        out.append(f"### {qid} (expected: {'answer' if expect[qid] == 'answer' else 'no data'})\n")
        for m in models:
            r = next(r for r in last[m]["rows"] if r["id"] == qid)
            verdict = "PASS" if r["passed"] else f"FAIL ({', '.join(r['failures'])})"
            out.append(f"**{NAMES[m]}**: {verdict}, ${r['cost']:.5f}, {r['seconds']} s"
                       + (f", reason: {r['reason']}" if r.get("reason") else ""))
            out.append(f"\n> {r['answer']}\n")
            for sql, params in r["queries"]:
                shown = " ".join(sql.split())
                out.append(f"- `{shown}`" + (f" params `{params}`" if params else ""))
            out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    print(main(sys.argv[1:]))
