-- How often each team goes for it on fourth-and-short, and how often it works.
--
-- The definition (each filter is a choice; change one and the numbers mean something else):
--   * Regular season only, like the other marts.
--   * Fourth-and-2 or less. At fourth-and-long, kicking is almost always right, so including
--     it would measure field position more than decision-making.
--   * Win probability between 10% and 90% before the snap. Outside that, a trailing team
--     has to go for it and a leading team has no reason to, which isn't aggressiveness.
--   * The denominator is real decisions only (see stg_fourth_downs): penalties that wiped
--     out the play, kneels, and spikes are already excluded.
--
-- League-wide, this rate went from 26.8% in 2015 to 61.8% in 2025.
with short_yardage_decisions as (
    select *
    from {{ ref('stg_fourth_downs') }}
    where season_type = 'REG'
        and ydstogo <= 2
        and wp between 0.10 and 0.90
),

team_seasons as (
    select
        season,
        posteam as team,
        count(*) as fourth_downs,
        count_if(went_for_it) as went_for_it,
        sum(fourth_down_converted) as converted
    from short_yardage_decisions
    group by season, posteam
)

select
    team_seasons.team || '-' || team_seasons.season as team_season_key,
    team_seasons.season,
    team_seasons.team,
    teams.team_name,
    team_seasons.fourth_downs,
    team_seasons.went_for_it,
    round(100 * team_seasons.went_for_it / team_seasons.fourth_downs, 1) as go_pct,
    team_seasons.converted,
    -- nullif: a team that never went for it has no conversion rate (null), not a divide-by-zero.
    round(100 * team_seasons.converted / nullif(team_seasons.went_for_it, 0), 1) as conversion_pct
from team_seasons
left join {{ ref('stg_teams') }} as teams
    on team_seasons.team = teams.team_abbr
