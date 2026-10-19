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
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlglot import exp

from markupsafe import Markup

from nfl_ask.agent import AskResult
from nfl_ask.pricing import haiku_cost
from nfl_ask.web.charts import render_chart
from nfl_ask.web.limits import RateLimiter
from nfl_ask.web.present import (coverage, data_table, key_stats, mart_docs, mart_name, notes_for,
                                 sources_for, subject_rows)

HERE = Path(__file__).parent
MAX_QUESTION_CHARS = 500  # longer questions cost more tokens and are rarely clearer
PACIFIC = ZoneInfo("America/Los_Angeles")  # the refresh schedule's timezone

# A spread of topics, so the examples show range rather than suggest the only questions that work.
EXAMPLE_QUESTIONS = [
    "Is Dak Prescott worth his contract?",
    "Which offense was the most efficient in 2024?",
    "Which team covered the spread most often in 2024?",
    "Who's the most aggressive team on fourth down?",
    "How has Josh Allen played year over year?",
]
LOADING_LINES = ["Reviewing the tape…", "Checking the cap sheet…", "Running it back…",
                 "Asking the film room…", "Counting dropbacks…"]

log = logging.getLogger(__name__)
# uvicorn's own logger, so the line shows in the server output. Tokens and cost only: never the
# question, the answer or anything else about the visitor.
usage_log = logging.getLogger("uvicorn.error")


def tables_read(sql: str) -> list[str]:
    """The marts a query reads, for "how I got this" (CTEs left out; unparseable SQL gives [])."""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.ParseError:
        return []
    ctes = {cte.alias_or_name for cte in tree.find_all(exp.CTE)}
    return sorted({t.name for t in tree.find_all(exp.Table) if t.name and t.name not in ctes})


def answer_view(result: AskResult, dates: Mapping[str, datetime]) -> dict:
    """What the answer fragment shows: the subject's key numbers, the chart, the data tables, and
    where each number came from."""
    steps, tables, marts, stats = [], [], {}, []
    chart_number = result.chart["query"] if result.chart else None
    subjects = {}  # query number -> the rows the headline is about
    for number, ((sql, params), rows) in enumerate(zip(result.queries, result.results), start=1):
        read = tables_read(sql)
        steps.append({"number": number, "sql": sql, "params": params,
                      "sources": [(table, dates.get(table)) for table in read]})
        if rows is None:
            continue  # a rejected or failed query: shown in the SQL list, no data
        charted = number == chart_number
        subjects[number] = subject_rows(rows, result.headline or result.text)
        table = data_table(rows, first=[result.chart["x"], result.chart["y"]] if charted else (),
                           subject=subjects[number])
        # Key numbers from the charted query (else the first), only when one row is the subject.
        if not stats and len(subjects[number]) == 1 and (charted or chart_number is None):
            stats = key_stats(rows, subjects[number][0], table["columns"])
        table["number"], table["from"] = number, [mart_name(t) for t in read]
        tables.append(table)
        for t in read:
            mart = marts.setdefault(t, {"name": mart_name(t), "table": t, "published": dates.get(t),
                                        "description": mart_docs().get(t, {}).get("description", ""),
                                        "notes": []})
            for label, note in notes_for(t, table["columns"]):
                if (label, note) not in mart["notes"]:
                    mart["notes"].append((label, note))

    chart_svg = None
    if result.chart:
        svg = render_chart(result.chart, result.results[chart_number - 1], subjects.get(chart_number, ()))
        chart_svg = Markup(svg) if svg else None  # built from escaped parts in charts.py
    # The charted data first: it's the table the chart is drawn from.
    tables.sort(key=lambda t: t["number"] != chart_number)
    return {"steps": steps, "tables": tables, "marts": list(marts.values()), "chart": chart_svg,
            "sources": sources_for(marts), "stats": stats, "coverage": coverage()}


def serving_url(env: str, environ: Mapping[str, str]) -> str:
    """The serving database for NFL_ENV: the pooled URL when set (the website makes many short
    connections, which is what Prisma's pooler is for), else the direct one Dagster also uses."""
    name = f"SERVING_DB_URL_{env.upper()}"
    return environ.get(f"{name}_POOLED") or environ[name]


def day(moment: datetime) -> str:
    local = moment.astimezone(PACIFIC)
    return f"{local:%b} {local.day}, {local.year}"


def create_app(
    *,
    ask: Callable[[str], AskResult],
    freshness: Callable[[], Mapping[str, datetime]],
    limiter: RateLimiter | None = None,
    trust_proxy: bool = False,
) -> FastAPI:
    limiter = limiter or RateLimiter()

    def visitor(request: Request) -> str:
        """Who's asking, for the rate limit only. X-Forwarded-For only behind a trusted proxy
        (the host's): otherwise anyone could set it and dodge the limit. Its first entry is the
        visitor; the rest are the proxies it passed through."""
        forwarded = request.headers.get("x-forwarded-for", "")
        if trust_proxy and forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

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

    @app.get("/health", response_class=PlainTextResponse)
    def health():
        return "ok"  # for the host's health check: no database, no model

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
        def fragment(context, status=200, headers=None):
            response = templates.TemplateResponse(request, "_answer.html", context, status_code=status)
            response.headers["Cache-Control"] = "no-store"
            response.headers.update(headers or {})
            return response

        question = question.strip()
        if not question:
            return fragment({"notice": "Type a question first."})
        if len(question) > MAX_QUESTION_CHARS:
            return fragment({"notice": f"Please keep questions under {MAX_QUESTION_CHARS} characters."})
        decision = limiter.allow(visitor(request))
        if not decision.ok:
            wait = decision.retry_after
            when = f"{wait} seconds" if wait < 120 else f"{round(wait / 60)} minutes"
            # A real 429 with Retry-After (for browsers, monitoring and scripts); the page shows
            # the message and counts down from data-retry-after (app.js).
            return fragment({"notice": f"That's a lot of questions in a short time. Please try again in {when}.",
                             "retry_after": wait}, status=429, headers={"Retry-After": str(wait)})
        try:
            result = ask(question)
        except Exception as e:
            # Never the message or a traceback: either could carry the question.
            log.warning("answering failed: %s", type(e).__name__)
            return fragment({"notice": "Something went wrong answering that. Please try again."})
        u = result.usage
        usage_log.info("answer status=%s queries=%d tokens in=%d out=%d cache_read=%d cache_write=%d cost=$%.5f",
                       result.status, len(result.queries), u.get("input_tokens", 0), u.get("output_tokens", 0),
                       u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0), haiku_cost(u))

        return fragment({"question": question, "result": result, "asked_on": day(datetime.now(PACIFIC)),
                         **answer_view(result, published())})

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
    url = serving_url(env, os.environ)
    limiter = RateLimiter(
        per_minute=int(os.getenv("ASK_LIMIT_PER_MINUTE", "5")),
        per_hour=int(os.getenv("ASK_LIMIT_PER_HOUR", "30")),
        per_day_total=int(os.getenv("ASK_LIMIT_PER_DAY_TOTAL", "500")),
    )
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

    return create_app(ask=ask, freshness=freshness, limiter=limiter,
                      trust_proxy=os.getenv("ASK_TRUST_PROXY") == "1")
