-- Real offensive plays only: passes (including sacks and scrambles) and runs, from scrimmage.
-- Drops kickoffs, punts, kicks, kneels, spikes, and no_play rows (penalties that wiped out a play).
--
-- Also drops two-point tries (about 120 a season). They're logged as pass or run, but they
-- aren't downs: an untimed, all-or-nothing snap from the 2 after a touchdown, so they don't
-- answer "how efficient is this offense, play by play?". Official passing stats leave them
-- out for the same reason. Counting them also gave teams that score more touchdowns more
-- of these snaps. Effect on qb_season_epa: a median change of 0.002 EPA per dropback, 0.018 at most.
select
    -- play_id is only unique within a game, so build one key for the whole table.
    game_id || '-' || cast(play_id as integer) as play_key,
    game_id,
    cast(play_id as integer) as play_id,
    season,
    cast(week as integer) as week,
    season_type,
    posteam,
    defteam,
    play_type,
    epa,
    -- nflverse stores flags as 1.0 / 0.0; integers make averages read as rates.
    cast(success as integer) as success,
    wp,
    cast(qb_dropback as integer) as qb_dropback,
    cast(qb_scramble as integer) as qb_scramble,
    -- passer / passer_id include scrambles; passer_player_name does not.
    passer_id,
    passer as passer_name
from {{ source('raw', 'pbp') }}
where play_type in ('pass', 'run')
    -- coalesce: a NULL flag means "not flagged", so keep the play rather than drop it.
    -- (Today the NULL rows are all non-plays like "END QUARTER 1", already removed above.)
    and coalesce(two_point_attempt, 0) = 0
