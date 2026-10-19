"""The Ask page, with a fake answer function and a fake freshness lookup: no model calls, no
database, no cost. These pin what the page promises visitors: the question travels only in the
request body and is never logged, every answer shows its SQL and where the data came from, and
nothing the model writes can run in the browser.
"""

import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from nfl_ask.agent import NO_DATA_MESSAGE, AskResult
from nfl_ask.query import QueryResult
from nfl_ask.web import MAX_QUESTION_CHARS, create_app, tables_read

PUBLISHED = datetime(2026, 10, 19, 18, 34, tzinfo=UTC)
SECRET_QUESTION = "Is Drake Maye worth it in 2025, asks visitor 4f9c?"


class FakeAsk:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.questions = result, error, []

    def __call__(self, question):
        self.questions.append(question)
        if self.error:
            raise self.error
        return self.result


LEADERS = QueryResult(columns=["qb_season_key", "passer_name", "cap_share", "epa_over_expected"],
                      rows=[("2025_maye", "D.Maye", 0.0298, 0.2953), ("2025_purdy", "B.Purdy", 0.0421, 0.1812)],
                      truncated=False)
BAR = {"kind": "bar", "query": 1, "x": "passer_name", "y": "epa_over_expected", "series": None,
       "title": "EPA over expected, 2025"}


def answered(text="Drake Maye was the best value QB in 2025.", queries=None, chart=None,
             explanation="He was 0.295 EPA per dropback over expected at 3.0% of the cap."):
    queries = queries if queries is not None else [
        ("select player, epa_over_expected from qb_contract_value where player = %s", ["Drake Maye"])
    ]
    return AskResult(status="answered", text=f"{text} {explanation}", queries=queries, headline=text,
                     explanation=explanation, chart=chart, results=[LEADERS] * len(queries))


def client(ask=None):
    app = create_app(ask=ask or FakeAsk(answered()), freshness=lambda: {"qb_contract_value": PUBLISHED})
    return TestClient(app, raise_server_exceptions=False)


# --- The page -----------------------------------------------------------------------------------


def test_question_box_posts_in_the_request_body():
    page = client().get("/").text
    assert 'hx-post="/answer"' in page
    assert 'name="question"' in page
    assert "hx-get" not in page  # a GET would put the question in the URL, and in access logs


def test_example_questions_are_clickable():
    page = client().get("/").text
    assert page.count('name="question" value="') >= 3


def test_page_says_how_fresh_the_data_is():
    assert "Data as of Oct 19, 2026" in client().get("/").text


def test_htmx_is_served_from_this_site():
    c = client()
    page = c.get("/").text
    assert 'src="/static/htmx.min.js"' in page
    assert "unpkg" not in page and "cdn" not in page  # no third party sees who visits
    assert c.get("/static/htmx.min.js").status_code == 200


# --- Answers ------------------------------------------------------------------------------------


def test_answer_shows_its_sql_values_and_sources():
    html = client().post("/answer", data={"question": "Was Maye worth it?"}).text
    assert "Drake Maye was the best value QB in 2025." in html
    assert "select player, epa_over_expected from qb_contract_value where player = %s" in html
    # The bound value, shown next to its query (the answer text names him too, so look for it there).
    assert "Values: <code>Drake Maye</code>" in html
    assert "qb_contract_value" in html and "Oct 19, 2026" in html  # the mart and when it was published


def test_answer_leads_with_headline_then_explanation():
    html = client().post("/answer", data={"question": "Was Maye worth it?"}).text
    assert 'class="headline">Drake Maye was the best value QB in 2025.' in html
    assert html.index("best value QB") < html.index("0.295 EPA per dropback over expected")


def test_the_chart_is_drawn_from_the_query_rows():
    html = client(FakeAsk(answered(chart=BAR))).post("/answer", data={"question": "q"}).text
    assert "<svg" in html and html.count('class="bar ') == 2


def test_no_chart_when_none_was_chosen():
    assert "<svg" not in client().post("/answer", data={"question": "q"}).text


def test_the_data_is_shown_as_a_readable_table():
    html = client().post("/answer", data={"question": "q"}).text
    assert "<table" in html and "Quarterback" in html and "3.0%" in html
    assert "2025_maye" not in html  # internal keys stay out of the table


def test_where_this_comes_from_uses_the_dbt_descriptions():
    html = client().post("/answer", data={"question": "q"}).text
    assert "Where this comes from" in html
    assert "Every QB season from qb_season_epa" in html  # qb_contract_value's description in marts.yml


def test_no_data_suggests_what_can_be_asked():
    ask = FakeAsk(AskResult(status="no_data", text=NO_DATA_MESSAGE, queries=[]))
    html = client(ask).post("/answer", data={"question": "Who wins the Super Bowl?"}).text
    assert "Try asking about" in html


def test_no_data_gets_the_standard_reply():
    ask = FakeAsk(AskResult(status="no_data", text=NO_DATA_MESSAGE, queries=[]))
    html = client(ask).post("/answer", data={"question": "Who wins the Super Bowl?"}).text
    assert NO_DATA_MESSAGE.replace("'", "&#39;") in html


def test_model_text_cannot_run_in_the_page():
    ask = FakeAsk(answered(text='<script>alert("x")</script>',
                           queries=[("select 1 from qb_season_epa where x = %s", ["<img onerror=1>"])]))
    html = client(ask).post("/answer", data={"question": "hi"}).text
    assert "<script>alert" not in html and "<img onerror" not in html
    assert "&lt;script&gt;" in html


def test_answers_are_never_cached():
    response = client().post("/answer", data={"question": "Was Maye worth it?"})
    assert response.headers["cache-control"] == "no-store"


# --- Privacy and cost ---------------------------------------------------------------------------


def test_a_question_in_the_url_is_refused():
    ask = FakeAsk(answered())
    response = client(ask).get("/answer", params={"question": SECRET_QUESTION})
    assert response.status_code == 405
    assert ask.questions == []


def test_question_is_not_logged_even_when_answering_fails(caplog):
    caplog.set_level(logging.DEBUG)
    response = client(FakeAsk(error=RuntimeError("model unavailable"))).post(
        "/answer", data={"question": SECRET_QUESTION}
    )
    assert response.status_code == 200  # a friendly message in the answer area, not an error page
    assert "try again" in response.text.lower()
    assert "4f9c" not in caplog.text
    assert "4f9c" not in response.text


@pytest.mark.parametrize("question", ["", "   ", "x" * (MAX_QUESTION_CHARS + 1)])
def test_empty_or_overlong_questions_never_reach_the_model(question):
    ask = FakeAsk(answered())
    response = client(ask).post("/answer", data={"question": question})
    assert response.status_code == 200
    assert ask.questions == []


# --- Which marts an answer read -----------------------------------------------------------------


def test_tables_read_lists_marts_not_ctes():
    sql = ("with best as (select * from qb_contract_value) "
           "select b.player from best b join qb_season_epa e using (qb_season_key)")
    assert tables_read(sql) == ["qb_contract_value", "qb_season_epa"]


def test_tables_read_survives_sql_it_cannot_parse():
    assert tables_read("select from where") == []


# --- Download PDF -------------------------------------------------------------------------------


def test_answers_offer_a_pdf_download():
    html = client().post("/answer", data={"question": "Was Maye worth it?"}).text
    assert "data-pdf" in html and "Download PDF" in html


def test_no_pdf_button_without_an_answer():
    ask = FakeAsk(AskResult(status="no_data", text=NO_DATA_MESSAGE, queries=[]))
    assert "data-pdf" not in client(ask).post("/answer", data={"question": "q"}).text


def test_the_page_loads_its_own_script_and_a_print_layout():
    c = client()
    page = c.get("/").text
    assert 'src="/static/app.js"' in page
    css = c.get("/static/style.css").text
    assert "@media print" in css
    js = c.get("/static/app.js").text
    assert "window.print()" in js


def test_each_answer_logs_its_cost_but_never_the_question(caplog):
    caplog.set_level(logging.INFO)
    result = answered()
    result.usage = {"input_tokens": 12000, "output_tokens": 900, "cache_read_input_tokens": 3000,
                    "cache_creation_input_tokens": 0}
    client(FakeAsk(result)).post("/answer", data={"question": SECRET_QUESTION})
    assert "cost=$0.00168" in caplog.text  # 12000*0.10 + 900*0.50 + 3000*0.01 per million
    assert "4f9c" not in caplog.text


# --- Credit for the data ------------------------------------------------------------------------


def test_every_served_mart_credits_its_sources():
    """A new mart can't be served without saying where its data comes from."""
    from nfl_dagster.assets.serving import SERVED_MARTS
    from nfl_ask.web.present import MART_SOURCES
    assert set(SERVED_MARTS) <= set(MART_SOURCES)
    assert all(MART_SOURCES[m] for m in SERVED_MARTS)


def test_the_footer_credits_the_data_and_its_license():
    page = client().get("/").text
    assert "https://github.com/nflverse" in page and "https://overthecap.com" in page
    assert "https://creativecommons.org/licenses/by/4.0/" in page
    assert "not affiliated" in page.lower()


def test_an_answer_credits_the_sources_of_the_marts_it_read():
    html = client().post("/answer", data={"question": "q"}).text  # reads qb_contract_value
    sources = html[html.index("Where this comes from"):]
    assert "OverTheCap" in sources and "nflverse play-by-play" in sources


def test_credits_follow_the_marts_actually_read():
    epa_only = answered(queries=[("select passer_full_name, epa_per_dropback from qb_season_epa", [])])
    html = client(FakeAsk(epa_only)).post("/answer", data={"question": "q"}).text
    sources = html[html.index("Where this comes from"):]
    assert "nflverse play-by-play" in sources and "OverTheCap" not in sources
