"""The catalog the model reads: built from the dbt YAML, the mart SQL headers, and the served
columns. Formatting is tested here without a database."""

from nfl_ask.catalog import PROJECT_ROOT, LiveCatalog, catalog_text

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


class FakeConn:
    """Answers the served-columns query with whatever tables are "published" right now."""

    def __init__(self, columns):
        self.columns, self.queries = columns, 0

    def execute(self, sql):
        self.queries += 1
        rows = [(t, c, d) for t, cols in self.columns.items() for c, d in cols]
        return type("Result", (), {"fetchall": lambda _self: rows})()


def test_a_newly_published_table_reaches_the_model_without_a_restart():
    conn = FakeConn({"team_season_epa": COLUMNS["team_season_epa"]})
    catalog = LiveCatalog(PROJECT_ROOT)
    assert "## qb_contract_value" not in catalog(conn)
    conn.columns["qb_contract_value"] = COLUMNS["qb_contract_value"]  # its first publish
    assert "## qb_contract_value" in catalog(conn)


def test_the_catalog_text_is_rebuilt_only_when_the_tables_change():
    conn = FakeConn(dict(COLUMNS))
    catalog = LiveCatalog(PROJECT_ROOT)
    first = catalog(conn)
    assert catalog(conn) is first  # the same text object: nothing rebuilt, the prompt cache still hits
    assert conn.queries == 2  # but every question checks
