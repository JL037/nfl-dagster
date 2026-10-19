"""Ask one question from the command line, against the dev serving database (or prod with
NFL_ENV=prod). Prints the answer, the SQL behind it, and what it cost. Stores nothing.

    python scripts/ask.py "Which quarterback was the best value in 2025?"
"""

import os
import sys

import anthropic
import psycopg
from dotenv import load_dotenv

from nfl_ask.agent import answer_question
from nfl_ask.catalog import build_catalog
from nfl_ask.pricing import haiku_cost
from nfl_ask.query import run_query

def main(question: str) -> None:
    load_dotenv()
    env = os.getenv("NFL_ENV", "dev")
    with psycopg.connect(os.environ[f"SERVING_DB_URL_{env.upper()}"], autocommit=True) as conn:
        result = answer_question(
            question,
            client=anthropic.Anthropic(),
            query_fn=lambda sql, params: run_query(conn, sql, params),
            catalog=build_catalog(conn),
        )
    print(f"[{result.status}] {result.text}")
    for sql, params in result.queries:
        print(f"  sql: {sql}" + (f"  params: {params}" if params else ""))
    cost = haiku_cost(result.usage)
    print(f"  tokens: {result.usage}  cost: ${cost:.5f}")


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]))
