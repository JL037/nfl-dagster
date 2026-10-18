-- Which QBs produced the most for their share of the salary cap? One row per QB season
-- (every row of qb_season_epa), with that season's cap hit and a value score.
--
-- Definitions, measured on the 393 finished QB seasons (2015-2025) with a usable cap hit:
--
-- cap_share = cap_number / that season's league salary cap (seed league_salary_caps).
--   The same denominator for every team. OverTheCap's cap_percent divides by each team's
--   adjusted cap and is rounded to 0.1%, so a 0.6% and a 0.64% rookie look the same.
--
-- expected_epa_per_dropback: a straight line through those finished seasons, EPA per
--   dropback against cap_share, i.e. what QBs paid this share of the cap usually produce.
--   Spending does buy performance, but weakly: correlation 0.29, and each 1% of the cap is
--   worth about +0.007 EPA per dropback (QBs under 5% of the cap average 0.015; over 15%, 0.117).
--
-- epa_over_expected = epa_per_dropback - expected_epa_per_dropback.
-- worth_it = epa_over_expected > 0: he played better than QBs paid the same usually play.
--   Top seasons: Lamar Jackson 2019 (+0.36) and Patrick Mahomes 2018 (+0.35), both MVPs on
--   rookie deals; Brock Purdy 2023; Drake Maye 2025 (+0.30).
--   Rejected: EPA / cap share. It ranks any cheap QB at the top (Nick Mullens 2018, 0.107
--   EPA per dropback, ranked 3rd), is undefined at a $0 cap hit, and runs backwards when
--   EPA is negative.
--
-- Which seasons get a score:
-- - The line is fitted on finished seasons only, then applied to every season, so the
--   season in progress is scored against a fixed yardstick. Treat in-progress scores as
--   estimates: after 5 weeks, a QB's EPA per dropback is typically 0.11 off his final number
--   (correlation 0.60 with the full season; it's 0.85 by week 11). Still, 5 weeks of a season
--   predict that season better than his whole previous season does (0.39).
-- - OverTheCap keeps one team per season: where the player ended up, with that team's cap
--   hit. For a QB released or traded mid-season, that isn't what the team that played him
--   paid (Daniel Jones 2024: 381 dropbacks for the Giants, cap hit $0 with the Vikings). Those
--   rows (5 of 398 finished-season rows) keep their cap hit but get no score.
-- - A QB with no cap row keeps his row, with nulls: Dwayne Haskins 2019-2020, and Jalon
--   Daniels 2026 (new contract; OverTheCap hasn't filled in its season history yet).
with qb_seasons as (
    select
        qb.*,
        cap_hits.cap_number,
        cap_hits.team_name as cap_team_name,
        cap_hits.cap_number / caps.salary_cap_millions as cap_share,
        -- OverTheCap still uses Washington's older names for older seasons.
        teams.team_nick = case
            when cap_hits.team_name in ('Redskins', 'Washington') then 'Commanders'
            else cap_hits.team_name
        end as is_cap_hit_for_team
    from {{ ref('qb_season_epa') }} as qb
    left join {{ ref('stg_cap_hits') }} as cap_hits
        on cap_hits.gsis_id = qb.passer_id
        and cap_hits.season = qb.season
    left join {{ ref('league_salary_caps') }} as caps
        on caps.season = qb.season
    left join {{ ref('stg_teams') }} as teams
        on teams.team_abbr = qb.team
),

scored as (
    select *
    from qb_seasons
    where is_cap_hit_for_team
        and cap_share is not null
),

fit as (
    select
        regr_slope(epa_per_dropback, cap_share) as slope,
        regr_intercept(epa_per_dropback, cap_share) as intercept
    from scored
    where is_season_complete
),

expected as (
    select
        scored.qb_season_key,
        fit.intercept + fit.slope * scored.cap_share as expected_epa_per_dropback
    from scored
    cross join fit
)

select
    qb_seasons.qb_season_key,
    qb_seasons.season,
    qb_seasons.passer_id,
    qb_seasons.passer_name,
    qb_seasons.team,
    qb_seasons.dropbacks,
    qb_seasons.epa_per_dropback,
    qb_seasons.is_season_complete,
    qb_seasons.cap_number,
    qb_seasons.cap_share,
    coalesce(qb_seasons.is_cap_hit_for_team, false) as is_cap_hit_for_team,
    expected.expected_epa_per_dropback,
    qb_seasons.epa_per_dropback - expected.expected_epa_per_dropback as epa_over_expected,
    qb_seasons.epa_per_dropback > expected.expected_epa_per_dropback as worth_it
from qb_seasons
left join expected using (qb_season_key)
