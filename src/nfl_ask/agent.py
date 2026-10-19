"""Answer a visitor's question from the served marts, or say we don't have the data.

A manual tool loop on Claude (Haiku 5.5 by default): the model may call run_query at most
`max_queries` times, then must answer. Three rules are enforced in code, not just asked for:

- No data, no answer: the model has a no_data tool, and running out of queries means no data.
- Every number in an answer must appear in a query result (or the question); otherwise the
  answer is replaced by the standard reply. A number "known" from training isn't our data.
- The model only ever reaches the data through query.run_query()'s gate.

Nothing about the question is logged or stored here (the app stores nothing about its users).
"""

import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from nfl_ask.query import QueryRejected, QueryResult

DEFAULT_MODEL = os.environ.get("ASK_MODEL", "claude-haiku-5-5")
NO_DATA_MESSAGE = "We don't have the data to give an accurate answer to that."

RULES = """\
You answer questions about NFL quarterbacks and teams using only the data described below: \
the tables of the nfl-dagster project, read with the run_query tool.

Rules:
1. No data, no answer. If these tables can't answer the question accurately (a statistic, \
season, league, player or term they don't cover), call no_data straight away. Don't guess, \
don't use what you know about football, and don't keep digging: you have at most 3 queries.
2. Every number in your answer must come from a query result in this conversation. Rounding \
is fine, and a fraction may be shown as a percent (0.026 as 2.6%). Compute every number you state \
in SQL (rates, shares, differences), not in your head, and never quote numbers from the \
definitions below: they are examples written when the tables were built and may be out of date.
3. Write one Postgres SELECT per call, against these tables only (no schema prefix needed). \
Put every text value (names, teams, keys) in params and refer to it as %s; never type text \
into the SQL. Numbers such as seasons may be written directly.
4. Use the definitions below exactly as written (for example "worth it" and cap share).
5. A season with is_season_complete = false is still in progress: say its numbers are estimates.
6. Finish by calling the answer tool: a headline (one sentence under 25 words that answers \
the question directly; details go in the explanation), an explanation (two to four plain sentences: the key numbers, how they compare, and \
any caveat such as a season in progress), and a chart. Always include a chart when the answer \
involves several items or seasons: bar for a ranking or comparison, line for a trend across \
seasons, scatter for two measures against each other (such as cap share against EPA). A chart \
plots one of your query results by its query number and column names and draws exactly those \
rows, so query the rows you want shown (at most 25). Use chart null only for a single number. \
No markdown, no tags.
7. Write player and team names exactly as they appear in the results (J.Love, not a guessed \
first name): the data has initials, and a guessed name may be wrong.

The tables:
"""

TOOLS = [
    {
        "name": "run_query",
        "description": (
            "Run one read-only Postgres SELECT against the tables described in the system "
            "prompt. Text values go in params, referenced as %s in the SQL."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "One SELECT statement."},
                "params": {
                    "type": "array",
                    "description": "Values for each %s in the SQL, in order.",
                    "items": {"anyOf": [{"type": "string"}, {"type": "number"}]},
                },
            },
            "required": ["sql", "params"],
            "additionalProperties": False,
        },
    },
    {
        "name": "answer",
        "description": (
            "Give the final answer: a one-sentence headline, a short explanation, and optionally a "
            "chart of one query result. Every number must come from a query result."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "One sentence that answers the question."},
                "explanation": {"type": "string", "description": "Two to four plain sentences."},
                "chart": {
                    "anyOf": [
                        {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string", "enum": ["bar", "line", "scatter"]},
                                "query": {"type": "integer", "description": "The query number whose rows to plot."},
                                "x": {"type": "string", "description": "Column for the x axis (bar: the category)."},
                                "y": {"type": "string", "description": "Numeric column for the y axis (bar: the value)."},
                                "series": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}],
                                    "description": "Line or scatter only: column naming each series (at most 3), or null.",
                                },
                                "title": {"type": "string", "description": "Short chart title."},
                            },
                            "required": ["kind", "query", "x", "y", "series", "title"],
                            "additionalProperties": False,
                        },
                        {"type": "null"},
                    ]
                },
            },
            "required": ["headline", "explanation", "chart"],
            "additionalProperties": False,
        },
    },
    {
        "name": "no_data",
        "description": (
            "Use when the tables can't answer the question accurately. The visitor is told we "
            "don't have the data."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string", "description": "What is missing."}},
            "required": ["reason"],
            "additionalProperties": False,
        },
    },
]


@dataclass
class AskResult:
    status: str  # "answered" or "no_data"
    text: str
    queries: list[tuple[str, list]] = field(default_factory=list)  # for "how I got this"
    usage: dict[str, int] = field(default_factory=dict)  # tokens, summed over the loop's calls
    reason: str = ""  # why there's no answer, for the evals; visitors only see NO_DATA_MESSAGE
    headline: str = ""
    explanation: str = ""
    chart: dict | None = None  # checked against its result by valid_chart(); None if it didn't fit
    # One per query, in order (None where it was rejected or failed): the rows the page shows.
    results: list[QueryResult | None] = field(default_factory=list)


USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

UNCHECKED = "numbers not in any result: "
NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?")


def unverified_numbers(answer: str, results: Sequence[QueryResult], question: str) -> list[str]:
    """Numbers in `answer` that no query result (or the question) accounts for.

    A number is accounted for if it is in the question, is a small count (0-10, as in "the
    top 3"), or equals a result value at the precision written, either as is or as a percent.
    """
    def numbers(text):
        found = []
        for token in NUMBER.findall(text):
            cleaned = token.replace(",", "").lstrip("+")
            decimals = len(cleaned.split(".")[1]) if "." in cleaned else 0
            found.append((cleaned, float(cleaned), decimals))
        return found

    in_question = {value for _, value, _ in numbers(question)}
    values = [
        float(v) for result in results for row in result.rows for v in row
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ]
    unverified = []
    for cleaned, value, decimals in numbers(answer):
        if value in in_question or (decimals == 0 and 0 <= value <= 10):
            continue
        tolerance = 0.5 * 10 ** -decimals + 1e-9
        # Magnitudes: an answer may say the sign in words ("allowed 0.062" for -0.062).
        if any(abs(abs(v) - abs(value)) <= tolerance or abs(abs(v) * 100 - abs(value)) <= tolerance
               for v in values):
            continue
        unverified.append(cleaned)
    return unverified


def format_result(result: QueryResult, number: int) -> str:
    payload = {"query": number, "columns": result.columns, "rows": result.rows, "truncated": result.truncated}
    return json.dumps(payload, default=str)


CHART_KINDS = ("bar", "line", "scatter")


def valid_chart(chart: dict | None, results: Sequence[QueryResult | None]) -> dict | None:
    """The chart if it fits its data, else None: a bad chart choice costs the chart, not the answer.

    It must name a successful query (numbered from 1) and columns of that result, with numbers
    in y. The page draws the result's own rows, so a chart can't show a number no query returned.
    """
    if not chart or chart.get("kind") not in CHART_KINDS:
        return None
    number = chart.get("query")
    if not isinstance(number, int) or not 1 <= number <= len(results) or results[number - 1] is None:
        return None
    result = results[number - 1]
    columns = [chart.get("x"), chart.get("y")] + ([chart["series"]] if chart.get("series") else [])
    if any(c not in result.columns for c in columns) or not result.rows:
        return None
    y = result.columns.index(chart["y"])
    if not all(isinstance(row[y], (int, float)) and not isinstance(row[y], bool)
               for row in result.rows if row[y] is not None):
        return None
    return chart


TRAILING_TAG = re.compile(r"(\s*</?[a-z_]+>)+\s*$")


def clean(text: str) -> str:
    """Trim a stray closing tag the model sometimes adds ("...2025.</headline>")."""
    return TRAILING_TAG.sub("", text.strip())


PACKED_FIELD = re.compile(r'<parameter name="(\w+)">(.*?)(?=</\1>|<parameter name="|$)', re.S)


def unpack(given: dict) -> dict:
    """Recover fields the model packed into `headline` as pseudo-XML (seen live):
    'Headline.</headline> <parameter name="explanation">...</explanation> <parameter name="chart">{...}'.
    The recovered fields then go through the same checks as any answer."""
    headline = given.get("headline", "")
    if '<parameter name="' not in headline:
        return given
    first, _, rest = headline.partition('<parameter name="')
    found = {name: value.strip() for name, value in PACKED_FIELD.findall('<parameter name="' + rest)}
    chart = given.get("chart")
    if chart is None and "chart" in found:
        try:
            chart = json.loads(found["chart"])
        except ValueError:
            chart = None
    # What was packed wins: the real fields then hold placeholders (seen live: explanation "x").
    return {"headline": first, "explanation": found.get("explanation") or given.get("explanation", ""),
            "chart": chart}


def answer_question(
    question: str,
    *,
    client,
    query_fn: Callable[[str, list], QueryResult],
    catalog: str,
    model: str = DEFAULT_MODEL,
    max_queries: int = 3,
) -> AskResult:
    usage = dict.fromkeys(USAGE_FIELDS, 0)

    def finish(status: str, text: str, reason: str = "", **answer) -> AskResult:
        return AskResult(status=status, text=text, queries=queries, usage=usage, reason=reason,
                         results=numbered, **answer)

    def answered(headline: str, explanation: str = "", chart: dict | None = None) -> AskResult:
        headline, explanation = clean(headline), clean(explanation)
        if len(explanation) < 3:
            explanation = ""  # a placeholder ("x"), not an explanation
        if not headline:
            return finish("no_data", NO_DATA_MESSAGE, "empty answer")
        # No query, no answer; and every number must be backed by a result.
        if not results:
            return finish("no_data", NO_DATA_MESSAGE, "answer without a query")
        checked = " ".join([headline, explanation, (chart or {}).get("title", "")])
        if unverified := unverified_numbers(checked, results, question):
            return finish("no_data", NO_DATA_MESSAGE, UNCHECKED + ", ".join(unverified))
        text = f"{headline} {explanation}".strip()
        return finish("answered", text, headline=headline, explanation=explanation,
                      chart=valid_chart(chart, numbered))
    # Stable rules and catalog first, cached; the question is the only thing that varies.
    system = [{"type": "text", "text": RULES + catalog, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": question}]
    queries: list[tuple[str, list]] = []
    results: list[QueryResult] = []  # the successful ones, for checking numbers
    numbered: list[QueryResult | None] = []  # one per query, as numbered for the model

    # At most max_queries queries, plus one last turn to answer from them, plus one turn to
    # fix an answer whose numbers didn't check out (told which ones, once).
    turns, retried = max_queries + 1, False
    while turns > 0:
        turns -= 1
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            system=system,
            tools=TOOLS,
            output_config={"effort": "low"},
            messages=messages,
        )
        for name in USAGE_FIELDS:
            usage[name] += getattr(response.usage, name, 0) or 0
        if response.stop_reason == "refusal":
            return finish("no_data", NO_DATA_MESSAGE, "refusal")
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        gave_up = [block for block in tool_uses if block.name == "no_data"]
        if gave_up:
            return finish("no_data", NO_DATA_MESSAGE, f"model: {gave_up[0].input.get('reason', '')}")
        final = [block for block in tool_uses if block.name == "answer"]
        if final:
            given = unpack(final[0].input)
            outcome = answered(given.get("headline", ""), given.get("explanation", ""), given.get("chart"))
            unchecked = outcome.reason.removeprefix(UNCHECKED)
            if outcome.reason.startswith(UNCHECKED) and not retried:
                retried, turns = True, turns + 1
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                     "content": (f"These numbers aren't in any query result: {unchecked}. Compute them in "
                                 "SQL with a query, or leave them out, then call answer again."
                                 if block is final[0] else "Not run: answer was called in the same turn.")}
                    for block in tool_uses
                ]})
                continue
            return outcome

        if not tool_uses:
            # A plain-text reply is taken as a headline-only answer.
            return answered("".join(b.text for b in response.content if b.type == "text"))

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_uses:
            if len(queries) >= max_queries:
                tool_results.append({
                    "type": "tool_result", "tool_use_id": block.id, "is_error": True,
                    "content": "No queries left. Answer from the results above, or call no_data.",
                })
                continue
            sql, params = block.input.get("sql", ""), list(block.input.get("params", []))
            queries.append((sql, params))
            numbered.append(None)  # replaced by the rows if the query succeeds
            try:
                result = query_fn(sql, params)
            except QueryRejected as e:
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "is_error": True, "content": f"Rejected: {e}"})
                continue
            except Exception as e:  # e.g. a column that doesn't exist: let the model fix it
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "is_error": True, "content": f"Query failed: {type(e).__name__}: {e}"})
                continue
            results.append(result)
            numbered[-1] = result
            tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                 "content": format_result(result, len(queries))})
        messages.append({"role": "user", "content": tool_results})

    return finish("no_data", NO_DATA_MESSAGE, "query budget used up")
