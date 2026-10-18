-- Downstream models filter and group stg_cap_hits by season. Snowflake doesn't promise to
-- apply the model's WHERE (real years only) before casting year to a number, so a careless
-- cast fails on the 'Total' rows with "Failed to cast variant value". This query shape hit
-- that error every time before stg_cap_hits switched to try_to_number. Returns no rows.
select season, count(*) as player_seasons
from {{ ref('stg_cap_hits') }}
where season > 2031
group by season
having count(*) < 0
