"""The eval scoring rules: strict enough to catch a wrong answer, loose enough for wording."""

import pytest

from nfl_ask.scoring import check


@pytest.mark.parametrize(
    ("answer", "kind", "expected", "decimals", "row", "ok"),
    [
        ("Drake Maye was the best value.", "name", "D.Maye", 0, {}, True),
        ("Josh Allen was the best value.", "name", "D.Maye", 0, {}, False),
        ("The Los Angeles Rams led the league.", "team", "LA", 0, {"team_name": "Los Angeles Rams"}, True),
        ("LA led the league.", "team", "LA", 0, {"team_name": "Los Angeles Rams"}, True),
        ("Houston led the league.", "team", "LA", 0, {"team_name": "Los Angeles Rams"}, False),
        ("He was +0.295 over expected.", "value", 0.2953, 2, {}, True),
        ("He was +0.30 over expected.", "value", 0.2953, 2, {}, True),
        ("He was about 0.3 over expected.", "value", 0.2953, 2, {}, False),   # not precise enough
        ("He was +0.41 over expected.", "value", 0.2953, 2, {}, False),
        ("His cap hit was 10.6% of the cap.", "percent", 10.6123, 1, {}, True),
        ("His cap hit was 11% of the cap.", "percent", 10.6123, 1, {}, False),
        ("Home teams covered 47.7% of the time.", "percent", 47.68, 1, {}, True),
        ("19 quarterbacks were worth it.", "count", 19, 0, {}, True),
        ("18 quarterbacks were worth it.", "count", 19, 0, {}, False),
        ("He was -0.23 below expected.", "value", -0.2349, 2, {}, True),
    ],
)
def test_check(answer, kind, expected, decimals, row, ok):
    assert check(answer, kind, expected, row, decimals) is ok


def test_full_name_check_needs_the_whole_name():
    from nfl_ask.scoring import check
    assert check("Jordan Love led the league.", "full_name", "Jordan Love", {})
    assert not check("J.Love led the league.", "full_name", "Jordan Love", {})
    assert not check("Josh Love led the league.", "full_name", "Jordan Love", {})


def test_team_check_without_a_nickname_uses_the_abbreviation():
    from nfl_ask.scoring import check
    assert check("LAC covered 13 times.", "team", "LAC", {"team": "LAC"})
    assert not check("DET covered 12 times.", "team", "LAC", {"team": "LAC"})
