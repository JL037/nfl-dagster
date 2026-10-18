-- One row per player per season: that season's salary cap charge (the "cap hit"), from
-- OverTheCap's per-season history. This is what answers "what did this player cost his team
-- in season X?", using the real cap charge instead of estimating it from year_signed + years.
--
-- Amounts are in millions of dollars. cap_percent is OverTheCap's figure: the share of the
-- team's adjusted cap, rounded to 0.1%. It isn't cap_number / league cap (2016's league cap
-- was $155.27M; cap_number / cap_percent ranges from $153M to $178M that year).
with players as (
    -- season_history describes the player, not the contract: every contract row for a
    -- player carries the same list (assert_cap_hits_keep_every_season guards this).
    -- Flattening every contract row would count each season once per contract, so keep one
    -- row per player first. Name, position and gsis_id come from the latest contract.
    select
        otc_id,
        max(gsis_id) as gsis_id,
        max_by(player, year_signed) as player_name,
        max_by(position, year_signed) as position,
        any_value(season_history) as season_history
    from {{ source('raw', 'contracts') }}
    group by otc_id
)

select
    players.otc_id || '-' || season.value:year::string as player_season_key,
    players.otc_id,
    -- Joins to play-by-play (passer_id). Null for players nflverse can't map. In 4 cases one
    -- gsis_id has two OverTheCap players in the same season (none of them QBs), which is
    -- why the key is otc_id.
    players.gsis_id,
    players.player_name,
    players.position,
    -- try_to_number, not ::int: Snowflake may cast before applying the WHERE below (when a
    -- query filters or groups by season), and ::int raises an error on the 'Total' rows.
    -- See tests/assert_cap_hits_can_filter_on_season.sql.
    try_to_number(season.value:year::string) as season,
    -- Team nickname as OverTheCap writes it ("Patriots"), not the abbreviation.
    nullif(season.value:team::string, '') as team_name,
    season.value:cap_number::float as cap_number,
    season.value:cap_percent::float as cap_percent,
    season.value:base_salary::float as base_salary,
    season.value:prorated_bonus::float as prorated_bonus,
    season.value:guaranteed_salary::float as guaranteed_salary,
    season.value:cash_paid::float as cash_paid
from players,
    lateral flatten(input => players.season_history) as season
-- Real seasons only. Each list also ends with a 'Total' row (the career sum: keeping it
-- would count every player's cap twice), and has entries with a null year or year '0'.
-- Future seasons stay: they're the cap charges already scheduled by current contracts.
where season.value:year::string regexp '[0-9]{4}'
