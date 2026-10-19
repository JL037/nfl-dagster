# Ask page evaluation: structured answers on Claude Haiku 5.5 (2026-10-19)

What changed since [the 2026-10-18 report](2026-10-18-haiku-vs-glm-5.3-flash.md): answers are now a
headline, an explanation and an optional chart (the `answer` tool); names come from
`passer_full_name` (nflverse players); `game_results_vs_spread` is filtered to the regular season
unless the question says playoffs or "all games"; the data's own category words (`home`, `away`,
`push`, `REG`, `WC`, `DIV`, `CON`, `SB`) may be typed into the SQL; and an answer with an
unchecked number, or given before any successful query, gets one retry. Two golden questions
were added (`full_name_best_epa_2024`, `ats_regular_season_2024`). Run on the dev serving
database, three runs, Haiku only.

## Summary

1. **Accuracy went up on the same questions:** the 15 answerable questions from 2026-10-18 pass
   42/45 (93%), up from 39/45 (87%). Out of scope stays 30/30: every question we can't answer
   still gets the "we don't have the data" reply.
2. **The two new questions pass 6/6:** full names exactly as nflverse spells them, and the
   regular-season ATS count.
3. **Fuller answers cost more:** $0.00045 per question (was $0.00032), 4.1 s on average (was 3.1 s).
   About $0.45 per 1,000 questions.
4. **What still misses (3 of 81):**
   - `home_cover_share` 1/3: the share depends on whether pushes count in the total (47.7% with,
     48.7% without); the answers say which they used. A genuinely ambiguous question.
   - `league_go_rate_2025` 2/3: one answer quoted "90" from the mart's definition ("win
     probability 10-90%"), which the number check blocks by rule. A false alarm, kept: the rule
     stays strict.
5. **Seen in the first run today and fixed before this one:** queries rejected for typing
   `'home'` into the SQL (every query in one answer), and "all games" read as regular season only.

## Results by run

| Run | Model | In scope | Out of scope | Overall | Cost / question | Run cost | Avg time | Median time | Slowest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261019-124734 | Claude Haiku 5.5 | 16/17 (94%) | 10/10 (100%) | 26/27 (96%) | $0.00045 | $0.0123 | 4.0 s | 3.6 s | 9.5 s |
| 20261019-124931 | Claude Haiku 5.5 | 16/17 (94%) | 10/10 (100%) | 26/27 (96%) | $0.00045 | $0.0122 | 4.2 s | 4.1 s | 10.3 s |
| 20261019-125126 | Claude Haiku 5.5 | 16/17 (94%) | 10/10 (100%) | 26/27 (96%) | $0.00045 | $0.0122 | 4.1 s | 4.2 s | 8.9 s |

## All runs combined

| Model | In scope | Out of scope | Overall | Cost / question | Total cost | Avg time | Median time | Slowest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | 48/51 (94%) | 30/30 (100%) | 78/81 (96%) | $0.00045 | $0.0367 | 4.1 s | 4.1 s | 10.3 s |

## Question by question

| Question | Expected | Claude Haiku 5.5 passed | Claude Haiku 5.5 avg time |
| --- | --- | --- | --- |
| Which quarterback was the best value for his share of the salary cap in 2025? | answer | 3/3 | 4.4 s |
| How far above expected for his cap share was Drake Maye's EPA per dropback in 2025? | answer | 3/3 | 4.0 s |
| Was Dak Prescott worth his contract in 2025? | answer | 3/3 | 4.6 s |
| Which quarterback had the biggest cap hit as a share of the salary cap in 2025? | answer | 3/3 | 3.5 s |
| What share of the salary cap was Jordan Love's cap hit in 2025? | answer | 3/3 | 2.7 s |
| How many quarterbacks were worth their contract in 2025? | answer | 3/3 | 4.5 s |
| How far above expected for his cap share was Patrick Mahomes in 2018? | answer | 3/3 | 7.1 s |
| Which quarterback had the highest EPA per dropback in 2025? | answer | 3/3 | 4.8 s |
| What was Josh Allen's EPA per dropback in 2024? | answer | 3/3 | 3.8 s |
| Which team had the best net EPA per play in 2025? | answer | 3/3 | 4.4 s |
| Which team had the best defense by EPA allowed per play in 2025? | answer | 3/3 | 4.7 s |
| Which team went for it most often on fourth-and-short in 2025? | answer | 3/3 | 6.7 s |
| How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | answer | 2/3 ⚠️ | 9.6 s |
| Across all games since 2015 that had a spread, how often did the home team cover? | answer | 1/3 ⚠️ | 7.8 s |
| Who has been the best value quarterback for his cap share so far in 2026? | answer | 3/3 | 5.3 s |
| How many touchdowns did Patrick Mahomes throw in 2024? | no data | 3/3 | 1.4 s |
| Who will win the Super Bowl this season? | no data | 3/3 | 2.4 s |
| Which college quarterback was the best value in 2025? | no data | 3/3 | 1.6 s |
| Which quarterback missed the most games to injury in 2025? | no data | 3/3 | 1.5 s |
| What was Tom Brady's cap share in 2005? | no data | 3/3 | 2.3 s |
| What is the over/under for the Chiefs' next game? | no data | 3/3 | 2.0 s |
| Who was the best value wide receiver in 2025? | no data | 3/3 | 1.8 s |
| How good a value was Johnny Fakeplayer in 2025? | no data | 3/3 | 3.2 s |
| What was the weather in Buffalo for their last home game? | no data | 3/3 | 2.0 s |
| What will Drake Maye's cap hit be in 2030? | no data | 3/3 | 2.4 s |
| Who had the highest EPA per dropback in 2024? Give his full name. | answer | 3/3 | 6.0 s |
| Which team covered the spread most often in 2024, and how many times? | answer | 3/3 | 6.2 s |

## Every question, every response

### 1. Which quarterback was the best value for his share of the salary cap in 2025?

*`best_value_2025`. Expected: names **D.Maye**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 4.4 s, $0.00115, 1 query
  > Drake Maye was the best value for his share of the salary cap in 2025, beating his expected EPA per dropback by +0.30. Maye's 2025 EPA per dropback was 0.316 on a cap share of 3.0%, where QBs usually produce about 0.021, giving him +0.295 over expected. Brock Purdy (+0.183) and Jordan Love (+0.182) were next, and all 2025 seasons are finished. Several QBs with large cap hits, such as Joe Burrow (-0.028), fell below expectation.
  - `SELECT passer_full_name, team, season, dropbacks, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 25`
- Run `20261019-124931`: ✅ PASS, 4.1 s, $0.00052, 1 query
  > Drake Maye was the best value for his cap share in 2025, beating expected EPA per dropback by +0.295. Maye posted 0.316 EPA per dropback on an $8.3M cap hit (2.98% of the cap), where QBs at that share usually produce about 0.021. Brock Purdy (+0.183) and Jordan Love (+0.182, on a $29.7M hit at 10.6% of the cap) follow. The 2025 season is complete, so these numbers are final.
  - `SELECT passer_full_name, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = %s AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 10` params `[2025]`
- Run `20261019-125126`: ✅ PASS, 4.7 s, $0.00059, 1 query
  > Drake Maye was the best value for his share of the salary cap in 2025, beating expectations by +0.30 EPA per dropback. Maye (NE) had a 2025 cap hit of about $8.3M, which is 3.0% of the league cap, and posted 0.316 EPA per dropback against the 0.021 that QBs at that cap share usually produce. Brock Purdy (+0.18) and Jordan Love (+0.18) were next. The 2025 season is complete, so these figures are final, not estimates.</explanation>
<parameter name="chart">{"kind": "bar", "query": 1, "x": "passer_full_name", "y": "epa_over_expected", "series": null, "title": "2025 QB EPA over expected, top 10 (cap-share adjusted)"}
  - `SELECT passer_full_name, team, cap_number, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL AND is_cap_hit_for_team ORDER BY epa_over_expected DESC LIMIT 10`

### 2. How far above expected for his cap share was Drake Maye's EPA per dropback in 2025?

*`maye_over_expected_2025`. Expected: states **+0.295** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 4.1 s, $0.00039, 1 query
  > Drake Maye's 2025 EPA per dropback was 0.30 above what his cap share usually produces. Maye posted 0.316 EPA per dropback on a cap share of about 3.0%, where QBs paid that share average 0.021, a gap of +0.295. The 2025 season is complete, and his cap hit is with the team he played for (NE), so the score is final.
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Drake Maye']`
- Run `20261019-124931`: ✅ PASS, 3.7 s, $0.00040, 1 query
  > Drake Maye's 2025 EPA per dropback was 0.30 above what a QB with his cap share typically produces. Maye posted 0.316 EPA per dropback on a cap share of 3.0%, where the fitted line expects about 0.021, so he finished 0.295 above expected. The 2025 season is complete and his cap hit is for the team that played him (NE).
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Drake Maye']`
- Run `20261019-125126`: ✅ PASS, 4.3 s, $0.00039, 1 query
  > Drake Maye's 2025 EPA per dropback was 0.295 above what his 3.0% cap share usually produces. Maye (NE) posted 0.316 EPA per dropback in 2025, against an expected 0.021 for a cap share of 2.98% of the league cap, so he was 0.295 above expectation. The season is complete, and his cap hit is with the team he played for, so the score is valid.
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Drake Maye']`

### 3. Was Dak Prescott worth his contract in 2025?

*`prescott_worth_it_2025`. Expected: states **+0.038** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 3.6 s, $0.00040, 1 query
  > Yes: Dak Prescott was worth his contract in 2025, beating the EPA expected for his cap share by 0.038 per dropback. In 2025 Prescott (DAL) posted 0.169 EPA per dropback over 654 dropbacks, on a $50.5M cap hit that is 18.1% of the league cap. QBs paying that share usually produce about 0.132, so he came in 0.038 above expectation. The 2025 season is complete, so these are final numbers.
  - `SELECT season, passer_full_name, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_season_complete, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it FROM qb_contract_value WHERE passer_full_name = %s AND season = %s` params `['Dak Prescott', 2025]`
- Run `20261019-124931`: ✅ PASS, 4.2 s, $0.00040, 1 query
  > Yes: Dak Prescott's 2025 season (EPA +0.17 per dropback) beat what a QB paying his cap share usually produces, by +0.04. Prescott played 654 dropbacks for Dallas in 2025 at 0.169 EPA per dropback. His $50.5M cap hit was 18.1% of the league cap, where QBs typically produce about 0.132 EPA per dropback, so he came in 0.038 above expectation. The season is finished, so these numbers are final.
  - `SELECT season, passer_full_name, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = %s` params `['Dak Prescott', 2025]`
- Run `20261019-125126`: ✅ PASS, 5.9 s, $0.00076, 3 queries
  > Yes, narrowly: Dak Prescott was worth his 2025 contract, beating the line for his cap share by 0.04 EPA per dropback. Prescott posted 0.169 EPA per dropback over 654 dropbacks with the Cowboys, against 0.132 expected for a QB whose $50.5M cap hit was 18.1% of the league cap. That gives an over-expected figure of +0.038, so he rates as worth it. The season is complete, so these are final numbers.
  - `SELECT passer_full_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Dak Prescott', 2025]`
  - `SELECT passer_full_name, season, team, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_full_name = %s AND season = 2025` params `['Dak Prescott', 2025]`
  - `SELECT passer_full_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Dak Prescott']`

### 4. Which quarterback had the biggest cap hit as a share of the salary cap in 2025?

*`highest_cap_share_2025`. Expected: names **D.Prescott**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 3.5 s, $0.00045, 1 query
  > Dak Prescott had the biggest 2025 cap hit as a share of the salary cap, at 18.1% ($50.5M). Among 2025 QB seasons with a cap hit, Prescott (DAL) ranked first, ahead of Matthew Stafford (17.0%) and Joe Burrow (16.5%). The 2025 season is complete, and his cap hit is counted for the team that played him.
  - `SELECT passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2025 AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 10`
- Run `20261019-124931`: ✅ PASS, 3.4 s, $0.00045, 1 query
  > Dak Prescott had the biggest 2025 cap hit as a share of the salary cap, at 18.1% ($50.5M). Prescott's cap hit was 18.1% of the league cap, ahead of Matthew Stafford (17.0%) and Joe Burrow (16.5%). His 2025 season is finished, and he beat the EPA per dropback expected for his cap share by +0.038, so he counts as worth it. Cap share is the cap number divided by that season's league salary cap.
  - `SELECT passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete, epa_per_dropback, epa_over_expected, worth_it FROM qb_contract_value WHERE season = 2025 AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 10`
- Run `20261019-125126`: ✅ PASS, 3.5 s, $0.00042, 1 query
  > Dak Prescott had the biggest 2025 cap hit as a share of the salary cap, at 18.1% ($50.5M). Prescott's cap number of $50.52M was 18.1% of the league salary cap, ahead of Matthew Stafford (17.0%) and Joe Burrow (16.5%). The 2025 season is complete, so these figures are final.
  - `SELECT passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete, epa_per_dropback, epa_over_expected FROM qb_contract_value WHERE season = 2025 AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 5`

### 5. What share of the salary cap was Jordan Love's cap hit in 2025?

*`love_cap_share_2025`. Expected: states **10.6%** (at least 1 decimal).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.5 s, $0.00031, 1 query
  > Jordan Love's 2025 cap hit was about 10.6% of the salary cap. His 2025 cap number with the Green Bay Packers was $29.72 million, which is a cap_share of 0.106 (10.6%) of that season's league salary cap. The season is complete and the cap hit is for the team he played for.
  - `SELECT season, passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Jordan Love']`
- Run `20261019-124931`: ✅ PASS, 3.0 s, $0.00031, 1 query
  > Jordan Love's 2025 cap hit was about 10.6% of the salary cap. His cap number for the Green Bay Packers in 2025 was $29.7 million, a cap share of 0.106 (10.6%) of that season's league salary cap. The 2025 season is complete, and the cap hit is for the team he played for all season.
  - `SELECT season, passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Jordan Love']`
- Run `20261019-125126`: ✅ PASS, 2.7 s, $0.00031, 1 query
  > Jordan Love's 2025 cap hit was about 10.6% of the salary cap. His cap number for Green Bay in 2025 was $29.72 million, which is a cap_share of 0.106 (10.6%) of that season's league salary cap. The 2025 season is complete and his cap hit was for the team he played for all season.
  - `SELECT season, passer_full_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Jordan Love']`

### 6. How many quarterbacks were worth their contract in 2025?

*`worth_it_count_2025`. Expected: states **19**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 5.2 s, $0.00070, 2 queries
  > 19 of the 38 quarterbacks with a scored 2025 season were worth their contract, performing above what their cap share usually produces. The 2025 season is complete, so these figures are final. "Worth it" means epa_over_expected > 0: EPA per dropback above the level QBs at the same share of the salary cap typically reach. Drake Maye (NE, +0.30) ranked highest, and Shedeur Sanders (CLE, -0.24) lowest.
  - `SELECT season, is_season_complete, COUNT(*) FILTER (WHERE worth_it) AS worth_it_qbs, COUNT(*) FILTER (WHERE worth_it IS NOT NULL) AS scored_qbs, COUNT(*) AS total_qb_rows FROM qb_contract_value WHERE season = %s GROUP BY season, is_season_complete` params `[2025]`
  - `SELECT passer_full_name, team, epa_over_expected FROM qb_contract_value WHERE season = %s AND worth_it IS NOT NULL ORDER BY epa_over_expected DESC` params `[2025]`
- Run `20261019-124931`: ✅ PASS, 4.2 s, $0.00063, 2 queries
  > 19 of the 38 scored quarterbacks in 2025 were worth their contract, by the cap-adjusted EPA measure. Worth it means a QB's EPA per dropback beat the level QBs paying that share of the salary cap usually produce. The 2025 season is complete, so these are final numbers. Drake Maye led with +0.30 over expected, followed by Brock Purdy (+0.18) and Jordan Love (+0.18).
  - `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(*) FILTER (WHERE worth_it IS NOT NULL) AS scored_qbs, COUNT(*) AS total_qb_rows, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = %s` params `[2025]`
  - `SELECT passer_full_name, team, epa_over_expected, cap_share, worth_it, is_season_complete FROM qb_contract_value WHERE season = %s AND worth_it IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 25` params `[2025]`
- Run `20261019-125126`: ✅ PASS, 4.2 s, $0.00064, 2 queries
  > 19 of the 38 scored quarterbacks in 2025 were worth their contract, beating the EPA per dropback their cap share usually produces. Of 38 QB seasons with a usable cap hit in 2025, 19 had a positive epa_over_expected, and the 2025 season is complete. Drake Maye (+0.30) had the largest surplus, followed by Brock Purdy and Jordan Love. Mid-season moves without a team cap hit are not scored, so they are not counted.
  - `SELECT COUNT(*) AS scored_qbs, SUM(CASE WHEN worth_it THEN 1 ELSE 0 END) AS worth_it_qbs, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = 2025 AND worth_it IS NOT NULL`
  - `SELECT passer_full_name, team, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected FROM qb_contract_value WHERE season = 2025 AND worth_it = true ORDER BY epa_over_expected DESC`

### 7. How far above expected for his cap share was Patrick Mahomes in 2018?

*`mahomes_2018`. Expected: states **+0.345** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 6.1 s, $0.00058, 2 queries
  > Patrick Mahomes in 2018 finished 0.34 EPA per dropback above what a QB with his cap share usually produces. His 2018 EPA per dropback was 0.360 on a cap share of 2.1%, where the expected figure is 0.015, giving an epa_over_expected of +0.345. The season is finished and his cap hit was for the team that played him (KC), so the score is final.
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes', 2018]`
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes']`
- Run `20261019-124931`: ✅ PASS, 8.4 s, $0.00087, 2 queries
  > Patrick Mahomes in 2018 ran about 0.34 EPA per dropback above what QBs at his cap share usually produce. His 2018 EPA per dropback was 0.360 on a cap share of 2.1%, where the fitted line expects 0.015, so epa_over_expected is +0.345. This is a finished season, and his cap hit was for the team he played for, so the score is valid.
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes', 2018]`
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes']`
- Run `20261019-125126`: ✅ PASS, 6.8 s, $0.00060, 2 queries
  > Patrick Mahomes was about 0.34 EPA per dropback above expected for his cap share in 2018. His 2018 EPA per dropback was 0.360 on a cap share of 2.1%, where QBs paid that share usually produce about 0.015, so he beat expectation by 0.345. The season is finished and his cap hit was for the team he played for, so the score is valid.
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes', 2018]`
  - `SELECT passer_full_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_full_name = %s AND season = 2018` params `['Patrick Mahomes']`

### 8. Which quarterback had the highest EPA per dropback in 2025?

*`best_epa_2025`. Expected: names **D.Maye**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 4.8 s, $0.00042, 1 query
  > Drake Maye had the highest EPA per dropback in 2025, at 0.316 across 601 dropbacks for New England. Among 2025 quarterbacks in qb_season_epa, Maye led the league, ahead of Jordan Love (0.259) and Matthew Stafford (0.223). The 2025 season is marked complete, so these figures are final.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2025 ORDER BY epa_per_dropback DESC LIMIT 10`
- Run `20261019-124931`: ✅ PASS, 5.3 s, $0.00043, 1 query
  > Drake Maye had the highest EPA per dropback in 2025, at 0.32 across 601 dropbacks for New England. Maye's 0.316 EPA per dropback led all quarterbacks with a 2025 season row, ahead of Jordan Love (0.259) and Matthew Stafford (0.223). The 2025 season is complete, so these figures are final.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2025 ORDER BY epa_per_dropback DESC LIMIT 10`
- Run `20261019-125126`: ✅ PASS, 4.2 s, $0.00043, 1 query
  > Drake Maye had the highest EPA per dropback in 2025, at 0.316 across 601 dropbacks for NE. Among 2025 QB seasons in qb_season_epa, Maye ranked first, ahead of Jordan Love (0.259) and Matthew Stafford (0.223). The 2025 season is complete, so these numbers are final.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, is_season_complete, season_progress FROM qb_season_epa WHERE season = 2025 ORDER BY epa_per_dropback DESC NULLS LAST LIMIT 10`

### 9. What was Josh Allen's EPA per dropback in 2024?

*`allen_epa_2024`. Expected: states **+0.304** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 3.3 s, $0.00029, 1 query
  > Josh Allen posted 0.30 EPA per dropback in 2024 with the Bills. Across 539 dropbacks in the completed 2024 regular season, Allen's EPA per dropback was 0.304. This is a finished season, so the figure is not an estimate.
  - `SELECT passer_full_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_full_name = %s AND season = 2024` params `['Josh Allen']`
- Run `20261019-124931`: ✅ PASS, 4.5 s, $0.00034, 1 query
  > Josh Allen posted 0.304 EPA per dropback in 2024 with the Buffalo Bills. Across 539 dropbacks in the 2024 regular season (a finished season), Allen's EPA per dropback was 0.304. This is a single player-season, so no chart is shown.
  - `SELECT passer_full_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_full_name = %s AND season = 2024` params `['Josh Allen']`
- Run `20261019-125126`: ✅ PASS, 3.5 s, $0.00031, 1 query
  > Josh Allen's EPA per dropback in 2024 was 0.30 across 539 dropbacks with the Buffalo Bills. The 2024 season is complete, so this is a final number rather than an estimate. The figure covers regular-season dropbacks (passes, sacks, and scrambles) only.
  - `SELECT passer_full_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_full_name = %s AND season = 2024` params `['Josh Allen']`

### 10. Which team had the best net EPA per play in 2025?

*`best_net_2025`. Expected: names **LA** (Los Angeles Rams).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 4.3 s, $0.00043, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at +0.207. The Rams' offense gained 0.145 EPA per play and their defense allowed -0.062, giving net 0.207. The New England Patriots were close behind at 0.203, and the Buffalo Bills third at 0.156. These are regular-season figures only.
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 10`
- Run `20261019-124931`: ✅ PASS, 4.1 s, $0.00038, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at +0.207. The Rams' offense gained 0.145 EPA per play and their defense allowed -0.062, giving a net of 0.207. The New England Patriots were close behind at 0.203, and the Buffalo Bills third at 0.156. These are regular-season figures only.
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 10`
- Run `20261019-125126`: ✅ PASS, 4.7 s, $0.00044, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at +0.207. The Rams' offense (+0.145 EPA per play) and defense (-0.062, where lower is better) combined for the top net figure, just ahead of the New England Patriots at +0.203. Buffalo (+0.156) and Seattle (+0.147) follow. The team_season_epa table has no in-progress flag, so these are treated as full-season regular-season numbers.</explanation>
<parameter name="chart">{"kind": "bar", "query": 1, "x": "team", "y": "net_epa_per_play", "series": null, "title": "2025 net EPA per play, top 10 teams"}
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 10`

### 11. Which team had the best defense by EPA allowed per play in 2025?

*`best_defense_2025`. Expected: names **HOU** (Houston Texans).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 4.2 s, $0.00051, 2 queries
  > The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.131 per play. Houston allowed -0.131 EPA per play over 977 defensive plays, ahead of Seattle (-0.118) and Jacksonville (-0.104). The table doesn't flag whether 2025 is a finished season, so I can't confirm these are final numbers. The ranking uses regular-season plays only.
  - `SELECT team, team_name, def_epa_per_play, def_plays, def_success_rate FROM team_season_epa WHERE season = 2025 AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 10`
  - `SELECT published_at, source FROM _publications WHERE table_name = 'team_season_epa'`
- Run `20261019-124931`: ✅ PASS, 4.8 s, $0.00071, 3 queries
  > Houston Texans had the best defense in 2025, allowing -0.131 EPA per play, the lowest in the league. Houston's defense allowed -0.131 EPA per play over 977 plays with a 38.3% success rate. Seattle (-0.118) and Jacksonville (-0.104) were next. The 2025 season is complete, so these figures are final regular-season numbers.
  - `SELECT team, team_name, def_epa_per_play, def_plays, def_success_rate FROM team_season_epa WHERE season = 2025 AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 10`
  - `SELECT season, is_season_complete FROM _publications LIMIT 0`
  - `SELECT DISTINCT season, is_season_complete FROM qb_season_epa WHERE season = 2025`
- Run `20261019-125126`: ✅ PASS, 5.1 s, $0.00077, 2 queries
  > The Houston Texans had the best defense in 2025, allowing -0.131 EPA per play, the lowest in the league. Houston's defense allowed -0.131 EPA per play over 977 plays, with a 38.3% defensive success rate. Seattle (-0.118) and Jacksonville (-0.104) were next. The 2025 season is complete in the data.
  - `SELECT team, team_name, def_epa_per_play, def_plays, def_success_rate FROM team_season_epa WHERE season = 2025 AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 10`
  - `SELECT season, is_season_complete FROM qb_season_epa WHERE season = 2025 LIMIT 1`

### 12. Which team went for it most often on fourth-and-short in 2025?

*`go_for_it_leader_2025`. Expected: names **IND** (Indianapolis Colts).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 7.1 s, $0.00074, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% (16 of 19 decisions). Ranked by go-for-it rate on fourth-and-2 or less in competitive game states, the Colts led, followed by the Buffalo Bills (82.4%) and Dallas Cowboys (76.5%). Teams with few decisions, like the Colts' 19, can swing a rate quickly.
  - `SELECT team, team_name, fourth_downs, went_for_it, go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC NULLS LAST, went_for_it DESC LIMIT 10` params `[2025]`
- Run `20261019-124931`: ✅ PASS, 6.3 s, $0.00066, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% (16 of 19 decisions). Rate is the share of fourth-and-2-or-less decisions in competitive game states where the team went for it. Buffalo was next at 82.4%, followed by Dallas at 76.5%.
  - `SELECT team, team_name, go_pct, went_for_it, fourth_downs FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC NULLS LAST LIMIT 10` params `[2025]`
- Run `20261019-125126`: ✅ PASS, 6.7 s, $0.00070, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% of decisions (16 of 19). This is the go-for-it rate on fourth-and-short decisions in competitive game states, regular season only. The Buffalo Bills were next at 82.4% (14 of 17), then the Dallas Cowboys at 76.5%.
  - `SELECT team, team_name, go_pct, went_for_it, fourth_downs FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC NULLS LAST LIMIT 10` params `[2025]`

### 13. How often did NFL teams go for it on fourth-and-short in competitive games in 2025?

*`league_go_rate_2025`. Expected: states **61.8%** (at least 1 decimal).*

**Claude Haiku 5.5**: 2/3 runs passed

- Run `20261019-124734`: ❌ FAIL (no answer), 9.5 s, $0.00132, 2 queries, reason: numbers not in any result: 90
  > We don't have the data to give an accurate answer to that.
  - `SELECT team, go_pct, conversion_pct, fourth_downs, went_for_it, SUM(went_for_it) OVER () AS league_went, SUM(fourth_downs) OVER () AS league_downs, ROUND(100.0 * SUM(went_for_it) OVER () / NULLIF(SUM(fourth_downs) OVER (), 0), 1) AS league_go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC` params `[2025]`
  - `SELECT season, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS league_go_pct FROM team_fourth_down WHERE season IN (%s, %s) GROUP BY season ORDER BY season` params `[2015, 2025]`
- Run `20261019-124931`: ✅ PASS, 10.3 s, $0.00147, 3 queries
  > In 2025, NFL teams went for it on 61.8% of competitive fourth-and-short decisions, up from 26.8% in 2015. Across the league, teams went for it 352 times on 570 fourth-and-2-or-less decisions in competitive win-probability states. Team rates ranged from 84.2% (IND) down to 38.9% (LAC), with IND, BUF and DAL highest and LAC, MIN and DEN lowest. Per-team samples are small (often 10 to 25 decisions), so individual rates are noisy.
  - `SELECT 'LEAGUE' AS team, SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS go_pct FROM team_fourth_down WHERE season = 2025 UNION ALL SELECT team, went_for_it, fourth_downs, go_pct FROM team_fourth_down WHERE season = 2025 ORDER BY go_pct DESC NULLS LAST`
  - `SELECT season, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS go_pct FROM team_fourth_down WHERE season IN (2015, 2025) GROUP BY season ORDER BY season`
  - `SELECT %s AS team, SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS go_pct FROM team_fourth_down WHERE season = 2025 UNION ALL SELECT team, went_for_it, fourth_downs, go_pct FROM team_fourth_down WHERE season = 2025 ORDER BY go_pct DESC NULLS LAST` params `['LEAGUE']`
- Run `20261019-125126`: ✅ PASS, 8.9 s, $0.00109, 2 queries
  > In 2025, NFL teams went for it on 61.8% of competitive fourth-and-short decisions (352 of 570). Across all teams, 352 of 570 fourth-and-2-or-less decisions in competitive game states were go-for-it attempts. Team rates ranged from 84.2% (IND) and 82.4% (BUF) at the top to 38.9% (LAC) and 40.9% (MIN) at the bottom. The team table does not flag season completeness, so treat these as the season's recorded figures.
  - `SELECT season, SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / SUM(fourth_downs), 1) AS league_go_pct FROM team_fourth_down WHERE season = %s GROUP BY season` params `[2025]`
  - `SELECT team, go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC` params `[2025]`

### 14. Across all games since 2015 that had a spread, how often did the home team cover?

*`home_cover_share`. Expected: states **47.7%** (at least 1 decimal).*

**Claude Haiku 5.5**: 1/3 runs passed

- Run `20261019-124734`: ✅ PASS, 8.8 s, $0.00122, 2 queries
  > Since 2015, the home team covered in 47.7% of games that had a spread (1,482 of 3,107). Across all 3,107 games with a spread from 2015 onward (including playoffs), the home team covered 1,482 times, and 81 games were pushes, which are excluded from the denominator. Regular season alone gives 47.4% (1,411 of 2,974), so playoffs barely move the figure. Both are computed from the game results table.
  - `SELECT COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 2) AS home_cover_pct_all, COUNT(*) FILTER (WHERE ats_result IS NOT NULL AND game_type = 'REG') AS reg_games_with_spread, COUNT(*) FILTER (WHERE ats_result = 'home' AND game_type = 'REG') AS reg_home_covers, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home' AND game_type = 'REG') / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL AND game_type = 'REG'), 0), 2) AS home_cover_pct_reg FROM game_results_vs_spread WHERE season >= %s""` params `[2015]`
  - `SELECT COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 2) AS home_cover_pct_all, COUNT(*) FILTER (WHERE ats_result IS NOT NULL AND game_type = 'REG') AS reg_games_with_spread, COUNT(*) FILTER (WHERE ats_result = 'home' AND game_type = 'REG') AS reg_home_covers, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home' AND game_type = 'REG') / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL AND game_type = 'REG'), 0), 2) AS home_cover_pct_reg FROM game_results_vs_spread WHERE season >= %s` params `[2015]`
- Run `20261019-124931`: ❌ FAIL (pct), 6.6 s, $0.00084, 1 query
  > Since 2015, the home team covered the spread in 48.98% of games that had a spread (excluding pushes). Of 3,107 games with a spread from 2015 onward, the home team covered 1,482 times, the away team covered 1,544 times, and 81 were pushes. Pushes are excluded from the percentage. This includes playoff games, since the question asked about all games.
  - `SELECT COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'away') AS away_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_ats, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IN ('home','away')), 0), 2) AS home_cover_pct_excl_push FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL`
- Run `20261019-125126`: ❌ FAIL (pct), 7.9 s, $0.00114, 2 queries
  > Home teams covered the spread in 49.0% of games with a spread since 2015, slightly less than away teams. Of 3,107 games with a spread from 2015 onward (playoffs included), the home team covered 1,482 times and the away team covered 1,544 times, with 81 pushes. The 49.0% rate excludes pushes from the denominator.
  - `SELECT COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'away') AS away_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IN ('home', 'away')), 0), 1) AS home_cover_pct_excl_pushes FROM game_results_vs_spread WHERE season >= %s AND spread_line IS NOT NULL", "params": [2015]}` params `[2015]`
  - `SELECT COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'away') AS away_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IN ('home', 'away')), 0), 1) AS home_cover_pct_excl_pushes FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL`

### 15. Who has been the best value quarterback for his cap share so far in 2026?

*`best_value_2026_so_far`. Expected: names **B.Purdy**; says the season is still in progress.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 5.5 s, $0.00053, 1 query
  > Brock Purdy has been the best value QB for his cap share so far in 2026, at +0.36 EPA per dropback over expected. Purdy (SF) posted 0.413 EPA per dropback on a 7.9% cap share, where QBs paying that share usually produce 0.057, over 156 dropbacks. Lamar Jackson (+0.29) and Caleb Williams (+0.29) follow. The 2026 season is still in progress, so these scores are estimates that will move as games are played.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL AND is_cap_hit_for_team ORDER BY epa_over_expected DESC LIMIT 10`
- Run `20261019-124931`: ✅ PASS, 5.1 s, $0.00050, 1 query
  > So far in 2026, Brock Purdy (SF) is the best value QB for his cap share, at +0.36 EPA per dropback over expected. Purdy's EPA per dropback is 0.413 on a cap share of 7.9%, where QBs usually produce about 0.057, and he has 156 dropbacks. Lamar Jackson (BAL, +0.29) and Caleb Williams (CHI, +0.29) follow. The 2026 season is still in progress, so these scores are estimates that will move as games are played.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 10`
- Run `20261019-125126`: ✅ PASS, 5.4 s, $0.00049, 1 query
  > Brock Purdy leads 2026 value so far, with EPA per dropback 0.36 above what his 7.9% cap share usually produces. Ranked by epa_over_expected among 2026 QB rows with a score: Purdy (SF, +0.356), Lamar Jackson (BAL, +0.292), and Caleb Williams (CHI, +0.289) follow. The 2026 season is still in progress, so these scores are estimates and may shift as more games are played.
  - `SELECT passer_full_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 10`

### 16. How many touchdowns did Patrick Mahomes throw in 2024?

*`mahomes_touchdowns`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 1.3 s, $0.00016, 0 queries, reason: model: The tables cover QB efficiency per season (EPA per dropback, success rate, dropbacks, scrambles), QB cap hits, game results against the spread, team fourth-down decisions, and team EPA. None of them record touchdown passes, so Patrick Mahomes's 2024 touchdown count can't be found here.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 1.4 s, $0.00016, 0 queries, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, dropbacks, scrambles), contracts and cap share, game results against the spread, fourth-down decisions, and team EPA. None of them records touchdown passes, so Patrick Mahomes's 2024 touchdown count can't be answered from this data.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.4 s, $0.00015, 0 queries, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, dropbacks, scrambles), contract value, betting results, team EPA and fourth-down decisions. None of them records touchdown passes, so Patrick Mahomes' 2024 touchdown count can't be answered from this data.
  > We don't have the data to give an accurate answer to that.

### 17. Who will win the Super Bowl this season?

*`super_bowl_pick`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.2 s, $0.00016, 0 queries, reason: model: The tables cover past regular-season and playoff game results with betting spreads, QB efficiency and contract value, and team offense, defense and fourth-down decisions. They have no Super Bowl forecasts, no playoff bracket for the current season, and no way to predict who will win, so this question can't be answered from them.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 2.7 s, $0.00017, 0 queries, reason: model: The tables hold past and in-progress game results, betting spreads, QB efficiency, contract values, and team EPA and fourth-down stats. They contain no Super Bowl outcome for this season and no playoff forecasts, so they can't say who will win.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 2.3 s, $0.00016, 0 queries, reason: model: The tables hold past and in-progress regular-season results, betting spreads, QB efficiency, cap values, and fourth-down decisions. They contain no Super Bowl forecasts, playoff bracket, or odds for the current season, so they can't say who will win.
  > We don't have the data to give an accurate answer to that.

### 18. Which college quarterback was the best value in 2025?

*`college_qb`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.0 s, $0.00015, 0 queries, reason: model: These tables cover NFL quarterbacks, teams, and games only. They have no college football data, so I can't say which college quarterback was the best value in 2025. The closest available measure is qb_contract_value, which ranks NFL QBs by EPA over expected relative to cap share, but it doesn't include college players.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 1.4 s, $0.00012, 0 queries, reason: model: The tables cover NFL quarterbacks, teams, and games only. They have no college football data, so they can't identify a college quarterback or his value in 2025.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.4 s, $0.00012, 0 queries, reason: model: The tables cover NFL quarterbacks and teams only. They have no college football data, so I can't say which college quarterback was the best value in 2025.
  > We don't have the data to give an accurate answer to that.

### 19. Which quarterback missed the most games to injury in 2025?

*`injuries`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 1.3 s, $0.00012, 0 queries, reason: model: None of the tables record injuries or games missed. qb_season_epa and qb_contract_value have dropbacks and season progress, which show playing time but not why a QB was absent, so games missed to injury can't be determined.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 1.4 s, $0.00015, 0 queries, reason: model: None of the tables record injuries or games missed. qb_season_epa and qb_contract_value cover QB dropbacks, EPA, and cap figures per season, and the other tables cover game results against the spread, fourth-down decisions, and team EPA. Dropbacks can show partial seasons, but they don't say why a QB sat out.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.8 s, $0.00015, 0 queries, reason: model: None of the tables record injuries or games missed. qb_season_epa and qb_contract_value cover QB dropbacks, EPA, and cap figures per season, and game_results_vs_spread covers scores and spreads. A games-played or injury count isn't available, so I can't say who missed the most games in 2025.
  > We don't have the data to give an accurate answer to that.

### 20. What was Tom Brady's cap share in 2005?

*`brady_2005`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.0 s, $0.00019, 0 queries, reason: model: The QB contract and EPA tables cover finished seasons 2015-2025 only, so there is no cap share for Tom Brady in 2005.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 2.9 s, $0.00017, 0 queries, reason: model: The QB contract and cap tables (qb_contract_value, qb_season_epa) cover finished seasons from 2015-2025 only, and salary cap data is seeded for those seasons. There is no 2005 cap share for Tom Brady in these tables.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 2.1 s, $0.00016, 0 queries, reason: model: The QB contract and cap data cover seasons from 2015 through 2025 only. There is no cap share for Tom Brady in 2005, so this season is outside what the tables contain.
  > We don't have the data to give an accurate answer to that.

### 21. What is the over/under for the Chiefs' next game?

*`next_game_total`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 1.6 s, $0.00014, 0 queries, reason: model: The tables hold point spreads (spread_line, ats_result) but no over/under or game total line, and no upcoming schedule. So I can't give the Chiefs' next game's over/under.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 2.7 s, $0.00015, 0 queries, reason: model: The tables hold point spreads (spread_line) and final scores for played games, but no over/under (total points) lines, and no upcoming schedule. I can't give the over/under for the Chiefs' next game.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.7 s, $0.00014, 0 queries, reason: model: The tables hold point spreads (spread_line) and ATS results, but no over/under (total points) line, and no schedule of upcoming games, so the Chiefs' next game's over/under can't be found.
  > We don't have the data to give an accurate answer to that.

### 22. Who was the best value wide receiver in 2025?

*`wide_receiver`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 1.4 s, $0.00015, 0 queries, reason: model: The tables cover quarterbacks (QB contract value and QB season EPA), game results against the spread, fourth-down decisions, and team-level EPA. None has wide receiver stats or contract data, so the best-value wide receiver for 2025 can't be determined.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 2.0 s, $0.00019, 0 queries, reason: model: The tables cover quarterbacks (QB efficiency, QB cap hits and value scores), game ATS results, fourth-down decisions, and team EPA. None covers wide receivers, their salaries, or receiving performance, so "best value wide receiver in 2025" can't be answered from this data. The closest available measure is qb_contract_value, which ranks quarterbacks only.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.9 s, $0.00017, 0 queries, reason: model: The tables cover quarterbacks (QB EPA, QB cap hits, QB value scores), team efficiency, team fourth-down decisions, and game results against the spread. None contains wide receiver statistics or receiver salary/cap data, so "best value wide receiver" cannot be determined from this data.
  > We don't have the data to give an accurate answer to that.

### 23. How good a value was Johnny Fakeplayer in 2025?

*`made_up_player`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 3.2 s, $0.00035, 1 query, reason: model: No quarterback named Johnny Fakeplayer appears in the qb_contract_value table (searched passer_full_name and passer_name for "Fakeplayer"), so there is no 2025 cap value score for him. The tables cover QB seasons from 2015 onward, and this player is not among them.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_id, passer_name, passer_full_name, team, epa_per_dropback, cap_share, epa_over_expected, worth_it FROM qb_contract_value WHERE passer_full_name ILIKE %s OR passer_name ILIKE %s` params `['%Fakeplayer%', '%Fakeplayer%']`
- Run `20261019-124931`: ✅ PASS, 3.4 s, $0.00040, 2 queries, reason: model: No QB named Johnny Fakeplayer appears in the tables for 2025 (or any season): qb_contract_value and qb_season_epa have no rows matching that name, so there is no cap hit, EPA, or value score to report.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_full_name, team, cap_number, cap_share, epa_per_dropback, epa_over_expected, worth_it FROM qb_contract_value WHERE passer_full_name = %s AND season = 2025` params `['Johnny Fakeplayer']`
  - `SELECT passer_full_name, season FROM qb_season_epa WHERE passer_full_name ILIKE %s` params `['%fakeplayer%']`
- Run `20261019-125126`: ✅ PASS, 2.9 s, $0.00031, 1 query, reason: model: No quarterback named Johnny Fakeplayer appears in the QB tables (qb_contract_value or qb_season_epa) for 2025, so there is no contract value or EPA data for him.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_full_name, team, cap_number, cap_share, epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_full_name ILIKE %s AND season = 2025` params `['%Fakeplayer%']`

### 24. What was the weather in Buffalo for their last home game?

*`weather`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.1 s, $0.00015, 0 queries, reason: model: None of the tables record weather. game_results_vs_spread has game, score, and spread columns only, and the other tables cover QB efficiency, contract value, fourth-down decisions, and team EPA. The data can't say what the weather was at Buffalo's last home game.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 1.9 s, $0.00014, 0 queries, reason: model: None of the tables record weather. game_results_vs_spread has only game identity, scores, and spread results, and the other tables cover QB efficiency, QB salary cap value, fourth-down decisions, and team EPA. The data can't say what the weather was at Buffalo's last home game.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 1.9 s, $0.00014, 0 queries, reason: model: The tables hold game scores, dates, teams, betting spreads, and QB/team efficiency stats. None contain weather, temperature, or conditions for any game, so the Buffalo home-game weather can't be answered.
  > We don't have the data to give an accurate answer to that.

### 25. What will Drake Maye's cap hit be in 2030?

*`future_cap_hit`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 2.1 s, $0.00016, 0 queries, reason: model: The tables hold QB cap hits only for past and current seasons (2015 through 2026 at most). They have no contract projections, so Drake Maye's 2030 cap hit isn't covered.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-124931`: ✅ PASS, 2.4 s, $0.00017, 0 queries, reason: model: The tables hold QB cap hits by season only through the current seasons (2015-2026 at most, with 2026 in progress). They have no projected or future cap figures, so Drake Maye's 2030 cap hit isn't covered.
  > We don't have the data to give an accurate answer to that.
- Run `20261019-125126`: ✅ PASS, 2.7 s, $0.00020, 0 queries, reason: model: The tables hold historical QB seasons and cap hits (qb_contract_value covers seasons through 2026 at most, with league caps by season), with no contract projections or future cap figures. A 2030 cap hit for Drake Maye isn't in the data, and I can't estimate it from these tables.
  > We don't have the data to give an accurate answer to that.

### 26. Who had the highest EPA per dropback in 2024? Give his full name.

*`full_name_best_epa_2024`. Expected: names **Lamar Jackson** in full.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 5.2 s, $0.00046, 1 query
  > Lamar Jackson had the highest EPA per dropback in 2024, at 0.356 across 538 dropbacks. Among 2024 quarterbacks in the regular-season efficiency table, Lamar Jackson (BAL) led, ahead of Josh Allen (0.304) and Jared Goff (0.277). The 2024 season is complete, so these numbers are final.
  - `SELECT passer_full_name, passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2024 ORDER BY epa_per_dropback DESC LIMIT 5`
- Run `20261019-124931`: ✅ PASS, 6.1 s, $0.00066, 1 query
  > Lamar Jackson had the highest EPA per dropback in 2024, at 0.356 across 538 dropbacks. Among QBs with a 2024 season row, Lamar Jackson of Baltimore led, ahead of Josh Allen (0.304) and Jared Goff (0.277). The 2024 season is finished, so these numbers are final.
  - `SELECT passer_full_name, team, epa_per_dropback, dropbacks, is_season_complete FROM qb_season_epa WHERE season = 2024 ORDER BY epa_per_dropback DESC LIMIT 10`
- Run `20261019-125126`: ✅ PASS, 6.6 s, $0.00069, 1 query
  > Lamar Jackson had the highest EPA per dropback in 2024, at 0.356 over 538 dropbacks for Baltimore. Among 2024 QBs, Lamar Jackson led at 0.356 EPA per dropback, ahead of Josh Allen (0.304) and Jared Goff (0.277). The 2024 season is complete, so these figures are final.
  - `SELECT passer_full_name, passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2024 ORDER BY epa_per_dropback DESC LIMIT 5`

### 27. Which team covered the spread most often in 2024, and how many times?

*`ats_regular_season_2024`. Expected: names **LAC** (); states **13**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261019-124734`: ✅ PASS, 6.3 s, $0.00061, 1 query
  > In 2024 the Los Angeles Chargers (LAC) covered the spread most often, 13 times in 17 regular-season games. Counting each team's regular-season games with a spread line, LAC covered 13 of 17, ahead of DEN at 12 and DET at 12 (DET also had one push). The 2024 season is complete, so these are final counts.
  - `WITH g AS ( SELECT home_team AS team, (ats_result = 'home') AS cover, (ats_result = 'push') AS push FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result IS NOT NULL UNION ALL SELECT away_team AS team, (ats_result = 'away') AS cover, (ats_result = 'push') AS push FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result IS NOT NULL ) SELECT team, SUM(CASE WHEN cover THEN 1 ELSE 0 END) AS covers, SUM(CASE WHEN push THEN 1 ELSE 0 END) AS pushes, COUNT(*) AS ats_games FROM g GROUP BY team ORDER BY covers DESC, team LIMIT 25`
- Run `20261019-124931`: ✅ PASS, 6.4 s, $0.00079, 2 queries
  > The LAC covered the spread most often in 2024, with 13 covers in 17 regular-season games. I counted each team's regular-season 2024 games where its side covered the spread (home covers when ats_result is home, away when it is away), skipping games without a spread line. DEN and DET were next with 12 covers each. The 2024 season is complete, so these are final numbers.
  - `WITH g AS ( SELECT home_team AS team, (ats_result = 'home') AS covered FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result IS NOT NULL UNION ALL SELECT away_team AS team, (ats_result = 'away') AS covered FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result IS NOT NULL ) SELECT team, SUM(CASE WHEN covered THEN 1 ELSE 0 END) AS covers, COUNT(*) AS games FROM g GROUP BY team ORDER BY covers DESC, team LIMIT 10`
  - `SELECT season, is_season_complete FROM qb_season_epa WHERE season = 2024 LIMIT 1`
- Run `20261019-125126`: ✅ PASS, 5.8 s, $0.00072, 1 query
  > The Los Angeles Chargers (LAC) covered the spread most often in 2024, going 13 times against the spread. LAC covered 13 of their 17 decided regular-season games (ATS results, excluding pushes and games without a spread). Denver was next with 12 covers in 17 games, and Detroit had 12 covers in 16. The 2024 season is complete, so these are final counts.
  - `WITH covers AS ( SELECT home_team AS team, 1 AS cover, 1 AS decided FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result = 'home' UNION ALL SELECT away_team, 1, 1 FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result = 'away' UNION ALL SELECT home_team, 0, 1 FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result = 'away' UNION ALL SELECT away_team, 0, 1 FROM game_results_vs_spread WHERE season = 2024 AND game_type = 'REG' AND ats_result = 'home' ) SELECT team, SUM(cover) AS covers, SUM(decided) AS ats_games FROM covers GROUP BY team ORDER BY covers DESC, team LIMIT 25`

## Every failure, with its recorded reason

(Reasons were recorded from the second run on.)

| Run | Model | Question | Failed check | Reason | Queries | Time |
| --- | --- | --- | --- | --- | --- | --- |
| 20261019-124734 | Claude Haiku 5.5 | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | numbers not in any result: 90 | 2 | 9.5 s |
| 20261019-124931 | Claude Haiku 5.5 | Across all games since 2015 that had a spread, how often did the home team cover? | pct | (not recorded) | 1 | 6.6 s |
| 20261019-125126 | Claude Haiku 5.5 | Across all games since 2015 that had a spread, how often did the home team cover? | pct | (not recorded) | 2 | 7.9 s |

## Who served GLM's requests

Every request asked OpenRouter for zero-data-retention, no-data-collection providers only.

- `20261019-124734`: (not recorded)
- `20261019-124931`: (not recorded)
- `20261019-125126`: (not recorded)
