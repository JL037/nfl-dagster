"""Turn eval runs (evals/results/*.json) into one Markdown report.

    python evals/report.py evals/results/*.json > report.md

For every question: the question as asked, the expected answer (from the run, or recomputed
from the serving database for runs that didn't store it), and every model's response in every
run, with pass/fail, response time, cost, queries, and the reason for any "no data".
"""

import json
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
NAMES = {"haiku": "Claude Haiku 5.5", "glm": "GLM-5.3 Flash"}


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(lines)


def pct(passed: int, total: int) -> str:
    return f"{passed}/{total} ({100 * passed / total:.0f}%)"


def run_summary(rows: list[dict]) -> list:
    in_scope = [r for r in rows if r["expect"] == "answer"]
    out_scope = [r for r in rows if r["expect"] == "no_data"]
    cost = sum(r["cost"] for r in rows)
    seconds = sorted(r["seconds"] for r in rows)
    return [pct(sum(r["passed"] for r in in_scope), len(in_scope)),
            pct(sum(r["passed"] for r in out_scope), len(out_scope)),
            pct(sum(r["passed"] for r in rows), len(rows)),
            f"${cost / len(rows):.5f}", f"${cost:.4f}",
            f"{sum(seconds) / len(seconds):.1f} s", f"{seconds[len(seconds) // 2]:.1f} s", f"{seconds[-1]:.1f} s"]


def expected_text(item: dict, truth: dict | None) -> str:
    if item["expect"] == "no_data":
        return 'the no-data reply ("We don\'t have the data to give an accurate answer to that.")'
    if truth is None:
        return "(no truth row)"
    parts = []
    for c in item.get("checks", []):
        value = truth[c["column"]]
        if c["kind"] == "name":
            parts.append(f"names **{value}**")
        elif c["kind"] == "full_name":
            parts.append(f"names **{value}** in full")
        elif c["kind"] == "team":
            parts.append(f"names **{value}** ({truth.get('team_name', '')})")
        elif c["kind"] == "count":
            parts.append(f"states **{int(value)}**")
        elif c["kind"] == "percent":
            parts.append(f"states **{float(value):.{c.get('decimals', 0)}f}%** (at least {c.get('decimals', 0)} decimal)")
        else:
            parts.append(f"states **{float(value):+.3f}** (at least {c.get('decimals', 0)} decimals)")
    if item.get("contains_any"):
        parts.append("says the season is still in progress")
    return "; ".join(parts)


def load_truths(golden: list[dict], runs) -> dict:
    """Expected rows: stored in newer runs; otherwise recomputed from the serving database."""
    truths = {}
    for _, run in runs:
        for model in run.values():
            for r in model["rows"]:
                if "truth" in r:
                    truths[r["id"]] = r["truth"]
    missing = [item for item in golden if "truth" in item and item["id"] not in truths]
    if missing:
        import psycopg
        from dotenv import load_dotenv

        from nfl_ask.query import run_query

        load_dotenv()
        url = os.environ[f"SERVING_DB_URL_{os.getenv('NFL_ENV', 'dev').upper()}"]
        with psycopg.connect(url, autocommit=True) as conn:
            for item in missing:
                result = run_query(conn, item["truth"], [], validate=False)
                truths[item["id"]] = dict(zip(result.columns, result.rows[0])) if result.rows else None
    return truths


def main(paths: list[str]) -> str:
    golden = yaml.safe_load((HERE / "golden.yaml").read_text())
    runs = [(Path(p).stem, json.loads(Path(p).read_text())) for p in sorted(paths)]
    models = list(runs[-1][1])
    truths = load_truths(golden, runs)
    out = []

    out.append("## Results by run\n")
    rows = [[stamp, NAMES[m], *run_summary(run[m]["rows"])] for stamp, run in runs for m in models]
    out.append(table(["Run", "Model", "In scope", "Out of scope", "Overall", "Cost / question",
                      "Run cost", "Avg time", "Median time", "Slowest"], rows))

    out.append("\n## All runs combined\n")
    rows = [[NAMES[m], *run_summary([r for _, run in runs for r in run[m]["rows"]])] for m in models]
    out.append(table(["Model", "In scope", "Out of scope", "Overall", "Cost / question", "Total cost",
                      "Avg time", "Median time", "Slowest"], rows))

    out.append("\n## Question by question\n")
    rows = []
    for item in golden:
        cells = []
        for m in models:
            results = [next(r for r in run[m]["rows"] if r["id"] == item["id"]) for _, run in runs]
            passes = sum(r["passed"] for r in results)
            avg = sum(r["seconds"] for r in results) / len(results)
            cells += [f"{passes}/{len(runs)}" + ("" if passes == len(runs) else " ⚠️"), f"{avg:.1f} s"]
        rows.append([item["question"], "answer" if item["expect"] == "answer" else "no data", *cells])
    header = ["Question", "Expected"]
    for m in models:
        header += [f"{NAMES[m]} passed", f"{NAMES[m]} avg time"]
    out.append(table(header, rows))

    out.append("\n## Every question, every response\n")
    for number, item in enumerate(golden, 1):
        out.append(f"### {number}. {item['question']}\n")
        out.append(f"*`{item['id']}`. Expected: {expected_text(item, truths.get(item['id']))}.*\n")
        for m in models:
            results = [(stamp, next(r for r in run[m]["rows"] if r["id"] == item["id"])) for stamp, run in runs]
            passes = sum(r["passed"] for _, r in results)
            out.append(f"**{NAMES[m]}**: {passes}/{len(results)} runs passed\n")
            for stamp, r in results:
                verdict = "✅ PASS" if r["passed"] else f"❌ FAIL ({', '.join(r['failures'])})"
                facts = [verdict, f"{r['seconds']} s", f"${r['cost']:.5f}", f"{len(r['queries'])} quer{'y' if len(r['queries']) == 1 else 'ies'}"]
                if r.get("reason"):
                    facts.append(f"reason: {r['reason']}")
                out.append(f"- Run `{stamp}`: " + ", ".join(facts))
                out.append(f"  > {r['answer']}")
                for sql, params in r["queries"]:
                    out.append(f"  - `{' '.join(sql.split())}`" + (f" params `{params}`" if params else ""))
            out.append("")

    out.append("## Every failure, with its recorded reason\n")
    out.append("(Reasons were recorded from the second run on.)\n")
    rows = []
    for stamp, run in runs:
        for m in models:
            for r in run[m]["rows"]:
                if not r["passed"]:
                    question = next(i["question"] for i in golden if i["id"] == r["id"])
                    rows.append([stamp, NAMES[m], question, ", ".join(r["failures"]),
                                 r.get("reason", "") or "(not recorded)", len(r["queries"]), f"{r['seconds']} s"])
    out.append(table(["Run", "Model", "Question", "Failed check", "Reason", "Queries", "Time"], rows))

    out.append("\n## Who served GLM's requests\n")
    out.append("Every request asked OpenRouter for zero-data-retention, no-data-collection providers only.\n")
    for stamp, run in runs:
        providers = run.get("glm", {}).get("providers") or []
        out.append(f"- `{stamp}`: {', '.join(providers) if providers else '(not recorded)'}")
    return "\n".join(out)


if __name__ == "__main__":
    print(main(sys.argv[1:]))
