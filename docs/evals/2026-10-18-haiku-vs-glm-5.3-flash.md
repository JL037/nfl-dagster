# Ask page model evaluation: Claude Haiku 5.5 vs GLM-5.3 Flash (2026-10-18)

Which model should answer the Ask page's questions? Both ran the **same loop, rules and
questions**: 25 golden questions (`evals/golden.yaml`), 15 the served marts can answer and 10
they can't, against the dev serving database. Each model ran three times, about 6 cents in
all. Scoring is fixed rules, not an LLM grader: the right player or team named, the right
number at the precision written, and for out-of-scope questions exactly the "We don't have the
data" reply. Regenerate the data sections with `python evals/report.py evals/results/*.json`.

**Code changes between runs.** Run 1 (`201055`) is the baseline. Before run 2 (`201603`):
- no-data reasons are recorded
- a rule to compute every number in SQL and never quote the definitions
- a wildcard-only literal (`'%'`) is allowed in SQL

Before run 3 (`202158`): the number check compares magnitudes, so "allowed 0.062" can stand for
-0.062. The models answer slightly differently each run, so read the combined table, not one run.

## Findings

1. **"No data, no answer" held on both models: 30 of 30 out-of-scope questions, every run.**
   Neither model ever invented anything: touchdowns, a Super Bowl pick, college players,
   injuries, 2005, betting lines, wide receivers, a made-up player, weather, a 2030 cap hit.
   The no-data rule is enforced in code, and it worked the same on both.
2. **Accuracy on answerable questions is close:** Haiku 39/45 (87%), GLM 37/45 (82%). Three
   runs can't separate them on accuracy alone.
3. **Haiku is cheaper per question even though GLM is cheaper per token.** GLM's list price is
   about half of Haiku's ($0.048 / $0.20 vs $0.10 / $0.50 per million input / output tokens),
   but it costs **44% more per question** ($0.00046 vs $0.00032). It spends extra output
   tokens reasoning (49 tokens to say "ok", against Haiku's 4), and Haiku reads its 3,700-token
   instructions from cache at a tenth of the price. Either way, 1,000 questions cost under 50 cents.
4. **Haiku is about twice as fast:** 3.1 s on average against 5.7 s, and GLM's slowest answer
   took 22.7 s.
5. **Haiku's privacy story is simpler.** Every Haiku request goes to one company (Anthropic).
   GLM's were served by **nine different hosting companies** through OpenRouter. All were
   zero-data-retention providers by OpenRouter's own listing, which was enforced per request and
   in the account settings, but that is nine parties to trust rather than one.
6. **The misses share causes, and the number check caught every one of them:**
   - **Aggregate questions** (league-wide fourth-down rate, home cover share) failed on both
     models. The models wrote numbers no query returned: the "10–90%" win-probability window and
     2015's 26.8% example, quoted from the definitions in the catalog, or a game count (3,026)
     added up in their heads. Every one of those answers was replaced with the no-data reply
     rather than shown. The numbers themselves were mostly right, but they weren't backed by a
     query, so the check behaved as designed.
   - **GLM ran out of its 3-query budget** twice (Jordan Love's cap share, Josh Allen's EPA),
     after spending queries on SQL our gate rejected.
   - **One false alarm in my number check** (Haiku, LA's defense written as "allowed 0.062"
     for -0.062), fixed before run 3.

## Recommendation

**Use Claude Haiku 5.5.** It's as accurate or better, about 30% cheaper per question, about twice as fast, and it involves one provider instead of nine. Keep `ASK_MODEL` and the
OpenRouter adapter, so the comparison can be re-run whenever a new model is worth trying.

## What to improve next (measured by re-running these evals)

- **Keep example results out of what the model reads.** The SQL headers mix methodology
  (the "10–90% win probability" window, which a correct answer may quote) with example findings
  (2015's 26.8%, which go stale). Separate them, and let answers quote methodology numbers.
- **Turn aggregate questions into lookups.** A league-by-season summary mart (league fourth-down
  rate, home/away/push shares) means the model looks a number up instead of computing it: a
  data-modeling fix, tested in dbt like every other mart.
- **Add golden questions** for the wording issue seen earlier (spelling out "New England
  Patriots" when the data only has `NE`) and for ambiguous names ("J.Daniels").

## Results by run

| Run | Model | In scope (15) | Out of scope (10) | Overall | Cost / question | Run cost | Avg time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 20261018-201055 | Claude Haiku 5.5 | 13/15 | 10/10 | 23/25 | $0.00032 | $0.0080 | 3.2 s |
| 20261018-201055 | GLM-5.3 Flash | 11/15 | 10/10 | 21/25 | $0.00054 | $0.0134 | 5.5 s |
| 20261018-201603 | Claude Haiku 5.5 | 13/15 | 10/10 | 23/25 | $0.00033 | $0.0082 | 3.2 s |
| 20261018-201603 | GLM-5.3 Flash | 14/15 | 10/10 | 24/25 | $0.00045 | $0.0113 | 5.3 s |
| 20261018-202158 | Claude Haiku 5.5 | 13/15 | 10/10 | 23/25 | $0.00031 | $0.0077 | 3.0 s |
| 20261018-202158 | GLM-5.3 Flash | 12/15 | 10/10 | 22/25 | $0.00038 | $0.0096 | 6.3 s |

## All runs combined

| Model | In scope | Out of scope | Overall | Cost / question | Total cost | Avg time |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | 39/45 | 30/30 | 69/75 | $0.00032 | $0.0239 | 3.1 s |
| GLM-5.3 Flash | 37/45 | 30/30 | 67/75 | $0.00046 | $0.0343 | 5.7 s |

## Question by question (passes out of runs)

| Question | Expected | Claude Haiku 5.5 | GLM-5.3 Flash |
| --- | --- | --- | --- |
| best_value_2025 | answer | 3/3 | 3/3 |
| maye_over_expected_2025 | answer | 3/3 | 3/3 |
| prescott_worth_it_2025 | answer | 3/3 | 2/3 ⚠️ |
| highest_cap_share_2025 | answer | 3/3 | 3/3 |
| love_cap_share_2025 | answer | 3/3 | 2/3 ⚠️ |
| worth_it_count_2025 | answer | 3/3 | 3/3 |
| mahomes_2018 | answer | 3/3 | 3/3 |
| best_epa_2025 | answer | 3/3 | 3/3 |
| allen_epa_2024 | answer | 3/3 | 2/3 ⚠️ |
| best_net_2025 | answer | 2/3 ⚠️ | 3/3 |
| best_defense_2025 | answer | 3/3 | 3/3 |
| go_for_it_leader_2025 | answer | 3/3 | 3/3 |
| league_go_rate_2025 | answer | 1/3 ⚠️ | 0/3 ⚠️ |
| home_cover_share | answer | 0/3 ⚠️ | 2/3 ⚠️ |
| best_value_2026_so_far | answer | 3/3 | 2/3 ⚠️ |
| mahomes_touchdowns | no data | 3/3 | 3/3 |
| super_bowl_pick | no data | 3/3 | 3/3 |
| college_qb | no data | 3/3 | 3/3 |
| injuries | no data | 3/3 | 3/3 |
| brady_2005 | no data | 3/3 | 3/3 |
| next_game_total | no data | 3/3 | 3/3 |
| wide_receiver | no data | 3/3 | 3/3 |
| made_up_player | no data | 3/3 | 3/3 |
| weather | no data | 3/3 | 3/3 |
| future_cap_hit | no data | 3/3 | 3/3 |

## Every failure, with its recorded reason

(Reasons were recorded from the second run on.)

| Run | Model | Question | Status | Failed check | Reason | Queries |
| --- | --- | --- | --- | --- | --- | --- |
| 20261018-201055 | Claude Haiku 5.5 | league_go_rate_2025 | no_data | no answer | (not recorded) | 1 |
| 20261018-201055 | Claude Haiku 5.5 | home_cover_share | no_data | no answer | (not recorded) | 1 |
| 20261018-201055 | GLM-5.3 Flash | prescott_worth_it_2025 | no_data | no answer | (not recorded) | 2 |
| 20261018-201055 | GLM-5.3 Flash | league_go_rate_2025 | no_data | no answer | (not recorded) | 2 |
| 20261018-201055 | GLM-5.3 Flash | home_cover_share | no_data | no answer | (not recorded) | 3 |
| 20261018-201055 | GLM-5.3 Flash | best_value_2026_so_far | no_data | no answer | (not recorded) | 1 |
| 20261018-201603 | Claude Haiku 5.5 | best_net_2025 | no_data | no answer | numbers not in any result: 0.062 | 2 |
| 20261018-201603 | Claude Haiku 5.5 | home_cover_share | no_data | no answer | numbers not in any result: 3026 | 2 |
| 20261018-201603 | GLM-5.3 Flash | league_go_rate_2025 | no_data | no answer | numbers not in any result: 90, 26.8, 2015 | 1 |
| 20261018-202158 | Claude Haiku 5.5 | league_go_rate_2025 | no_data | no answer | numbers not in any result: 90 | 1 |
| 20261018-202158 | Claude Haiku 5.5 | home_cover_share | no_data | no answer | numbers not in any result: 3026 | 2 |
| 20261018-202158 | GLM-5.3 Flash | love_cap_share_2025 | no_data | no answer | query budget used up | 3 |
| 20261018-202158 | GLM-5.3 Flash | allen_epa_2024 | no_data | no answer | query budget used up | 3 |
| 20261018-202158 | GLM-5.3 Flash | league_go_rate_2025 | no_data | no answer | numbers not in any result: 90 | 1 |

## Who served GLM's requests

Every request asked OpenRouter for zero-data-retention, no-data-collection providers only.

- 20261018-201055: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Parasail, PrimeIntellect, Together, Wafer
- 20261018-201603: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Sail Research, Together, Wafer
- 20261018-202158: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Sail Research, Wafer

## Full answers and SQL, run 20261018-202158

### best_value_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00038, 3.6 s

> Drake Maye (NE) was the best value for his share of the cap in 2025. His cap share was 3.0%, and he produced 0.316 EPA per dropback against an expected 0.021, a score of +0.295 over expected. The 2025 season is complete, so these numbers are final.

- `SELECT passer_name, team, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`

**GLM-5.3 Flash**: PASS, $0.00042, 3.1 s

> Drake Maye of New England was the best value in 2025, producing +0.295 EPA per dropback above what quarterbacks paid his share of the cap usually produce (about 3.0% of the salary cap). Brock Purdy (+0.183) and Jordan Love (+0.182) were next, but well behind.

- `SELECT passer_name, team, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`

### maye_over_expected_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00048, 4.1 s

> Drake Maye's 2025 EPA per dropback (0.316) was 0.295 above what QBs at his cap share (about 3.0% of the cap) usually produce (0.021). The season is complete and he was scored on the Patriots cap hit, so this is a final figure.

- `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Drake Maye', 2025]`
- `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%maye%', 2025]`

**GLM-5.3 Flash**: PASS, $0.00048, 2.9 s

> Drake Maye's 2025 EPA per dropback was about 0.30 above what QBs paid his share of the cap usually produce (0.32 actual vs 0.02 expected), and that season is complete so it's a final number, not an estimate.

- `SELECT passer_name, season, epa_over_expected, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = 2025` params `['Drake Maye']`
- `SELECT qb_season_key, passer_name, season, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s` params `['%Maye%']`

### prescott_worth_it_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00038, 3.3 s

> Yes, by this measure. Dak Prescott's 2025 season (complete, Dallas) came in at 0.169 EPA per dropback, about 0.038 above the 0.132 that QBs paying his cap share (18.1% of the cap, a $50.5M hit) usually produce, so he was flagged as worth it.

- `SELECT passer_name, season, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Prescott%', 2025]`

**GLM-5.3 Flash**: PASS, $0.00044, 4.7 s

> Yes. Dak Prescott's 2025 Cowboys season is marked complete, and he was classified as "worth it": he posted 0.169 EPA per dropback over 654 dropbacks while carrying an 18.1% cap share (about $50.5 million), above the 0.132 expected for QBs paid that much, for a +0.038 EPA per dropback over expected.

- `SELECT season, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE season = 2025 AND passer_name ILIKE %s` params `['%Prescott%']`

### highest_cap_share_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00031, 3.5 s

> Dak Prescott had the biggest cap hit as a share of the salary cap in 2025, at about 18.1% ($50.5 million) for the Dallas Cowboys. The 2025 season is complete, so this is a final figure.

- `SELECT passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = %s AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 5` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00035, 1.6 s

> Dak Prescott had the biggest 2025 cap hit: $50.5 million for Dallas, about 18.1% of the salary cap.

- `SELECT passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE season = 2025 ORDER BY cap_share DESC NULLS LAST LIMIT 1`

### love_cap_share_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00028, 3.8 s

> Jordan Love's 2025 cap hit with the Green Bay Packers was $29.7 million, about 10.6% of the league salary cap. The 2025 season is complete, so this is a final figure.

- `SELECT season, passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Love%', 2025]`

**GLM-5.3 Flash**: FAIL (no answer), $0.00070, 22.7 s, reason: query budget used up

> We don't have the data to give an accurate answer to that.

- `SELECT passer_name, season, team, cap_number, cap_share, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Jordan Love', 2025]`
- `SELECT passer_name, season, team, cap_number, cap_share, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s ORDER BY season` params `['Jordan Love']`
- `SELECT DISTINCT passer_name, passer_id FROM qb_contract_value WHERE passer_name ILIKE %s ORDER BY passer_name` params `['%Love%']`

### worth_it_count_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00031, 2.7 s

> In 2025, 19 of the 38 quarterbacks with a scored season were worth their contract, meaning their EPA per dropback beat what QBs paying that share of the salary cap usually produce. The 2025 season is complete, so these are final numbers.

- `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(worth_it) AS scored_count, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = %s` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00013, 19.0 s

> 19 of the 38 scored quarterbacks were worth their contract in 2025. Note that the 2025 season is still in progress, so those numbers are estimates based on the season so far.

- `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(*) AS total_scored, BOOL_OR(NOT is_season_complete) AS season_in_progress FROM qb_contract_value WHERE season = 2025 AND is_cap_hit_for_team`

### mahomes_2018 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00034, 2.8 s

> Patrick Mahomes in 2018 (KC) finished 0.34 EPA per dropback above expected for his cap share, based on 0.36 actual versus 0.01 expected. That season is complete, so the figure is final.

- `SELECT passer_name, season, team, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Mahomes%', 2018]`

**GLM-5.3 Flash**: PASS, $0.00043, 19.3 s

> In 2018 Patrick Mahomes produced 0.360 EPA per dropback, about +0.34 above the 0.015 expected from a QB on roughly 2.1% of the cap — the second-best value season in the data and an MVP year on a rookie deal.

- `SELECT epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Patrick Mahomes', 2018]`
- `SELECT passer_id, passer_name, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share, is_season_complete FROM qb_contract_value WHERE season = %s AND passer_name LIKE %s` params `[2018, 'Mahomes']`
- `SELECT season, passer_id, passer_name, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share FROM qb_contract_value WHERE passer_name LIKE %s ORDER BY season` params `['%Mahomes%']`

### best_epa_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00028, 3.5 s

> D.Maye of New England had the highest EPA per dropback in 2025, at about 0.316 across 601 dropbacks. The 2025 season is complete, so this is a final figure.

- `SELECT passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC LIMIT 1` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00033, 3.0 s

> Drake Maye of New England had the highest EPA per dropback in 2025 at about 0.316, ahead of Jordan Love (0.259) and Matthew Stafford (0.223).

- `SELECT passer_name, team, epa_per_dropback, dropbacks, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC LIMIT 5` params `[2025]`

### allen_epa_2024 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00034, 3.5 s

> Josh Allen's 2024 EPA per dropback was 0.30 (0.304 unrounded) over 539 dropbacks for Buffalo, and the season is complete. The table lists him only as "J.Allen," so I matched him by the BUF team and the 2024 season.

- `SELECT passer_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_name LIKE %s AND season = %s` params `['%Allen%', 2024]`

**GLM-5.3 Flash**: FAIL (no answer), $0.00082, 3.2 s, reason: query budget used up

> We don't have the data to give an accurate answer to that.

- `SELECT epa_per_dropback FROM qb_season_epa WHERE passer_name ILIKE 'Josh Allen' AND season = 2024` params `['Josh Allen']`
- `SELECT epa_per_dropback FROM qb_season_epa WHERE passer_name ILIKE %s AND season = 2024` params `['Josh Allen']`
- `SELECT passer_name, epa_per_dropback FROM qb_season_epa WHERE season = 2024 AND passer_id LIKE 'allen%'`

### best_net_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00031, 2.9 s

> The Los Angeles Rams had the best net EPA per play in 2025, at about 0.207 (offense 0.145, defense -0.062). The New England Patriots were close behind at about 0.203, and the Buffalo Bills were third at about 0.156.

- `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = %s ORDER BY net_epa_per_play DESC NULLS LAST LIMIT 3` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00071, 3.3 s

> The Los Angeles Rams had the best net EPA per play in 2025 at about 0.207.

- `SELECT team_name, team, net_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 1`

### best_defense_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00032, 2.7 s

> The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.13 EPA per play across 977 plays. The Seattle Seahawks (-0.12) and Jacksonville Jaguars (-0.10) followed.

- `SELECT team, team_name, def_epa_per_play, def_plays, net_epa_per_play FROM team_season_epa WHERE season = %s AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 3` params `[2025]`
- `SELECT is_season_complete FROM qb_season_epa WHERE season = %s LIMIT 1` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00034, 2.3 s

> The Houston Texans had the best defense in 2025, allowing -0.131 EPA per play, which edged out the Seattle Seahawks (-0.118) and the Jacksonville Jaguars (-0.104).

- `SELECT team, team_name, def_epa_per_play, def_success_rate FROM team_season_epa WHERE season = 2025 ORDER BY def_epa_per_play ASC LIMIT 3`

### go_for_it_leader_2025 (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00034, 3.1 s

> The Indianapolis Colts went for it most often on fourth-and-short in 2025: 16 times in 19 decisions, a 84.2% go rate. They also had the most go-for-it attempts of any team, ahead of the Bills (14) and Cowboys (13).

- `SELECT team, team_name, fourth_downs, went_for_it, go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC NULLS LAST, went_for_it DESC LIMIT 3` params `[2025]`

**GLM-5.3 Flash**: PASS, $0.00064, 3.7 s

> The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% (16 of 19 decisions in competitive game states). The Buffalo Bills were close behind at 82.4%.

- `SELECT team, team_name, fourth_downs, went_for_it, go_pct, conversion_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC LIMIT 3` params `[2025]`

### league_go_rate_2025 (expected: answer)

**Claude Haiku 5.5**: FAIL (no answer), $0.00034, 3.8 s, reason: numbers not in any result: 90

> We don't have the data to give an accurate answer to that.

- `SELECT SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS league_go_pct FROM team_fourth_down WHERE season = %s` params `[2025]`

**GLM-5.3 Flash**: FAIL (no answer), $0.00035, 1.2 s, reason: numbers not in any result: 90

> We don't have the data to give an accurate answer to that.

- `select round(100*sum(went_for_it)::numeric/sum(fourth_downs),1) as go_pct, min(season) from team_fourth_down where season = 2025`

### home_cover_share (expected: answer)

**Claude Haiku 5.5**: FAIL (no answer), $0.00091, 6.4 s, reason: numbers not in any result: 3026

> We don't have the data to give an accurate answer to that.

- `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IN (%s, %s)), 0), 1) AS home_cover_pct_excl_pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct_all FROM game_results_vs_spread WHERE season >= %s" params=["home","away","push","home","home","away","home","2015"]` params `['home', 'away', 'push', 'home', 'home', 'away', 'home', '2015']`
- `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IN (%s, %s)), 0), 1) AS home_cover_pct_excl_pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct_all FROM game_results_vs_spread WHERE season >= 2015` params `['home', 'away', 'push', 'home', 'home', 'away', 'home']`

**GLM-5.3 Flash**: PASS, $0.00059, 2.1 s

> Since 2015, there were 3,107 games with a spread, and the home team covered in 1,482 of them — about 47.7% of the time. So despite home-field advantage, home teams covered the spread slightly less often than they lost it.

- `SELECT count(*) FILTER (WHERE ats_result='home')::float / count(*) FILTER (WHERE ats_result IS NOT NULL) AS home_rate, count(*) FILTER (WHERE ats_result='home'), count(*) FILTER (WHERE ats_result IS NOT NULL) FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL`
- `SELECT count(*) FILTER (WHERE ats_result = %s)::float / count(*)::float AS home_rate, count(*) FILTER (WHERE ats_result = %s) AS home_covers, count(*) AS games FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL` params `['home', 'home']`

### best_value_2026_so_far (expected: answer)

**Claude Haiku 5.5**: PASS, $0.00044, 3.7 s

> So far in 2026, Brock Purdy (SF) ranks as the best value for his cap share, at +0.36 EPA per dropback above expected on a 7.9% cap share. Lamar Jackson (BAL, +0.29) and Caleb Williams (CHI, +0.29) are next. These are estimates because the 2026 season is still in progress.

- `SELECT passer_name, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 5`

**GLM-5.3 Flash**: PASS, $0.00085, 7.2 s

> Through the in-progress 2026 season, Brock Purdy has been the best value for his cap share: he's producing about 0.36 EPA per dropback above what QBs paid a similar share (about 7.9% of the cap) usually do, ahead of Lamar Jackson (+0.29) and Caleb Williams (+0.29). Since the season is still underway, these numbers are estimates.

- `SELECT passer_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2026 ORDER BY epa_over_expected DESC NULLS LAST LIMIT 10`

### mahomes_touchdowns (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00015, 1.4 s, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, dropbacks, scrambles), cap figures, game results against the spread, fourth-down decisions, and team EPA. None of them record touchdown passes, so Patrick Mahomes' 2024 touchdown total can't be answered from this data.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00017, 2.8 s, reason: model: The available tables only cover QB EPA per dropback, success rate, dropbacks, scrambles, and cap data — no touchdown counts for any quarterback or season.

> We don't have the data to give an accurate answer to that.


### super_bowl_pick (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00018, 1.9 s, reason: model: The tables cover past game results against the spread, QB efficiency and contract value, fourth-down decisions, and regular-season team EPA. They contain no playoff bracket, no Super Bowl forecast, and no data that could predict this season's Super Bowl winner.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00022, 2.7 s, reason: model: The tables hold historical regular-season stats (QB and team EPA, fourth-down decisions, ATS results) but no predictive model, playoff data, or future results, so they cannot say who will win the Super Bowl.

> We don't have the data to give an accurate answer to that.


### college_qb (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00012, 1.6 s, reason: model: The tables cover NFL quarterbacks and teams only (QB season EPA, cap hits, and contract value). They contain no college football data, so college quarterback value in 2025 cannot be determined.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00017, 0.9 s, reason: model: The tables cover only NFL QB seasons and teams; there is no college quarterback data to answer this.

> We don't have the data to give an accurate answer to that.


### injuries (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00013, 1.4 s, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, scrambles), cap hits, game results against the spread, fourth-down decisions, and team EPA. None record injuries or games missed, so I can't say which quarterback missed the most games in 2025.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00009, 4.8 s, reason: model: The tables cover QB EPA per dropback, contract value, team efficiency, and fourth-down decisions, but nothing about games missed to injury, so injuries/missed games can't be measured.

> We don't have the data to give an accurate answer to that.


### brady_2005 (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00033, 4.5 s, reason: model: The QB contract and cap tables have no row for Tom Brady in 2005. Their cap data covers 2015-2025 only, so no 2005 cap share is available.

> We don't have the data to give an accurate answer to that.

- `SELECT season, passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE passer_name LIKE %s AND season = 2005` params `['%Brady%']`

**GLM-5.3 Flash**: PASS, $0.00055, 5.2 s, reason: model: The database only covers the 2015-2025 seasons, so there is no row for Tom Brady's 2005 cap hit or cap share in qb_contract_value or qb_season_epa.

> We don't have the data to give an accurate answer to that.

- `SELECT qb_season_key, season, cap_number, cap_share, epa_per_dropback FROM qb_contract_value WHERE season = 2005 AND passer_name = %s` params `['Tom Brady']`
- `SELECT qb_season_key, season, dropbacks, epa_per_dropback FROM qb_season_epa WHERE season = 2005 AND passer_name = %s` params `['Tom Brady']`

### next_game_total (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00012, 1.7 s, reason: model: The tables hold point spreads (spread_line and ATS results) but no over/under (total points line) for any game, and no upcoming schedule, so the Chiefs' next game's over/under can't be found.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00009, 9.8 s, reason: model: The tables only cover played games and their betting spreads; there is no schedule of upcoming games and no over/under (total points) line data.

> We don't have the data to give an accurate answer to that.


### wide_receiver (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00014, 1.7 s, reason: model: The tables cover quarterbacks (qb_contract_value, qb_season_epa), team efficiency, fourth-down decisions, and game ATS results. None include wide receiver stats, salaries, or value scores, so the best value wide receiver in 2025 can't be determined.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00017, 0.6 s, reason: model: The tables cover QB EPA and contract value, team EPA, and fourth downs — no wide receiver data.

> We don't have the data to give an accurate answer to that.


### made_up_player (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00049, 5.3 s, reason: model: No QB named Johnny Fakeplayer has a 2025 season in qb_contract_value (searched by name, no rows returned), so his value score cannot be computed from these tables.

> We don't have the data to give an accurate answer to that.

- `SELECT season, passer_name, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%', 2025]`
- `SELECT season, passer_name, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%']`

**GLM-5.3 Flash**: PASS, $0.00023, 20.8 s, reason: model: No player named "Johnny Fakeplayer" (or anything matching "Fake") exists in the qb_contract_value or qb_season_epa tables, so there's no data to assess his 2025 value.

> We don't have the data to give an accurate answer to that.

- `SELECT qb_season_key, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Fakeplayer%', 2025]`
- `SELECT qb_season_key, passer_name, season, team, epa_per_dropback FROM qb_contract_value WHERE passer_name ILIKE %s LIMIT 20` params `['%Fake%']`

### weather (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00013, 1.4 s, reason: model: None of the tables record weather. game_results_vs_spread has game dates, teams, scores and spreads, but no temperature, wind, precipitation or conditions, so the Buffalo home game's weather can't be determined from this data.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00017, 3.7 s, reason: model: The available tables cover game results against the spread, QB EPA and contracts, fourth-down decisions, and team EPA, but none contain weather information (temperature, conditions, etc.) for any game.

> We don't have the data to give an accurate answer to that.


### future_cap_hit (expected: no data)

**Claude Haiku 5.5**: PASS, $0.00015, 1.8 s, reason: model: The tables hold QB cap hits only for past and in-progress seasons (the latest season shown is 2026, in progress). They contain no projected or future contract figures, so Drake Maye's 2030 cap hit cannot be determined from this data.

> We don't have the data to give an accurate answer to that.


**GLM-5.3 Flash**: PASS, $0.00019, 6.0 s, reason: model: Drake Maye's 2030 cap hit is a future contract number; the database only has historical and current-season cap hits (through the 2025 season in progress) and doesn't contain future salary or projected cap figures.

> We don't have the data to give an accurate answer to that.


