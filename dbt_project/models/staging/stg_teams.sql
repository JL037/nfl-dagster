select
    team_abbr,
    team_name,
    team_conf,
    team_division,
    team_color
from {{ source('raw', 'teams') }}
