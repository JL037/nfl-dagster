-- qb_contract_value must have exactly one row per qb_season_epa row from the first season
-- with a league salary cap figure (2015): the left joins to cap hits, caps and teams may leave
-- nulls, but must never drop or duplicate a QB season (a second cap row for the same player
-- and season would duplicate it). Returns a row if the counts differ.
--
-- It reads two models, so the ref tells dagster-dbt which asset owns the check; without
-- it the test isn't a Dagster check at all.
{{ config(meta={'dagster': {'ref': {'name': 'qb_contract_value'}}}) }}
select
    (select count(*) from {{ ref('qb_season_epa') }}
     where season >= (select min(season) from {{ ref('league_salary_caps') }})) as qb_seasons,
    (select count(*) from {{ ref('qb_contract_value') }}) as contract_value_rows
where qb_seasons <> contract_value_rows
