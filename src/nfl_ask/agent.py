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
is fine, and a fraction may be shown as a percent (0.026 as 2.6%).
3. Write one Postgres SELECT per call, against these tables only (no schema prefix needed). \
Put every text value (names, teams, keys) in params and refer to it as %s; never type text \
into the SQL. Numbers such as seasons may be written directly.
4. Use the definitions below exactly as written (for example "worth it" and cap share).
5. A season with is_season_complete = false is still in progress: say its numbers are estimates.
6. Answer in one to three plain sentences. No tables, no markdown.

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


USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

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
        if any(abs(v - value) <= tolerance or abs(v * 100 - value) <= tolerance for v in values):
            continue
        unverified.append(cleaned)
    return unverified


def format_result(result: QueryResult) -> str:
    payload = {"columns": result.columns, "rows": result.rows, "truncated": result.truncated}
    return json.dumps(payload, default=str)


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

    def finish(status: str, text: str) -> AskResult:
        return AskResult(status=status, text=text, queries=queries, usage=usage)
    # Stable rules and catalog first, cached; the question is the only thing that varies.
    system = [{"type": "text", "text": RULES + catalog, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": question}]
    queries: list[tuple[str, list]] = []
    results: list[QueryResult] = []

    # At most max_queries queries, plus one last turn to answer from them.
    for _ in range(max_queries + 1):
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
            return finish("no_data", NO_DATA_MESSAGE)
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if any(block.name == "no_data" for block in tool_uses):
            return finish("no_data", NO_DATA_MESSAGE)

        if not tool_uses:
            answer = "".join(b.text for b in response.content if b.type == "text").strip()
            # No query, no answer; and every number must be backed by a result.
            if not results or not answer or unverified_numbers(answer, results, question):
                return finish("no_data", NO_DATA_MESSAGE)
            return finish("answered", answer)

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
            tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                 "content": format_result(result)})
        messages.append({"role": "user", "content": tool_results})

    return finish("no_data", NO_DATA_MESSAGE)
