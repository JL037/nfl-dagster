-- A singular dbt test: it passes when this query returns no rows.
-- Every team-season must have sensible counts: at least one decision, no more attempts than
-- decisions, no more conversions than attempts, and percentages between 0 and 100.
select *
from {{ ref('team_fourth_down') }}
where fourth_downs < 1
    or went_for_it > fourth_downs
    or converted > went_for_it
    or go_pct not between 0 and 100
    or conversion_pct not between 0 and 100
