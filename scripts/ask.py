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
from nfl_ask.query import run_query

# Claude Haiku 5.5, $ per token (input, output, cache read, cache write).
PRICES = {"input_tokens": 0.10e-6, "output_tokens": 0.50e-6,
          "cache_read_input_tokens": 0.01e-6, "cache_creation_input_tokens": 0.125e-6}


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
    cost = sum(PRICES[k] * v for k, v in result.usage.items())
    print(f"  tokens: {result.usage}  cost: ${cost:.5f}")


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]))
