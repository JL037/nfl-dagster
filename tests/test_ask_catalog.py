"""The catalog the model reads: built from the dbt YAML, the mart SQL headers, and the served
columns. Formatting is tested here without a database."""

from nfl_ask.catalog import PROJECT_ROOT, catalog_text

COLUMNS = {
    "qb_contract_value": [("qb_season_key", "text"), ("epa_over_expected", "double precision"),
                          ("worth_it", "boolean")],
    "team_season_epa": [("team_season_key", "text"), ("off_epa_per_play", "double precision")],
    "_publications": [("table_name", "text"), ("published_at", "timestamp with time zone")],
}


def test_catalog_has_descriptions_definitions_and_columns():
    text = catalog_text(COLUMNS, PROJECT_ROOT)
    section = text.split("## qb_contract_value")[1].split("## ")[0]
    # The mart's description and a column note, from marts.yml.
    assert "cap share" in section.lower()
    assert "worth_it boolean: True when epa_over_expected > 0" in section
    # The definitions, from the comment block at the top of qb_contract_value.sql.
    assert "cap_share = cap_number / that season's league salary cap" in section
    assert "worth_it = epa_over_expected > 0" in section


def test_every_served_table_is_listed_even_without_yaml():
    text = catalog_text(COLUMNS, PROJECT_ROOT)
    for table in COLUMNS:
        assert f"## {table}" in text
    assert "published_at timestamp with time zone" in text


def test_only_served_tables_are_described():
    """A mart in dbt but not served can't be queried, so the model must not see it."""
    text = catalog_text(COLUMNS, PROJECT_ROOT)
    assert "## game_results_vs_spread" not in text
