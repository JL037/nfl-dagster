select
    team_abbr,
    team_name,
    -- Nickname ("Patriots"): how OverTheCap names teams in stg_cap_hits.
    team_nick,
    team_conf,
    team_division,
    team_color
from {{ source('raw', 'teams') }}
