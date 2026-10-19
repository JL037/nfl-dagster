"""Rate limits: per visitor and for the whole site, in memory only, keyed by a salted hash of
the visitor's address (never the address itself). A fake clock, so no waiting."""

from fastapi.testclient import TestClient

from nfl_ask.agent import AskResult
from nfl_ask.web import create_app
from nfl_ask.web.limits import RateLimiter


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def limiter(clock, **limits):
    defaults = {"per_minute": 2, "per_hour": 5, "per_day_total": 8}
    return RateLimiter(clock=clock, **{**defaults, **limits})


def test_a_visitor_over_the_minute_limit_waits():
    clock = Clock(); lim = limiter(clock)
    assert lim.allow("1.2.3.4").ok and lim.allow("1.2.3.4").ok
    third = lim.allow("1.2.3.4")
    assert not third.ok and 0 < third.retry_after <= 60
    clock.now += 61
    assert lim.allow("1.2.3.4").ok


def test_the_hour_limit_holds_after_the_minute_resets():
    clock = Clock(); lim = limiter(clock)
    for _ in range(5):
        assert lim.allow("v").ok
        clock.now += 31  # under 2 a minute
    assert not lim.allow("v").ok


def test_visitors_are_limited_separately():
    clock = Clock(); lim = limiter(clock)
    lim.allow("a"); lim.allow("a")
    assert not lim.allow("a").ok
    assert lim.allow("b").ok


def test_the_whole_site_has_a_daily_cap():
    clock = Clock(); lim = limiter(clock, per_minute=100, per_hour=100)
    for i in range(8):
        assert lim.allow(f"visitor-{i}").ok
    assert not lim.allow("someone-new").ok


def test_addresses_are_never_stored():
    lim = limiter(Clock())
    lim.allow("203.0.113.7")
    assert "203.0.113.7" not in repr(lim.__dict__)


def test_old_entries_are_forgotten():
    clock = Clock(); lim = limiter(clock)
    lim.allow("v")
    clock.now += 3601
    lim.allow("w")
    assert len(lim.visitors) == 1  # v's entry is gone once its hour has passed


# --- On the page ----------------------------------------------------------------------------


class CountingAsk:
    def __init__(self):
        self.calls = 0

    def __call__(self, question):
        self.calls += 1
        return AskResult(status="no_data", text="x", queries=[])


def page(ask, lim, **kwargs):
    app = create_app(ask=ask, freshness=lambda: {}, limiter=lim, **kwargs)
    return TestClient(app)


def test_over_the_limit_gets_a_message_and_the_model_is_not_called():
    ask, clock = CountingAsk(), Clock()
    c = page(ask, limiter(clock, per_minute=1))
    c.post("/answer", data={"question": "one"})
    html = c.post("/answer", data={"question": "two"}).text
    assert ask.calls == 1
    assert "a lot of questions" in html.lower() and "seconds" in html


def test_empty_questions_do_not_use_up_the_limit():
    ask = CountingAsk()
    c = page(ask, limiter(Clock(), per_minute=1))
    c.post("/answer", data={"question": "   "})
    c.post("/answer", data={"question": "real one"})
    assert ask.calls == 1


def test_forwarded_address_is_ignored_unless_trusted():
    ask = CountingAsk()
    c = page(ask, limiter(Clock(), per_minute=1))
    c.post("/answer", data={"question": "q"}, headers={"X-Forwarded-For": "1.1.1.1"})
    c.post("/answer", data={"question": "q"}, headers={"X-Forwarded-For": "2.2.2.2"})
    assert ask.calls == 1  # a made-up header can't dodge the limit


def test_forwarded_address_is_used_behind_a_trusted_proxy():
    ask = CountingAsk()
    c = page(ask, limiter(Clock(), per_minute=1), trust_proxy=True)
    c.post("/answer", data={"question": "q"}, headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"})
    c.post("/answer", data={"question": "q"}, headers={"X-Forwarded-For": "2.2.2.2, 10.0.0.1"})
    assert ask.calls == 2  # two real visitors behind the host's proxy


def test_over_the_limit_is_a_proper_429_with_retry_after():
    c = page(CountingAsk(), limiter(Clock(), per_minute=1))
    c.post("/answer", data={"question": "one"})
    response = c.post("/answer", data={"question": "two"})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert 'data-retry-after="60"' in response.text  # the page counts down from this


def test_the_page_shows_429_messages_and_handles_failures():
    c = page(CountingAsk(), limiter(Clock()))
    html = c.get("/").text
    assert 'name="htmx-config"' in html and '"429"' in html  # htmx swaps 429s instead of ignoring them
    js = c.get("/static/app.js").text
    assert "data-retry-after" in js  # disables Ask and counts down
    assert "htmx:sendError" in js and "htmx:responseError" in js  # network and server failures
