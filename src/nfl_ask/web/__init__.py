"""The Ask page: one question box over the served marts (FastAPI + HTMX).

What it promises visitors, enforced here and pinned in tests/test_ask_web.py:

- The question travels only in the request body (POST), never the URL, so it never reaches
  access logs; GET /answer is refused.
- Nothing about the question is logged or stored, even when answering fails (only the error's
  type is logged).
- Every answer shows the SQL behind it, its bound values, which marts it read and when they
  were published.
- Nothing the model writes can run in the browser: templates autoescape everything.
- HTMX is served from this site, not a CDN, so no third party sees who visits.

create_app() takes the answer and freshness functions, so tests run without a model or a
database; create_production_app() wires the real ones (run it with `uvicorn --factory`).
"""

import logging
import os
import random
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import sqlglot
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlglot import exp

from nfl_ask.agent import AskResult

HERE = Path(__file__).parent
MAX_QUESTION_CHARS = 500  # longer questions cost more tokens and are rarely clearer
PACIFIC = ZoneInfo("America/Los_Angeles")  # the refresh schedule's timezone

EXAMPLE_QUESTIONS = [
    "Who was the best value QB in 2025?",
    "Is Dak Prescott worth his contract?",
    "Which team covered the spread most often in 2024?",
    "Which team went for it on fourth down the most in 2025?",
]
LOADING_LINES = ["Reviewing the tape…", "Checking the cap sheet…", "Running it back…",
                 "Asking the film room…", "Counting dropbacks…"]

log = logging.getLogger(__name__)


def tables_read(sql: str) -> list[str]:
    """The marts a query reads, for "how I got this" (CTEs left out; unparseable SQL gives [])."""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError:
        return []
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return sorted({t.name for t in tree.find_all(exp.Table) if t.name and t.name not in ctes})


def day(moment: datetime) -> str:
    local = moment.astimezone(PACIFIC)
    return f"{local:%b} {local.day}, {local.year}"


def create_app(
    *,
    ask: Callable[[str], AskResult],
    freshness: Callable[[], Mapping[str, datetime]],
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")
    templates.env.filters["day"] = day

    def published() -> Mapping[str, datetime]:
        try:
            return freshness()
        except Exception as e:  # the page still works; it just can't say how fresh the data is
            log.warning("freshness lookup failed: %s", type(e).__name__)
            return {}

    @app.get("/", response_class=HTMLResponse)
    def page(request: Request):
        dates = published()
        return templates.TemplateResponse(request, "index.html", {
            "examples": EXAMPLE_QUESTIONS,
            "loading": random.choice(LOADING_LINES),
            # The oldest publication: every table is at least this fresh.
            "as_of": min(dates.values()) if dates else None,
            "max_chars": MAX_QUESTION_CHARS,
        })

    @app.post("/answer", response_class=HTMLResponse)
    def answer(request: Request, question: str = Form("")):
        def fragment(context):
            response = templates.TemplateResponse(request, "_answer.html", context)
            response.headers["Cache-Control"] = "no-store"
            return response

        question = question.strip()
        if not question:
            return fragment({"notice": "Type a question first."})
        if len(question) > MAX_QUESTION_CHARS:
            return fragment({"notice": f"Please keep questions under {MAX_QUESTION_CHARS} characters."})
        try:
            result = ask(question)
        except Exception as e:
            # Never the message or a traceback: either could carry the question.
            log.warning("answering failed: %s", type(e).__name__)
            return fragment({"notice": "Something went wrong answering that. Please try again."})

        dates = published()
        steps = [
            {"sql": sql, "params": params,
             "sources": [(table, dates.get(table)) for table in tables_read(sql)]}
            for sql, params in result.queries
        ]
        return fragment({"question": question, "result": result, "steps": steps})

    return app


def create_production_app() -> FastAPI:
    """The real app: Claude plus the serving database for NFL_ENV (dev unless set to prod).

        bws run -- uvicorn nfl_ask.web:create_production_app --factory --reload
    """
    import anthropic
    import psycopg

    from nfl_ask.agent import answer_question
    from nfl_ask.catalog import build_catalog
    from nfl_ask.query import run_query

    env = os.getenv("NFL_ENV", "dev")
    url = os.environ[f"SERVING_DB_URL_{env.upper()}"]
    client = anthropic.Anthropic()

    def connect():
        # prepare_threshold=None: no server-side prepared statements, which a pooler (the
        # website's pooled URL) can't keep track of across connections.
        return psycopg.connect(url, autocommit=True, prepare_threshold=None)

    with connect() as conn:
        catalog = build_catalog(conn)  # the served tables and their definitions, read once

    def ask(question: str) -> AskResult:
        with connect() as conn:
            return answer_question(question, client=client, catalog=catalog,
                                   query_fn=lambda sql, params: run_query(conn, sql, params))

    def freshness() -> dict[str, datetime]:
        with connect() as conn:
            return dict(conn.execute("select table_name, published_at from marts._publications").fetchall())

    return create_app(ask=ask, freshness=freshness)
