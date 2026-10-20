"""Share links: what they promise visitors. Nothing is saved until Share is clicked; only an
answer this server rendered can be shared; the link stops working after 24 hours; the model
can't read shared answers; shared pages stay out of search engines."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from nfl_ask.agent import NO_DATA_MESSAGE, AskResult
from nfl_ask.query import QueryRejected, validate_sql
from nfl_ask.web import create_app
from nfl_ask.web.share import MemoryShares, Tickets
from tests.test_ask_web import PUBLISHED, FakeAsk, answered

START = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)


@pytest.fixture
def site():
    clock, shares = [START], MemoryShares()
    app = create_app(ask=FakeAsk(answered()), freshness=lambda: {"qb_contract_value": PUBLISHED},
                     shares=shares, now=lambda: clock[0])
    return TestClient(app, raise_server_exceptions=False), shares, clock


def ticket(html):
    return dict(zip(("payload", "signature"), re.findall(r'name="(?:payload|signature)" value="([^"]+)"', html)))


def share(client, html):
    reply = client.post("/share", data=ticket(html)).text
    return re.search(r'data-share-path="(/r/[^"]+)"', reply).group(1)


def test_nothing_is_saved_until_share_is_clicked(site):
    client, shares, _ = site
    html = client.post("/answer", data={"question": "Who was the best value QB in 2025?"}).text
    assert "Share link" in html and shares.rows == {}


def test_a_shared_link_shows_the_answer(site):
    client, _, _ = site
    path = share(client, client.post("/answer", data={"question": "Who was the best value QB in 2025?"}).text)
    page = client.get(path)
    assert page.status_code == 200
    assert "Drake Maye was the best value QB in 2025." in page.text
    assert "Who was the best value QB in 2025?" in page.text  # the question it answered
    assert 'name="payload"' not in page.text  # the saved answer has no share form of its own


def test_the_link_expires_after_24_hours(site):
    client, shares, clock = site
    path = share(client, client.post("/answer", data={"question": "q"}).text)
    clock[0] = START + timedelta(hours=23, minutes=59)
    assert client.get(path).status_code == 200
    clock[0] = START + timedelta(hours=24)
    expired = client.get(path)
    assert expired.status_code == 404 and "expired or doesn't exist" in expired.text
    assert shares.rows == {}  # deleted, not just hidden


def test_only_answers_this_server_rendered_can_be_shared(site):
    client, shares, _ = site
    forged = Tickets().issue("<script>alert(1)</script>")  # signed with someone else's key
    reply = client.post("/share", data=dict(zip(("payload", "signature"), forged))).text
    assert "be shared anymore" in reply and shares.rows == {}
    genuine = ticket(client.post("/answer", data={"question": "q"}).text)
    tampered = {**genuine, "payload": genuine["payload"][:-4] + "AAAA"}
    assert "be shared anymore" in client.post("/share", data=tampered).text and shares.rows == {}


def test_no_data_replies_have_no_share_button(site):
    client, _, _ = site
    app = create_app(ask=FakeAsk(AskResult(status="no_data", text=NO_DATA_MESSAGE)),
                     freshness=dict, shares=MemoryShares())
    assert "Share link" not in TestClient(app).post("/answer", data={"question": "q"}).text


def test_shared_pages_stay_out_of_search_engines(site):
    client, _, _ = site
    page = client.get(share(client, client.post("/answer", data={"question": "q"}).text))
    assert page.headers["x-robots-tag"] == "noindex, nofollow"
    assert page.headers["referrer-policy"] == "no-referrer"
    assert 'name="robots" content="noindex, nofollow"' in page.text


def test_made_up_links_find_nothing(site):
    client, _, _ = site
    assert client.get("/r/not-a-real-token").status_code == 404
    assert client.get("/r/" + "A" * 22).status_code == 404


def test_the_model_cannot_read_shared_answers():
    with pytest.raises(QueryRejected):
        validate_sql("select html from ask.shares")


def test_sharing_is_off_without_a_store():
    app = create_app(ask=FakeAsk(answered()), freshness=dict)
    client = TestClient(app)
    assert "Share link" not in client.post("/answer", data={"question": "q"}).text
    assert client.get("/r/" + "A" * 22).status_code == 404


def test_the_privacy_note_says_what_share_keeps(site):
    client, _, _ = site
    page = " ".join(client.get("/").text.split())
    assert "If you click Share, that one answer (with its question) is saved behind a private link and deleted after 24 hours." in page
