"""How an answer's data is shown: readable column names and numbers, tables, and charts drawn
from the query's own rows. Pure functions, no model or database."""

import re

import pytest

from nfl_ask.query import QueryResult
from nfl_ask.web.charts import render_chart
from nfl_ask.web.present import column_label, data_table, format_value, mart_docs

LEADERS = QueryResult(
    columns=["qb_season_key", "passer_name", "season", "cap_share", "cap_number", "epa_over_expected", "worth_it"],
    rows=[("2025_maye", "D.Maye", 2025, 0.0298, 8_200_000.0, 0.2953, True),
          ("2025_purdy", "B.Purdy", 2025, 0.0421, 11_600_000.0, 0.1812, True),
          ("2025_young", "B.Young", 2025, 0.0350, 9_600_000.0, -0.0874, False)],
    truncated=False,
)


# --- Column names and numbers ------------------------------------------------------------------


@pytest.mark.parametrize(("column", "label"), [
    ("passer_name", "Quarterback"),
    ("epa_over_expected", "EPA over expected"),
    ("cap_share", "Cap share"),
    ("avg_epa_per_play", "Avg EPA per play"),  # a column the model computed
    ("qb_count", "QB count"),
])
def test_column_labels_read_like_english(column, label):
    assert column_label(column) == label


@pytest.mark.parametrize(("column", "value", "shown"), [
    ("cap_share", 0.0298, "3.0%"),
    ("go_pct", 0.712, "71.2%"),
    ("cap_number", 55_260_000.0, "$55.3M"),
    ("cap_number", 925_000.0, "$925K"),
    ("epa_over_expected", 0.2953, "0.295"),
    ("epa_over_expected", -0.0874, "−0.087"),
    ("season", 2025, "2025"),
    ("dropbacks", 1234, "1,234"),
    ("worth_it", True, "Yes"),
    ("team", None, "—"),
])
def test_values_are_formatted_for_people(column, value, shown):
    assert format_value(column, value) == shown


def test_percent_columns_already_in_percent_are_left_alone():
    assert format_value("go_pct", 71.2) == "71.2%"


# --- Tables ------------------------------------------------------------------------------------


def test_data_table_hides_internal_keys_and_formats_cells():
    table = data_table(LEADERS)
    assert "qb_season_key" not in table["columns"] and "Quarterback" in table["labels"]
    first = dict(zip(table["columns"], table["rows"][0]))
    assert first["cap_share"] == "3.0%" and first["worth_it"] == "Yes"


def test_data_table_caps_long_results_and_says_how_many_are_hidden():
    many = QueryResult(columns=["passer_name", "dropbacks"], rows=[(f"P{i}", i) for i in range(40)], truncated=False)
    table = data_table(many, max_rows=25)
    assert len(table["rows"]) == 25 and table["hidden"] == 15


def test_mart_docs_come_from_the_dbt_yaml():
    docs = mart_docs()
    assert docs["qb_contract_value"]["description"].startswith("Every QB season")
    assert "cap_share" in docs["qb_contract_value"]["columns"]


# --- Charts ------------------------------------------------------------------------------------


def bar(**overrides):
    return {"kind": "bar", "query": 1, "x": "passer_name", "y": "epa_over_expected",
            "series": None, "title": "EPA over expected, 2025", **overrides}


def test_bar_chart_draws_one_bar_per_row_from_the_rows_themselves():
    svg = render_chart(bar(), LEADERS)
    assert svg.startswith("<svg") and 'role="img"' in svg
    assert svg.count('class="bar ') == 3
    assert "0.295" in svg and "D.Maye" in svg  # value at the tip, category on the axis


def test_negative_bars_are_drawn_in_the_negative_color():
    svg = render_chart(bar(), LEADERS)
    assert svg.count('class="bar neg"') == 1 and svg.count('class="bar pos"') == 2


def test_every_mark_has_a_hover_tooltip():
    svg = render_chart(bar(), LEADERS)
    assert len(re.findall(r"<title>[^<]+</title>", svg)) >= 3 + 1  # three bars and the chart


def test_chart_text_is_escaped():
    sneaky = QueryResult(columns=["passer_name", "epa_over_expected"], rows=[("<script>x</script>", 0.1)], truncated=False)
    svg = render_chart(bar(title="<b>t</b>"), sneaky)
    assert "<script>" not in svg and "<b>" not in svg


def test_line_chart_with_two_series_has_a_legend():
    trend = QueryResult(columns=["season", "passer_name", "epa_per_dropback"],
                        rows=[(2023, "A", 0.1), (2024, "A", 0.2), (2023, "B", 0.05), (2024, "B", 0.12)], truncated=False)
    svg = render_chart({"kind": "line", "query": 1, "x": "season", "y": "epa_per_dropback",
                        "series": "passer_name", "title": "EPA per dropback"}, trend)
    assert svg.count('class="line ') == 2 and 'class="legend"' in svg


def test_single_series_needs_no_legend():
    trend = QueryResult(columns=["season", "epa_per_dropback"], rows=[(2023, 0.1), (2024, 0.2)], truncated=False)
    svg = render_chart({"kind": "line", "query": 1, "x": "season", "y": "epa_per_dropback",
                        "series": None, "title": "t"}, trend)
    assert 'class="legend"' not in svg


def test_more_than_three_series_is_not_charted():
    rows = [(2024, name, 0.1) for name in "ABCD"]
    many = QueryResult(columns=["season", "passer_name", "epa_per_dropback"], rows=rows, truncated=False)
    assert render_chart({"kind": "line", "query": 1, "x": "season", "y": "epa_per_dropback",
                         "series": "passer_name", "title": "t"}, many) is None


def test_scatter_draws_every_point_and_names_it_on_hover():
    svg = render_chart({"kind": "scatter", "query": 1, "x": "cap_share", "y": "epa_over_expected",
                        "series": None, "title": "Cap share vs EPA over expected"}, LEADERS)
    assert svg.count('class="dot ') == 3
    assert "<title>D.Maye" in svg


def test_yes_no_columns_are_not_aligned_as_numbers():
    table = data_table(LEADERS)
    assert table["numeric"][table["columns"].index("worth_it")] is False


def test_columns_that_never_change_move_to_a_note():
    same = QueryResult(columns=["passer_name", "season", "epa_over_expected"],
                       rows=[("A", 2025, 0.2), ("B", 2025, 0.1)], truncated=False)
    table = data_table(same)
    assert "season" not in table["columns"] and ("Season", "2025") in table["constants"]


def test_a_single_row_keeps_all_its_columns():
    one = QueryResult(columns=["season", "is_season_complete"], rows=[(2025, True)], truncated=False)
    assert data_table(one)["columns"] == ["season", "is_season_complete"]


def test_charted_columns_come_first():
    table = data_table(LEADERS, first=["passer_name", "epa_over_expected"])
    assert table["columns"][:2] == ["passer_name", "epa_over_expected"]


def test_axis_ticks_use_only_the_decimals_they_need():
    svg = render_chart(bar(), LEADERS)
    assert ">0.1<" in svg and ">0.100<" not in svg


def test_percent_suffixes_in_computed_names_read_as_percent():
    assert column_label("avg_epa_under_5pct") == "Avg EPA under 5%"


def test_full_name_replaces_the_short_name_in_tables():
    both = QueryResult(columns=["passer_name", "passer_full_name", "epa_over_expected"],
                       rows=[("J.Love", "Jordan Love", 0.18)], truncated=False)
    table = data_table(both)
    assert "passer_name" not in table["columns"]
    assert table["labels"][table["columns"].index("passer_full_name")] == "Quarterback"


def test_short_name_alone_is_still_shown():
    assert data_table(QueryResult(columns=["passer_name"], rows=[("J.Love",)], truncated=False))["columns"] == ["passer_name"]


@pytest.mark.parametrize(("column", "value", "shown"), [
    ("ol_avg_years_exp", 5.2857, "5.3"),
    ("ol_avg_age", 27.04, "27.0"),
    ("years_exp", 7, "7"),
])
def test_experience_and_age_read_as_years(column, value, shown):
    assert format_value(column, value) == shown
