-- cap_percent is a share of the cap, so it must be between 0 and 1. Checked from 2016 on, the
-- seasons the marts use. Before that the source has two impossible values (Sheldon Brown 2009:
-- cap_number 2,147.48, i.e. the largest 32-bit integer, and Albert Haynesworth 2006).
select player_season_key, cap_number, cap_percent
from {{ ref('stg_cap_hits') }}
where season >= 2016
    and (cap_percent < 0 or cap_percent > 1)
