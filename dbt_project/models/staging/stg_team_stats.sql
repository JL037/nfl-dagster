-- Box-score stats, one row per team, week and season type (REG, POST), from nflverse's weekly
-- team stats. One 1999 row has no team (a fragment: 1 pass, 2 runs), so it's left out.
select
    team || '-' || season || '-' || week || '-' || season_type as team_week_key,
    season,
    week,
    season_type,
    game_id,
    team,
    opponent_team,
    completions,
    attempts,
    passing_yards,
    passing_tds,
    passing_interceptions,
    sacks_suffered,
    carries,
    rushing_yards,
    rushing_tds,
    fumbles_lost_total as fumbles_lost,
    def_sacks,
    def_interceptions,
    def_fumbles_forced,
    def_tds,
    penalties,
    penalty_yards,
    fg_made,
    fg_att
from {{ source('raw', 'team_stats') }}
where team is not null
