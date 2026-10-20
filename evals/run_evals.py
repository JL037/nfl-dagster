"""Run the golden questions (evals/golden.yaml) on each model and score them.

Costs real money, a few cents per full run. Uses the dev serving database (NFL_ENV=prod for
prod). Stores the questions' answers only under evals/results/ (gitignored); these are our own
fixed test questions, not visitors'.

    python evals/run_evals.py                  # Claude Haiku 5.5 and GLM-5.3 Flash
    python evals/run_evals.py --models haiku
    python evals/run_evals.py --models haiku --ids example_prescott,broad_best_qb   # just these
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

import anthropic
import psycopg
import yaml
from dotenv import load_dotenv

from nfl_ask.agent import answer_question
from nfl_ask.catalog import build_catalog
from nfl_ask.openrouter import OpenRouterClient
from nfl_ask.pricing import haiku_cost
from nfl_ask.query import run_query
from nfl_ask.scoring import check

HERE = Path(__file__).parent
MODELS = {
    "haiku": ("claude-haiku-5-5", lambda: anthropic.Anthropic()),
    "glm": ("z-ai/glm-5.3-flash", lambda: OpenRouterClient(model="z-ai/glm-5.3-flash")),
}


def truth(conn, sql: str) -> dict | None:
    # Our own SQL, so no validation (it types text values in), but still read-only.
    result = run_query(conn, sql, [], validate=False)
    return dict(zip(result.columns, result.rows[0])) if result.rows else None


def score(item: dict, status: str, answer: str, row: dict | None) -> list[str]:
    """What failed; empty means the question passed."""
    if item["expect"] == "no_data":
        return [] if status == "no_data" else ["should be no_data"]
    if status != "answered":
        return ["no answer"]
    failures = [c["column"] for c in item.get("checks", [])
                if not check(answer, c["kind"], row[c["column"]], row, c.get("decimals", 0))]
    if item.get("contains_any") and not any(w in answer.lower() for w in item["contains_any"]):
        failures.append("in-progress caveat")
    return failures


def main(model_names: list[str], ids: list[str] | None = None) -> None:
    load_dotenv()
    golden = yaml.safe_load((HERE / "golden.yaml").read_text())
    if ids:
        unknown = set(ids) - {item["id"] for item in golden}
        if unknown:
            raise SystemExit(f"no such question ids: {', '.join(sorted(unknown))}")
        golden = [item for item in golden if item["id"] in ids]
    env = os.getenv("NFL_ENV", "dev")
    runs = {}
    with psycopg.connect(os.environ[f"SERVING_DB_URL_{env.upper()}"], autocommit=True) as conn:
        catalog = build_catalog(conn)
        truths = {item["id"]: truth(conn, item["truth"]) if "truth" in item else None for item in golden}
        for name in model_names:
            model, make_client = MODELS[name]
            client = make_client()
            rows = []
            for item in golden:
                cost_before = getattr(client, "total_cost", 0.0)
                started = time.monotonic()
                result = answer_question(item["question"], client=client, model=model, catalog=catalog,
                                         query_fn=lambda sql, params: run_query(conn, sql, params))
                seconds = time.monotonic() - started
                cost = haiku_cost(result.usage) if name == "haiku" else client.total_cost - cost_before
                failures = score(item, result.status, result.text, truths[item["id"]])
                rows.append({"id": item["id"], "question": item["question"], "expect": item["expect"],
                             "truth": truths[item["id"]], "status": result.status,
                             "reason": result.reason,
                             "passed": not failures, "failures": failures, "answer": result.text,
                             "queries": result.queries, "cost": cost, "seconds": round(seconds, 1)})
                print(f"{name:6} {'PASS' if not failures else 'FAIL'}  {item['id']:28} "
                      f"{result.status:9} ${cost:.5f}  {seconds:4.1f}s  {', '.join(failures)}"
                      + (f"  [{result.reason}]" if failures and result.reason else ""))
            runs[name] = {"model": model, "rows": rows,
                          "providers": sorted(getattr(client, "providers", []))}

    print("\nmodel   in-scope   out-of-scope   overall   cost/question   total cost   avg seconds")
    for name, run in runs.items():
        rows = run["rows"]
        in_scope = [r for r in rows if r["expect"] == "answer"]
        out_scope = [r for r in rows if r["expect"] == "no_data"]
        total = sum(r["cost"] for r in rows)
        print(f"{name:6}  {sum(r['passed'] for r in in_scope):2}/{len(in_scope):<2}       "
              f"{sum(r['passed'] for r in out_scope):2}/{len(out_scope):<2}          "
              f"{sum(r['passed'] for r in rows):2}/{len(rows):<2}     ${total / len(rows):.5f}       "
              f"${total:.4f}      {sum(r['seconds'] for r in rows) / len(rows):.1f}"
              + (f"   served by: {', '.join(run['providers'])}" if run["providers"] else ""))

    out = HERE / "results" / f"{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(runs, indent=2, default=str))
    print(f"\nDetails: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="haiku,glm")
    parser.add_argument("--ids", help="comma-separated question ids to run (default: all)")
    args = parser.parse_args()
    main(args.models.split(","), args.ids.split(",") if args.ids else None)
