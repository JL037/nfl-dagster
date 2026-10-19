"""The Ask loop, against a scripted fake model: no API calls, no cost.

Each test scripts what "the model" says turn by turn, and checks what the loop does with it:
answers built only from query results, the standard no-data reply otherwise.
"""

from types import SimpleNamespace

import pytest

from nfl_ask.agent import NO_DATA_MESSAGE, answer_question, unverified_numbers
from nfl_ask.query import QueryRejected, QueryResult


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(name, **inputs):
    tool.counter += 1
    return SimpleNamespace(type="tool_use", id=f"toolu_{tool.counter}", name=name, input=inputs)


tool.counter = 0


def turn(*blocks, stop="tool_use"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=100, output_tokens=20))


class FakeClient:
    """Plays back scripted model turns and records every request it receives."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []
        self.messages = self

    def create(self, **request):
        # Snapshot the messages as sent: the loop keeps appending to the same list.
        self.requests.append({**request, "messages": list(request["messages"])})
        return self.turns.pop(0)


MAYE = QueryResult(columns=["passer_name", "cap_share", "epa_over_expected"],
                   rows=[("D.Maye", 0.0298, 0.2953)], truncated=False)


def make_query_fn(results=None, reject=None):
    calls = []

    def query_fn(sql, params):
        calls.append((sql, params))
        if reject and reject in sql:
            raise QueryRejected("Text values must be a bound parameter")
        return results.pop(0) if results else MAYE

    query_fn.calls = calls
    return query_fn


def ask(turns, query_fn=None, **kwargs):
    client = FakeClient(turns)
    query_fn = query_fn or make_query_fn()
    result = answer_question("How good a value was Drake Maye in 2025?", client=client,
                             query_fn=query_fn, catalog="CATALOG", **kwargs)
    return result, client, query_fn


def test_answers_from_query_results():
    result, client, query_fn = ask([
        turn(tool("run_query", sql="select * from qb_contract_value where passer_name = %s", params=["D.Maye"])),
        turn(text("Drake Maye was +0.295 EPA per dropback over expected at 3.0% of the cap."), stop="end_turn"),
    ])
    assert result.status == "answered"
    assert "Drake Maye" in result.text
    assert result.queries == [("select * from qb_contract_value where passer_name = %s", ["D.Maye"])]
    # The query's rows went back to the model as the tool result.
    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and "D.Maye" in tool_result["content"]


def test_no_data_tool_gives_the_standard_reply():
    result, _, query_fn = ask([turn(tool("no_data", reason="No injury data is served."))])
    assert result.status == "no_data"
    assert result.text == NO_DATA_MESSAGE
    assert result.reason == "model: No injury data is served."
    assert query_fn.calls == []


def test_query_budget_is_enforced():
    """A model that keeps querying gets 3 queries, then the no-data reply: no deep digging."""
    endless = [turn(tool("run_query", sql="select * from qb_season_epa", params=[])) for _ in range(6)]
    result, client, query_fn = ask(endless, max_queries=3)
    assert len(query_fn.calls) == 3
    assert len(client.requests) <= 4  # three queries, then one last chance to answer
    assert result.status == "no_data" and result.text == NO_DATA_MESSAGE
    assert result.reason == "query budget used up"


def test_rejected_query_is_reported_to_the_model_and_counts():
    result, client, query_fn = ask([
        turn(tool("run_query", sql="select * from qb_contract_value where passer_name = 'D.Maye'", params=[])),
        turn(tool("run_query", sql="select * from qb_contract_value where passer_name = %s", params=["D.Maye"])),
        turn(text("Drake Maye was +0.295 over expected."), stop="end_turn"),
    ], query_fn=make_query_fn(reject="'D.Maye'"))
    error_result = client.requests[1]["messages"][-1]["content"][0]
    assert error_result["is_error"] is True and "bound parameter" in error_result["content"]
    assert len(query_fn.calls) == 2
    assert result.status == "answered"


def test_a_number_not_in_any_result_turns_the_answer_into_no_data():
    """The model 'knows' a number from training: it isn't in our data, so it isn't said."""
    result, _, _ = ask([
        turn(tool("run_query", sql="select * from qb_contract_value where passer_name = %s", params=["D.Maye"])),
        turn(text("Drake Maye threw 31 touchdowns and was +0.295 over expected."), stop="end_turn"),
    ])
    assert result.status == "no_data"
    assert result.text == NO_DATA_MESSAGE
    # Why, for the evals; the visitor only ever sees NO_DATA_MESSAGE.
    assert result.reason == "numbers not in any result: 31"


def test_an_answer_without_any_query_is_not_trusted():
    """No numbers to check here, so only the no-query rule can stop it."""
    result, _, _ = ask([turn(text("Drake Maye was a great value."), stop="end_turn")])
    assert result.status == "no_data"
    assert result.reason == "answer without a query"


def test_refusal_gives_the_standard_reply():
    """After a real query, a refusal carrying plausible text must not pass as an answer."""
    result, _, _ = ask([
        turn(tool("run_query", sql="select * from qb_contract_value where passer_name = %s", params=["D.Maye"])),
        turn(text("Drake Maye was a great value."), stop="refusal"),
    ])
    assert result.status == "no_data"
    assert result.reason == "refusal"


def test_requests_carry_the_catalog_rules_and_tools():
    _, client, _ = ask([turn(tool("no_data", reason="x"))])
    request = client.requests[0]
    system = "".join(block["text"] for block in request["system"])
    assert "CATALOG" in system
    assert "No data, no answer" in system
    assert "Compute every number you state in SQL" in system
    assert {t["name"] for t in request["tools"]} == {"run_query", "no_data"}
    assert request["model"] == "claude-haiku-5-5"


@pytest.mark.parametrize(
    ("answer", "unverified"),
    [
        ("+0.295 over expected", []),          # rounded from 0.2953
        ("+0.30 over expected", []),           # coarser rounding
        ("at 3.0% of the cap", []),            # 0.0298 shown as a percent
        ("at 2.98% of the cap", []),
        ("in 2025", []),                        # in the question
        ("the top 3 values", []),               # small counts are prose, not data
        ("31 touchdowns", ["31"]),             # not in any result
        ("+0.41 over expected", ["0.41"]),
        ("about 12.5% of the cap", ["12.5"]),
    ],
)
def test_unverified_numbers(answer, unverified):
    question = "How good a value was Drake Maye in 2025?"
    assert unverified_numbers(answer, [MAYE], question) == unverified


def test_a_sign_may_be_said_in_words():
    """Seen in the evals: LA's defense was -0.062 EPA per play, written "allowed 0.062"."""
    defense = QueryResult(columns=["team", "def_epa_per_play"], rows=[("LA", -0.0617)], truncated=False)
    assert unverified_numbers("LA allowed 0.062 EPA per play.", [defense], "Best defense?") == []
    assert unverified_numbers("LA allowed 0.071 EPA per play.", [defense], "Best defense?") == ["0.071"]
