"""The serving copies: each mart, published from Snowflake to the Postgres database the
website and its LLM read (see serving.py for why, and for the write-audit-publish swap)."""

import dagster as dg
from dagster_snowflake import SnowflakeResource

from nfl_dagster.resources import SNOWFLAKE_DATABASE
from nfl_dagster.serving import SCHEMA, ServingPostgresResource, postgres_type, publish_table

# Every mart is served, with its primary key: the column dbt tests as unique on that mart
# (test_served_primary_keys_are_tested_unique_in_dbt keeps the two in step).
# test_every_mart_is_served fails when a new mart isn't listed here.
SERVED_MARTS = {
    "team_season_epa": "team_season_key",
    "qb_season_epa": "qb_season_key",
    "game_results_vs_spread": "game_id",
    "team_fourth_down": "team_season_key",
    "qb_contract_value": "qb_season_key",
    "player_season_efficiency": "player_season_role_key",
    "team_player_leaders": "team_season_role_key",
    "team_rosters": "roster_key",
    "team_offensive_line": "team_season_key",
    "player_season_vs_league": "player_season_role_key",
    "player_careers": "player_role_key",
}

# When should the website's copy of a mart update? As soon as the mart does (eager), but not
# while ANY check on the mart has failed. That's stricter than the dbt models' gate, which
# only looks at blocking checks: dbt tests aren't blocking, so a mart whose tests failed is
# still materialized, and without this its bad rows would reach the website.
NO_FAILED_CHECKS_UPSTREAM = (
    ~dg.AutomationCondition.any_deps_match(
        dg.AutomationCondition.any_checks_match(dg.AutomationCondition.check_failed())
    )
).with_label("no_failed_checks_upstream")

SERVING_AUTOMATION_CONDITION = dg.AutomationCondition.eager() & NO_FAILED_CHECKS_UPSTREAM

COLUMNS_SQL = f"""
    select lower(column_name), data_type, numeric_precision, numeric_scale
    from {SNOWFLAKE_DATABASE}.information_schema.columns
    where table_schema = 'MARTS' and table_name = %s
    order by ordinal_position
"""


# One asset per mart, so lineage reaches the website mart by mart (marts/x -> serving/x),
# and a run can publish just the marts that changed (can_subset).
@dg.multi_asset(
    specs=[
        dg.AssetSpec(
            ["serving", mart],
            deps=[dg.AssetKey(["marts", mart])],
            group_name="serving",
            kinds={"snowflake", "postgres"},
            automation_condition=SERVING_AUTOMATION_CONDITION,
            description=f"marts.{mart} in the serving database (Prisma Postgres), copied from Snowflake.",
        )
        for mart in SERVED_MARTS
    ],
    can_subset=True,
)
def publish_marts(
    context: dg.AssetExecutionContext,
    snowflake: SnowflakeResource,
    serving: ServingPostgresResource,
):
    for key in context.selected_asset_keys:
        mart = key.path[-1]
        source = f"{SNOWFLAKE_DATABASE}.MARTS.{mart.upper()}"
        with snowflake.get_connection() as sf:
            cur = sf.cursor()
            described = cur.execute(COLUMNS_SQL, (mart.upper(),)).fetchall()
            columns = [(name, postgres_type(t, p, s)) for name, t, p, s in described]
            rows = cur.execute(f"select * from {source}").fetchall()
        with serving.get_connection() as pg:
            result = publish_table(
                pg, mart, columns, rows, primary_key=[SERVED_MARTS[mart]], source=source
            )
        yield dg.MaterializeResult(
            asset_key=key,
            metadata={
                "serving_table": dg.MetadataValue.text(f"{SCHEMA}.{mart}"),
                "source": dg.MetadataValue.text(source),
                "rows_published": dg.MetadataValue.int(result["rows_published"]),
                "column_count": dg.MetadataValue.int(len(columns)),
                "primary_key": dg.MetadataValue.text(SERVED_MARTS[mart]),
            },
        )
