-- From stg_cap_hits before the fix (commit d050bd0's first draft): this line failed with
-- "Failed to cast variant value "Total" to FIXED" when a query grouped by season.
select
    players.otc_id,
    season.value:year::int as season,
    season.value:cap_number::float as cap_number
from players,
    lateral flatten(input => players.season_history) as season
where season.value:year::string regexp '[0-9]{4}'
