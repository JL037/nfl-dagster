# Ask page model evaluation: Claude Haiku 5.5 vs GLM-5.3 Flash (2026-10-18)

Which model should answer the Ask page's questions? Both ran the **same loop, rules and
questions**: 25 golden questions (`evals/golden.yaml`), 15 the served marts can answer and 10
they can't, against the dev serving database. Each model ran three times, about 6 cents in
all. Scoring is fixed rules, not an LLM grader: the right player or team named, the right
number at the precision written, and for out-of-scope questions exactly the "We don't have the
data" reply. Regenerate the data sections with `python evals/report.py evals/results/*.json`. Expected
answers are computed from the dev serving database (as of 2026-10-18).

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

| Run | Model | In scope | Out of scope | Overall | Cost / question | Run cost | Avg time | Median time | Slowest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20261018-201055 | Claude Haiku 5.5 | 13/15 (87%) | 10/10 (100%) | 23/25 (92%) | $0.00032 | $0.0080 | 3.2 s | 2.7 s | 7.7 s |
| 20261018-201055 | GLM-5.3 Flash | 11/15 (73%) | 10/10 (100%) | 21/25 (84%) | $0.00054 | $0.0134 | 5.5 s | 4.4 s | 15.5 s |
| 20261018-201603 | Claude Haiku 5.5 | 13/15 (87%) | 10/10 (100%) | 23/25 (92%) | $0.00033 | $0.0082 | 3.2 s | 3.3 s | 6.1 s |
| 20261018-201603 | GLM-5.3 Flash | 14/15 (93%) | 10/10 (100%) | 24/25 (96%) | $0.00045 | $0.0113 | 5.3 s | 3.4 s | 15.5 s |
| 20261018-202158 | Claude Haiku 5.5 | 13/15 (87%) | 10/10 (100%) | 23/25 (92%) | $0.00031 | $0.0077 | 3.0 s | 3.1 s | 6.4 s |
| 20261018-202158 | GLM-5.3 Flash | 12/15 (80%) | 10/10 (100%) | 22/25 (88%) | $0.00038 | $0.0096 | 6.3 s | 3.3 s | 22.7 s |

## All runs combined

| Model | In scope | Out of scope | Overall | Cost / question | Total cost | Avg time | Median time | Slowest |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Haiku 5.5 | 39/45 (87%) | 30/30 (100%) | 69/75 (92%) | $0.00032 | $0.0239 | 3.1 s | 3.0 s | 7.7 s |
| GLM-5.3 Flash | 37/45 (82%) | 30/30 (100%) | 67/75 (89%) | $0.00046 | $0.0343 | 5.7 s | 3.7 s | 22.7 s |

## Question by question

| Question | Expected | Claude Haiku 5.5 passed | Claude Haiku 5.5 avg time | GLM-5.3 Flash passed | GLM-5.3 Flash avg time |
| --- | --- | --- | --- | --- | --- |
| Which quarterback was the best value for his share of the salary cap in 2025? | answer | 3/3 | 3.9 s | 3/3 | 4.2 s |
| How far above expected for his cap share was Drake Maye's EPA per dropback in 2025? | answer | 3/3 | 3.6 s | 3/3 | 3.9 s |
| Was Dak Prescott worth his contract in 2025? | answer | 3/3 | 5.5 s | 2/3 ⚠️ | 4.2 s |
| Which quarterback had the biggest cap hit as a share of the salary cap in 2025? | answer | 3/3 | 3.2 s | 3/3 | 1.4 s |
| What share of the salary cap was Jordan Love's cap hit in 2025? | answer | 3/3 | 3.2 s | 2/3 ⚠️ | 12.3 s |
| How many quarterbacks were worth their contract in 2025? | answer | 3/3 | 3.4 s | 3/3 | 11.8 s |
| How far above expected for his cap share was Patrick Mahomes in 2018? | answer | 3/3 | 4.1 s | 3/3 | 16.3 s |
| Which quarterback had the highest EPA per dropback in 2025? | answer | 3/3 | 3.3 s | 3/3 | 3.0 s |
| What was Josh Allen's EPA per dropback in 2024? | answer | 3/3 | 3.8 s | 2/3 ⚠️ | 3.2 s |
| Which team had the best net EPA per play in 2025? | answer | 2/3 ⚠️ | 2.8 s | 3/3 | 4.9 s |
| Which team had the best defense by EPA allowed per play in 2025? | answer | 3/3 | 3.9 s | 3/3 | 2.9 s |
| Which team went for it most often on fourth-and-short in 2025? | answer | 3/3 | 2.9 s | 3/3 | 3.7 s |
| How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | answer | 1/3 ⚠️ | 4.0 s | 0/3 ⚠️ | 6.2 s |
| Across all games since 2015 that had a spread, how often did the home team cover? | answer | 0/3 ⚠️ | 5.9 s | 2/3 ⚠️ | 3.9 s |
| Who has been the best value quarterback for his cap share so far in 2026? | answer | 3/3 | 4.3 s | 2/3 ⚠️ | 7.8 s |
| How many touchdowns did Patrick Mahomes throw in 2024? | no data | 3/3 | 1.7 s | 3/3 | 2.4 s |
| Who will win the Super Bowl this season? | no data | 3/3 | 1.8 s | 3/3 | 2.1 s |
| Which college quarterback was the best value in 2025? | no data | 3/3 | 1.5 s | 3/3 | 5.6 s |
| Which quarterback missed the most games to injury in 2025? | no data | 3/3 | 1.4 s | 3/3 | 5.8 s |
| What was Tom Brady's cap share in 2005? | no data | 3/3 | 3.4 s | 3/3 | 6.4 s |
| What is the over/under for the Chiefs' next game? | no data | 3/3 | 1.9 s | 3/3 | 6.0 s |
| Who was the best value wide receiver in 2025? | no data | 3/3 | 1.5 s | 3/3 | 1.2 s |
| How good a value was Johnny Fakeplayer in 2025? | no data | 3/3 | 4.4 s | 3/3 | 13.2 s |
| What was the weather in Buffalo for their last home game? | no data | 3/3 | 1.3 s | 3/3 | 2.8 s |
| What will Drake Maye's cap hit be in 2030? | no data | 3/3 | 1.6 s | 3/3 | 7.0 s |

## Every question, every response

### 1. Which quarterback was the best value for his share of the salary cap in 2025?

*`best_value_2025`. Expected: names **D.Maye**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.0 s, $0.00083, 1 query
  > Drake Maye of the New England Patriots was the best value in 2025. He had an EPA per dropback of 0.316 on an $8.3M cap hit (about 3.0% of the cap), which is 0.30 above the 0.021 that QBs at that cap share usually produce. The 2025 season is complete, so these numbers are final.
  - `SELECT passer_name, team, season, cap_number, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = %s AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 5` params `[2025]`
- Run `20261018-201603`: ✅ PASS, 4.0 s, $0.00085, 1 query
  > Drake Maye of the New England Patriots was the best value in 2025. His 0.316 EPA per dropback beat the 0.021 expected for his cap share (about 3.0% of the cap, or $8.3M), a score of +0.295. The season is complete, so these numbers are final.
  - `SELECT passer_name, team, season, cap_number, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`
- Run `20261018-202158`: ✅ PASS, 3.6 s, $0.00038, 1 query
  > Drake Maye (NE) was the best value for his share of the cap in 2025. His cap share was 3.0%, and he produced 0.316 EPA per dropback against an expected 0.021, a score of +0.295 over expected. The 2025 season is complete, so these numbers are final.
  - `SELECT passer_name, team, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 6.7 s, $0.00025, 1 query
  > Drake Maye was the best value in 2025: on just under 3% of the salary cap with New England, he posted 0.32 EPA per dropback, about 0.30 above what QBs paid that share usually produce.
  - `SELECT passer_name, team, cap_share, epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = %s AND is_cap_hit_for_team IS TRUE ORDER BY epa_over_expected DESC NULLS LAST LIMIT 1` params `[2025]`
- Run `20261018-201603`: ✅ PASS, 2.8 s, $0.00074, 1 query
  > Drake Maye was the best value in 2025: playing on just 3.0% of the salary cap for New England, he posted 0.32 EPA per dropback, about +0.30 above what QBs paid that share usually produce — the highest epa_over_expected that season. Brock Purdy (+0.18) and Jordan Love (+0.18) ranked next.
  - `SELECT passer_name, team, cap_share, epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`
- Run `20261018-202158`: ✅ PASS, 3.1 s, $0.00042, 1 query
  > Drake Maye of New England was the best value in 2025, producing +0.295 EPA per dropback above what quarterbacks paid his share of the cap usually produce (about 3.0% of the salary cap). Brock Purdy (+0.183) and Jordan Love (+0.182) were next, but well behind.
  - `SELECT passer_name, team, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2025 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 3`

### 2. How far above expected for his cap share was Drake Maye's EPA per dropback in 2025?

*`maye_over_expected_2025`. Expected: states **+0.295** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.7 s, $0.00030, 1 query
  > Drake Maye's 2025 EPA per dropback was about 0.30 above what QBs at his cap share (about 3.0% of the cap) usually produce: 0.316 actual versus an expected 0.021. The season is complete, so this is a final number.
  - `SELECT passer_name, season, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name LIKE %s AND season = %s` params `['%Maye%', 2025]`
- Run `20261018-201603`: ✅ PASS, 3.9 s, $0.00049, 2 queries
  > Drake Maye's 2025 EPA per dropback (0.316) was 0.295 above what a QB with his cap share (about 3.0% of the cap) usually produces (expected 0.021). The season is complete, and the cap hit is for the team he played for.
  - `SELECT passer_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Drake Maye', 2025]`
  - `SELECT passer_name, season, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name LIKE %s AND season = %s` params `['%Maye%', 2025]`
- Run `20261018-202158`: ✅ PASS, 4.1 s, $0.00048, 2 queries
  > Drake Maye's 2025 EPA per dropback (0.316) was 0.295 above what QBs at his cap share (about 3.0% of the cap) usually produce (0.021). The season is complete and he was scored on the Patriots cap hit, so this is a final figure.
  - `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Drake Maye', 2025]`
  - `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%maye%', 2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.9 s, $0.00079, 2 queries
  > Drake Maye's 2025 EPA per dropback of 0.316 was about 0.30 above the expected 0.021 for his cap share (epa_over_expected = +0.295), making it one of the top value seasons on record.
  - `SELECT passer_name, season, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Drake Maye', 2025]`
  - `SELECT passer_name, season, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Maye%', 2025]`
- Run `20261018-201603`: ✅ PASS, 4.0 s, $0.00065, 3 queries
  > In 2025, Drake Maye posted 0.316 EPA per dropback against an expected 0.021 for a QB paid his ~3.0% share of the cap, putting him about +0.295 EPA per dropback above expected — one of the top value seasons in the data.
  - `SELECT epa_per_dropback, expected_epa_per_dropback, epa_over_expected, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = 2025` params `['Drake Maye']`
  - `SELECT qb_season_key, passer_id, passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_name ILIKE %s AND season = 2025` params `['%Maye%']`
  - `SELECT epa_per_dropback, expected_epa_per_dropback, epa_over_expected, cap_share, is_season_complete FROM qb_contract_value WHERE passer_id = %s AND season = 2025` params `['00-0039851']`
- Run `20261018-202158`: ✅ PASS, 2.9 s, $0.00048, 2 queries
  > Drake Maye's 2025 EPA per dropback was about 0.30 above what QBs paid his share of the cap usually produce (0.32 actual vs 0.02 expected), and that season is complete so it's a final number, not an estimate.
  - `SELECT passer_name, season, epa_over_expected, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = 2025` params `['Drake Maye']`
  - `SELECT qb_season_key, passer_name, season, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s` params `['%Maye%']`

### 3. Was Dak Prescott worth his contract in 2025?

*`prescott_worth_it_2025`. Expected: states **+0.038** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 7.7 s, $0.00065, 2 queries
  > Yes, by this measure. In 2025 Dak Prescott (D.Prescott, DAL, 654 dropbacks, a finished season) posted 0.169 EPA per dropback, about +0.038 above the 0.132 that QBs paid his cap share (18.1%) usually produce, so he is marked worth it. This is a measure of efficiency relative to his salary, not a full evaluation of his contract.
  - `SELECT season, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Dak Prescott', 2025]`
  - `SELECT season, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it FROM qb_contract_value WHERE passer_name LIKE %s AND season = %s` params `['%Prescott%', 2025]`
- Run `20261018-201603`: ✅ PASS, 5.4 s, $0.00061, 2 queries
  > Yes, by this measure. Dak Prescott's 2025 season (D.Prescott, DAL, 654 dropbacks, a finished season) had an EPA per dropback of 0.169 against an expected 0.132 for his cap share of 18.1% (cap number 50.5). That puts him 0.038 above expectation, so the model counts him as worth it.
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Dak Prescott', 2025]`
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, is_cap_hit_for_team, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%prescott%', 2025]`
- Run `20261018-202158`: ✅ PASS, 3.3 s, $0.00038, 1 query
  > Yes, by this measure. Dak Prescott's 2025 season (complete, Dallas) came in at 0.169 EPA per dropback, about 0.038 above the 0.132 that QBs paying his cap share (18.1% of the cap, a $50.5M hit) usually produce, so he was flagged as worth it.
  - `SELECT passer_name, season, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Prescott%', 2025]`

**GLM-5.3 Flash**: 2/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 4.1 s, $0.00074, 2 queries
  > We don't have the data to give an accurate answer to that.
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE '%' || %s || '%' AND season = 2025` params `['Prescott']`
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name LIKE %s AND season = 2025` params `['%Prescott%']`
- Run `20261018-201603`: ✅ PASS, 3.8 s, $0.00066, 1 query
  > Yes — in 2025, Dak Prescott's cap hit of about $50.5 million was 18.1% of the league salary cap, and he posted 0.169 EPA per dropback over 654 dropbacks, about 0.04 EPA per dropback above what QBs paid that share usually produce. That makes 2025 a "worth it" season for him, though a modest one by that measure.
  - `SELECT season, passer_name, team, dropbacks, epa_per_dropback, cap_number, cap_share, epa_over_expected, worth_it, is_season_complete, is_cap_hit_for_team FROM qb_contract_value WHERE season = 2025 AND passer_name ILIKE %s` params `['%Prescott%']`
- Run `20261018-202158`: ✅ PASS, 4.7 s, $0.00044, 1 query
  > Yes. Dak Prescott's 2025 Cowboys season is marked complete, and he was classified as "worth it": he posted 0.169 EPA per dropback over 654 dropbacks while carrying an 18.1% cap share (about $50.5 million), above the 0.132 expected for QBs paid that much, for a +0.038 EPA per dropback over expected.
  - `SELECT season, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE season = 2025 AND passer_name ILIKE %s` params `['%Prescott%']`

### 4. Which quarterback had the biggest cap hit as a share of the salary cap in 2025?

*`highest_cap_share_2025`. Expected: names **D.Prescott**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.7 s, $0.00030, 1 query
  > In 2025, Dak Prescott (DAL) had the biggest cap hit as a share of the salary cap, at about 18.1% ($50.5 million). The 2025 season is complete, so this figure is final.
  - `SELECT passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2025 AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 5`
- Run `20261018-201603`: ✅ PASS, 3.3 s, $0.00030, 1 query
  > Dak Prescott had the biggest 2025 cap hit as a share of the salary cap, at about 18.1% ($50.5 million) for Dallas. The 2025 season is complete, so this is a final figure. Matthew Stafford (about 17.0%) and Joe Burrow (about 16.5%) were next.
  - `SELECT passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2025 AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 5`
- Run `20261018-202158`: ✅ PASS, 3.5 s, $0.00031, 1 query
  > Dak Prescott had the biggest cap hit as a share of the salary cap in 2025, at about 18.1% ($50.5 million) for the Dallas Cowboys. The 2025 season is complete, so this is a final figure.
  - `SELECT passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = %s AND cap_share IS NOT NULL ORDER BY cap_share DESC LIMIT 5` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.4 s, $0.00045, 1 query
  > Dak Prescott (Dallas) had the largest 2025 cap hit, at about $50.5 million — 18.1% of the salary cap. Note that 2025 is treated as in progress in this data, though cap share figures don't change with games played.
  - `SELECT passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE season = 2025 ORDER BY cap_share DESC NULLS LAST LIMIT 1`
- Run `20261018-201603`: ✅ PASS, 1.1 s, $0.00041, 1 query
  > In 2025, Dak Prescott had the biggest cap hit: about $50.5 million with Dallas, or 18.1% of the salary cap. Matthew Stafford was next at 17.0%.
  - `SELECT passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE season = 2025 ORDER BY cap_share DESC NULLS LAST LIMIT 5;`
- Run `20261018-202158`: ✅ PASS, 1.6 s, $0.00035, 1 query
  > Dak Prescott had the biggest 2025 cap hit: $50.5 million for Dallas, about 18.1% of the salary cap.
  - `SELECT passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE season = 2025 ORDER BY cap_share DESC NULLS LAST LIMIT 1`

### 5. What share of the salary cap was Jordan Love's cap hit in 2025?

*`love_cap_share_2025`. Expected: states **10.6%** (at least 1 decimal).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.5 s, $0.00029, 1 query
  > Jordan Love's 2025 cap hit with the Packers was $29.7 million, which is about 10.6% of the league salary cap. The 2025 season is complete, so this is a final figure.
  - `SELECT passer_name, team, season, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2025 AND passer_name ILIKE %s` params `['%Love%']`
- Run `20261018-201603`: ✅ PASS, 3.3 s, $0.00023, 1 query
  > Jordan Love's 2025 cap hit was $29.7 million, which is about 10.6% of the league salary cap (cap share 0.1065). This is a finished season, and the cap hit is for Green Bay, the team that played him.
  - `SELECT season, passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Love%', 2025]`
- Run `20261018-202158`: ✅ PASS, 3.8 s, $0.00028, 1 query
  > Jordan Love's 2025 cap hit with the Green Bay Packers was $29.7 million, about 10.6% of the league salary cap. The 2025 season is complete, so this is a final figure.
  - `SELECT season, passer_name, team, cap_number, cap_share, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Love%', 2025]`

**GLM-5.3 Flash**: 2/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.6 s, $0.00064, 2 queries
  > In 2025, Jordan Love's cap hit was about $29.7 million, which was about 10.6% of the league salary cap for Green Bay.
  - `SELECT cap_number, cap_share, team, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Jordan Love', 2025]`
  - `SELECT passer_name, passer_id, cap_number, cap_share, team, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Love%']`
- Run `20261018-201603`: ✅ PASS, 9.5 s, $0.00059, 2 queries
  > In 2025, Jordan Love's cap hit was about $29.7 million, which was 10.6% of that season's salary cap (the season is marked complete).
  - `SELECT passer_name, season, cap_number, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Jordan Love', 2025]`
  - `SELECT passer_name, season, team, cap_number, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s ORDER BY season` params `['%Love%']`
- Run `20261018-202158`: ❌ FAIL (no answer), 22.7 s, $0.00070, 3 queries, reason: query budget used up
  > We don't have the data to give an accurate answer to that.
  - `SELECT passer_name, season, team, cap_number, cap_share, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Jordan Love', 2025]`
  - `SELECT passer_name, season, team, cap_number, cap_share, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s ORDER BY season` params `['Jordan Love']`
  - `SELECT DISTINCT passer_name, passer_id FROM qb_contract_value WHERE passer_name ILIKE %s ORDER BY passer_name` params `['%Love%']`

### 6. How many quarterbacks were worth their contract in 2025?

*`worth_it_count_2025`. Expected: states **19**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 3.0 s, $0.00028, 1 query
  > In 2025, 19 of the 38 quarterbacks with a score were worth their contract, meaning they played better than the cap share they were paid usually produces. All 2025 seasons in the data are complete, so these figures are final.
  - `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(worth_it) AS scored_qbs, COUNT(*) AS total_rows, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = %s` params `[2025]`
- Run `20261018-201603`: ✅ PASS, 4.4 s, $0.00033, 1 query
  > In 2025, 19 of the 38 quarterbacks who received a score were worth their contract, meaning they played better than the share of the salary cap they were paid usually produces. The 2025 season is complete, so these are final numbers.
  - `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_qbs, COUNT(worth_it) AS scored_qbs, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = 2025`
- Run `20261018-202158`: ✅ PASS, 2.7 s, $0.00031, 1 query
  > In 2025, 19 of the 38 quarterbacks with a scored season were worth their contract, meaning their EPA per dropback beat what QBs paying that share of the salary cap usually produce. The 2025 season is complete, so these are final numbers.
  - `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(worth_it) AS scored_count, BOOL_AND(is_season_complete) AS all_complete FROM qb_contract_value WHERE season = %s` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.2 s, $0.00039, 1 query
  > 19 quarterbacks were worth their contract in 2025, meaning they produced more EPA per dropback than QBs paid the same share of the salary cap typically do. Note that 2025 is treated as an in-progress season in this data, so those scores are estimates.
  - `SELECT COUNT(*) FROM qb_contract_value WHERE season = 2025 AND worth_it`
- Run `20261018-201603`: ✅ PASS, 15.1 s, $0.00055, 2 queries
  > In the 2025 season, 19 of the 38 scored quarterback seasons were worth their contract, meaning those QBs produced more EPA per dropback than QBs paid the same share of the salary cap usually do.
  - `SELECT COUNT(*) AS total_scored, SUM(CASE WHEN worth_it THEN 1 ELSE 0 END) AS worth_it_count FROM qb_contract_value WHERE season = 2025 AND worth_it IS NOT NULL`
  - `SELECT is_season_complete FROM qb_contract_value WHERE season = 2025 LIMIT 1`
- Run `20261018-202158`: ✅ PASS, 19.0 s, $0.00013, 1 query
  > 19 of the 38 scored quarterbacks were worth their contract in 2025. Note that the 2025 season is still in progress, so those numbers are estimates based on the season so far.
  - `SELECT COUNT(*) FILTER (WHERE worth_it) AS worth_it_count, COUNT(*) AS total_scored, BOOL_OR(NOT is_season_complete) AS season_in_progress FROM qb_contract_value WHERE season = 2025 AND is_cap_hit_for_team`

### 7. How far above expected for his cap share was Patrick Mahomes in 2018?

*`mahomes_2018`. Expected: states **+0.345** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.8 s, $0.00048, 2 queries
  > Patrick Mahomes in 2018 (listed as P.Mahomes) finished 0.34 EPA per dropback above expected for his cap share. His cap share was about 2.1% of the cap, where QBs usually produce about 0.015 EPA per dropback, so he was worth it.
  - `SELECT passer_name, season, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Patrick Mahomes', 2018]`
  - `SELECT passer_name, season, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE passer_name LIKE %s AND season = %s` params `['%Mahomes%', 2018]`
- Run `20261018-201603`: ✅ PASS, 4.7 s, $0.00055, 2 queries
  > Patrick Mahomes in 2018 (listed as P.Mahomes) finished 0.34 EPA per dropback above what a QB paying his cap share (about 2.1% of the cap) usually produces. His expected figure was about 0.015 EPA per dropback, so his epa_over_expected is +0.345.
  - `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name = %s AND season = 2018` params `['Patrick Mahomes']`
  - `SELECT passer_name, season, team, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name LIKE %s AND season = 2018` params `['%Mahomes%']`
- Run `20261018-202158`: ✅ PASS, 2.8 s, $0.00034, 1 query
  > Patrick Mahomes in 2018 (KC) finished 0.34 EPA per dropback above expected for his cap share, based on 0.36 actual versus 0.01 expected. That season is complete, so the figure is final.
  - `SELECT passer_name, season, team, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Mahomes%', 2018]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 14.2 s, $0.00045, 2 queries
  > In 2018, Patrick Mahomes produced 0.36 EPA per dropback on about 2.1% of the salary cap, where QBs paid that share typically produce about 0.015 — so he was about +0.34 EPA per dropback above expected, one of the best value seasons on record.
  - `SELECT epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Patrick Mahomes', 2018]`
  - `SELECT epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share, cap_number FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Mahomes%', 2018]`
- Run `20261018-201603`: ✅ PASS, 15.5 s, $0.00067, 3 queries
  > In 2018, Patrick Mahomes (listed as P.Mahomes) was about +0.34 EPA per dropback above what QBs paid his share of the cap (2.1%) usually produce — his 0.36 EPA per dropback versus an expected 0.015 — making that season clearly worth his cap hit.
  - `SELECT passer_name, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, cap_share, worth_it FROM qb_contract_value WHERE season = %s AND passer_name = 'Patrick Mahomes'` params `['2018']`
  - `SELECT passer_name, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, cap_share, worth_it FROM qb_contract_value WHERE season = %s AND passer_name = %s` params `[2018, 'Patrick Mahomes']`
  - `SELECT passer_name, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, cap_share, worth_it FROM qb_contract_value WHERE season = %s AND passer_name ILIKE %s` params `[2018, '%Mahomes%']`
- Run `20261018-202158`: ✅ PASS, 19.3 s, $0.00043, 3 queries
  > In 2018 Patrick Mahomes produced 0.360 EPA per dropback, about +0.34 above the 0.015 expected from a QB on roughly 2.1% of the cap — the second-best value season in the data and an MVP year on a rookie deal.
  - `SELECT epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Patrick Mahomes', 2018]`
  - `SELECT passer_id, passer_name, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share, is_season_complete FROM qb_contract_value WHERE season = %s AND passer_name LIKE %s` params `[2018, 'Mahomes']`
  - `SELECT season, passer_id, passer_name, epa_over_expected, epa_per_dropback, expected_epa_per_dropback, cap_share FROM qb_contract_value WHERE passer_name LIKE %s ORDER BY season` params `['%Mahomes%']`

### 8. Which quarterback had the highest EPA per dropback in 2025?

*`best_epa_2025`. Expected: names **D.Maye**.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.8 s, $0.00030, 1 query
  > Drake Maye of the New England Patriots had the highest EPA per dropback among 2025 quarterbacks, at 0.316 over 601 dropbacks. The 2025 season is complete, so this is a final number.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2025 AND epa_per_dropback IS NOT NULL ORDER BY epa_per_dropback DESC LIMIT 5`
- Run `20261018-201603`: ✅ PASS, 3.5 s, $0.00029, 1 query
  > Drake Maye (listed as D.Maye) of the New England Patriots had the highest EPA per dropback in 2025, at 0.32 over 601 dropbacks. The 2025 season is complete, so this is a final number.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC NULLS LAST LIMIT 5` params `[2025]`
- Run `20261018-202158`: ✅ PASS, 3.5 s, $0.00028, 1 query
  > D.Maye of New England had the highest EPA per dropback in 2025, at about 0.316 across 601 dropbacks. The 2025 season is complete, so this is a final figure.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC LIMIT 1` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 3.2 s, $0.00051, 1 query
  > Drake Maye of the New England Patriots had the highest EPA per dropback in 2025, at 0.32 over 601 dropbacks (the season is complete, so this is a final figure).
  - `SELECT passer_name, team, epa_per_dropback, dropbacks, is_season_complete, season_progress FROM qb_season_epa WHERE season = 2025 ORDER BY epa_per_dropback DESC LIMIT 1`
- Run `20261018-201603`: ✅ PASS, 2.9 s, $0.00032, 1 query
  > Drake Maye of the Patriots had the highest EPA per dropback in 2025 at roughly 0.32, with 601 dropbacks, ahead of Jordan Love (0.26) and Matthew Stafford (0.22). That season shows as complete in the data, so it's a final figure rather than an estimate.
  - `SELECT passer_name, team, epa_per_dropback, dropbacks, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC LIMIT 3` params `['2025']`
- Run `20261018-202158`: ✅ PASS, 3.0 s, $0.00033, 1 query
  > Drake Maye of New England had the highest EPA per dropback in 2025 at about 0.316, ahead of Jordan Love (0.259) and Matthew Stafford (0.223).
  - `SELECT passer_name, team, epa_per_dropback, dropbacks, is_season_complete FROM qb_season_epa WHERE season = %s ORDER BY epa_per_dropback DESC LIMIT 5` params `[2025]`

### 9. What was Josh Allen's EPA per dropback in 2024?

*`allen_epa_2024`. Expected: states **+0.304** (at least 2 decimals).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 3.4 s, $0.00033, 1 query
  > Josh Allen's 2024 EPA per dropback was about 0.30 (0.304 over 539 dropbacks with the Bills). The 2024 season is complete. I matched him by the name "J.Allen" and team BUF, since the table keys on passer ID and I did not check the ID directly.
  - `SELECT passer_name, team, season, epa_per_dropback, dropbacks, is_season_complete FROM qb_season_epa WHERE passer_name = %s AND season = 2024` params `['J.Allen']`
- Run `20261018-201603`: ✅ PASS, 4.5 s, $0.00033, 1 query
  > Josh Allen's EPA per dropback in 2024 was about 0.30 (0.304), over 539 dropbacks for Buffalo. The 2024 season is complete. The table lists him as "J.Allen," so I matched him by team and season, and that row is the Bills' starter.
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_name ILIKE %s AND season = %s` params `['%Allen%', 2024]`
- Run `20261018-202158`: ✅ PASS, 3.5 s, $0.00034, 1 query
  > Josh Allen's 2024 EPA per dropback was 0.30 (0.304 unrounded) over 539 dropbacks for Buffalo, and the season is complete. The table lists him only as "J.Allen," so I matched him by the BUF team and the 2024 season.
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE passer_name LIKE %s AND season = %s` params `['%Allen%', 2024]`

**GLM-5.3 Flash**: 2/3 runs passed

- Run `20261018-201055`: ✅ PASS, 3.7 s, $0.00068, 1 query
  > Josh Allen posted an EPA per dropback of 0.304 in 2024 (539 dropbacks for Buffalo in a completed season).
  - `SELECT qb_season_key, passer_id, passer_name, team, dropbacks, epa_per_dropback, is_season_complete FROM qb_season_epa WHERE season = 2024 AND passer_name ILIKE %s` params `['%Allen%']`
- Run `20261018-201603`: ✅ PASS, 2.6 s, $0.00063, 2 queries
  > Josh Allen (listed as "J.Allen", BUF) had an EPA per dropback of 0.304 in 2024.
  - `SELECT epa_per_dropback FROM qb_season_epa WHERE passer_name = %s AND season = %s` params `['Josh Allen', 2024]`
  - `SELECT passer_id, passer_name, team, epa_per_dropback FROM qb_season_epa WHERE passer_name ILIKE %s AND season = %s` params `['%Allen%', 2024]`
- Run `20261018-202158`: ❌ FAIL (no answer), 3.2 s, $0.00082, 3 queries, reason: query budget used up
  > We don't have the data to give an accurate answer to that.
  - `SELECT epa_per_dropback FROM qb_season_epa WHERE passer_name ILIKE 'Josh Allen' AND season = 2024` params `['Josh Allen']`
  - `SELECT epa_per_dropback FROM qb_season_epa WHERE passer_name ILIKE %s AND season = 2024` params `['Josh Allen']`
  - `SELECT passer_name, epa_per_dropback FROM qb_season_epa WHERE season = 2024 AND passer_id LIKE 'allen%'`

### 10. Which team had the best net EPA per play in 2025?

*`best_net_2025`. Expected: names **LA** (Los Angeles Rams).*

**Claude Haiku 5.5**: 2/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.7 s, $0.00030, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at about +0.207 (0.145 offense, -0.062 defense). The New England Patriots were close behind at about +0.203.
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = 2025 AND net_epa_per_play IS NOT NULL ORDER BY net_epa_per_play DESC LIMIT 3`
- Run `20261018-201603`: ❌ FAIL (no answer), 2.7 s, $0.00032, 2 queries, reason: numbers not in any result: 0.062
  > We don't have the data to give an accurate answer to that.
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = %s AND net_epa_per_play IS NOT NULL ORDER BY net_epa_per_play DESC LIMIT 3` params `[2025]`
  - `SELECT is_season_complete FROM qb_season_epa WHERE season = %s LIMIT 1` params `[2025]`
- Run `20261018-202158`: ✅ PASS, 2.9 s, $0.00031, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at about 0.207 (offense 0.145, defense -0.062). The New England Patriots were close behind at about 0.203, and the Buffalo Bills were third at about 0.156.
  - `SELECT team, team_name, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = %s ORDER BY net_epa_per_play DESC NULLS LAST LIMIT 3` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 6.2 s, $0.00069, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at 0.21 per play, combining 0.14 offense with -0.06 defense. Note the 2025 season appears to still be in progress in this data, so treat that figure as an estimate.
  - `SELECT team, team_name, season, net_epa_per_play, off_epa_per_play, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 1`
- Run `20261018-201603`: ✅ PASS, 5.2 s, $0.00099, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025, at 0.21.
  - `SELECT team, team_name, net_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 1`
- Run `20261018-202158`: ✅ PASS, 3.3 s, $0.00071, 1 query
  > The Los Angeles Rams had the best net EPA per play in 2025 at about 0.207.
  - `SELECT team_name, team, net_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY net_epa_per_play DESC LIMIT 1`

### 11. Which team had the best defense by EPA allowed per play in 2025?

*`best_defense_2025`. Expected: names **HOU** (Houston Texans).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.4 s, $0.00056, 2 queries
  > The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.131 across 977 defensive plays. The Seattle Seahawks were next at -0.118. The 2025 season is marked complete in the QB data, so these figures are final.
  - `SELECT team, team_name, def_epa_per_play, def_plays, def_success_rate FROM team_season_epa WHERE season = %s AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 5` params `[2025]`
  - `SELECT is_season_complete, COUNT(*) FROM qb_season_epa WHERE season = %s GROUP BY is_season_complete` params `[2025]`
- Run `20261018-201603`: ✅ PASS, 4.5 s, $0.00053, 2 queries
  > The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.131 across 977 plays. The Seattle Seahawks (-0.118) and Jacksonville Jaguars (-0.104) were next. The team table doesn't flag whether 2025 is a finished season, so I can't confirm these are final numbers.
  - `SELECT team, team_name, def_epa_per_play, def_plays, is_season_complete FROM team_season_epa t LEFT JOIN _publications p ON false WHERE season = 2025 AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 3`
  - `SELECT team, team_name, def_epa_per_play, def_plays FROM team_season_epa WHERE season = 2025 AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 3`
- Run `20261018-202158`: ✅ PASS, 2.7 s, $0.00032, 2 queries
  > The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.13 EPA per play across 977 plays. The Seattle Seahawks (-0.12) and Jacksonville Jaguars (-0.10) followed.
  - `SELECT team, team_name, def_epa_per_play, def_plays, net_epa_per_play FROM team_season_epa WHERE season = %s AND def_epa_per_play IS NOT NULL ORDER BY def_epa_per_play ASC LIMIT 3` params `[2025]`
  - `SELECT is_season_complete FROM qb_season_epa WHERE season = %s LIMIT 1` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.3 s, $0.00054, 2 queries
  > The Houston Texans had the best defense in 2025, allowing about -0.13 EPA per play, just ahead of the Seattle Seahawks (-0.12) and Jacksonville Jaguars (-0.10). Note that if the 2025 season is still in progress, these numbers are estimates.
  - `SELECT team, team_name, def_epa_per_play, is_season_complete FROM team_season_epa WHERE season = 2025 ORDER BY def_epa_per_play ASC LIMIT 3`
  - `SELECT team, team_name, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY def_epa_per_play ASC LIMIT 3`
- Run `20261018-201603`: ✅ PASS, 4.1 s, $0.00035, 1 query
  > The Houston Texans had the best defense by EPA allowed per play in 2025, at -0.131 per play.
  - `SELECT team, team_name, def_epa_per_play FROM team_season_epa WHERE season = 2025 ORDER BY def_epa_per_play ASC LIMIT 1`
- Run `20261018-202158`: ✅ PASS, 2.3 s, $0.00034, 1 query
  > The Houston Texans had the best defense in 2025, allowing -0.131 EPA per play, which edged out the Seattle Seahawks (-0.118) and the Jacksonville Jaguars (-0.104).
  - `SELECT team, team_name, def_epa_per_play, def_success_rate FROM team_season_epa WHERE season = 2025 ORDER BY def_epa_per_play ASC LIMIT 3`

### 12. Which team went for it most often on fourth-and-short in 2025?

*`go_for_it_leader_2025`. Expected: names **IND** (Indianapolis Colts).*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.7 s, $0.00028, 1 query
  > The Indianapolis Colts (IND) went for it most often on fourth-and-short in 2025, at 84.2% (16 go-for-its in 19 decisions).
  - `SELECT team, team_name, go_pct, went_for_it, fourth_downs FROM team_fourth_down WHERE season = 2025 AND go_pct IS NOT NULL ORDER BY go_pct DESC LIMIT 1`
- Run `20261018-201603`: ✅ PASS, 3.0 s, $0.00029, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% (16 of 19 decisions). The Buffalo Bills were next at 82.4% (14 of 17).
  - `SELECT team, team_name, go_pct, went_for_it, fourth_downs FROM team_fourth_down WHERE season = %s AND go_pct IS NOT NULL ORDER BY go_pct DESC, went_for_it DESC LIMIT 3` params `[2025]`
- Run `20261018-202158`: ✅ PASS, 3.1 s, $0.00034, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025: 16 times in 19 decisions, a 84.2% go rate. They also had the most go-for-it attempts of any team, ahead of the Bills (14) and Cowboys (13).
  - `SELECT team, team_name, fourth_downs, went_for_it, go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC NULLS LAST, went_for_it DESC LIMIT 3` params `[2025]`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.4 s, $0.00036, 1 query
  > The Indianapolis Colts were the most aggressive team on fourth-and-short in 2025, going for it on 84.2% of such decisions (16 of 19). The Bills were close behind at 82.4%, with the Cowboys third at 76.5%.
  - `SELECT team, team_name, fourth_downs, went_for_it, go_pct FROM team_fourth_down WHERE season = 2025 ORDER BY go_pct DESC LIMIT 5`
- Run `20261018-201603`: ✅ PASS, 3.0 s, $0.00066, 1 query
  > The Indianapolis Colts were the most aggressive, going for it on 84.2% of their fourth-and-short decisions (16 of 19), ahead of the Buffalo Bills at 82.4% and the Dallas Cowboys at 76.5%. Note these are 2025 regular-season figures from a season that may still be in progress.
  - `SELECT team, team_name, fourth_downs, went_for_it, go_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC LIMIT 3` params `[2025]`
- Run `20261018-202158`: ✅ PASS, 3.7 s, $0.00064, 1 query
  > The Indianapolis Colts went for it most often on fourth-and-short in 2025, at 84.2% (16 of 19 decisions in competitive game states). The Buffalo Bills were close behind at 82.4%.
  - `SELECT team, team_name, fourth_downs, went_for_it, go_pct, conversion_pct FROM team_fourth_down WHERE season = %s ORDER BY go_pct DESC LIMIT 3` params `[2025]`

### 13. How often did NFL teams go for it on fourth-and-short in competitive games in 2025?

*`league_go_rate_2025`. Expected: states **61.8%** (at least 1 decimal).*

**Claude Haiku 5.5**: 1/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 4.3 s, $0.00047, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / SUM(fourth_downs), 1) AS league_go_pct, COUNT(*) AS team_rows FROM team_fourth_down WHERE season = %s` params `[2025]`
- Run `20261018-201603`: ✅ PASS, 3.8 s, $0.00032, 1 query
  > In 2025, NFL teams went for it on 352 of 570 fourth-and-short decisions in competitive games, a league-wide rate of 61.8%. This table has no completeness flag, so I can't confirm whether the 2025 season is finished.
  - `SELECT season, SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS league_go_pct FROM team_fourth_down WHERE season = %s GROUP BY season` params `[2025]`
- Run `20261018-202158`: ❌ FAIL (no answer), 3.8 s, $0.00034, 1 query, reason: numbers not in any result: 90
  > We don't have the data to give an accurate answer to that.
  - `SELECT SUM(went_for_it) AS went_for_it, SUM(fourth_downs) AS fourth_downs, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs), 0), 1) AS league_go_pct FROM team_fourth_down WHERE season = %s` params `[2025]`

**GLM-5.3 Flash**: 0/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 15.5 s, $0.00049, 2 queries
  > We don't have the data to give an accurate answer to that.
  - `SELECT SUM(went_for_it) AS went, SUM(fourth_downs) AS decisions, SUM(converted) AS conv, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs),0), 1) AS league_go_pct, MAX(is_season_complete IS NOT NULL) AS dummy FROM team_fourth_down WHERE season = 2025`
  - `SELECT SUM(went_for_it) AS went, SUM(fourth_downs) AS decisions, ROUND(100.0 * SUM(went_for_it) / NULLIF(SUM(fourth_downs),0), 1) AS league_go_pct FROM team_fourth_down WHERE season = 2025`
- Run `20261018-201603`: ❌ FAIL (no answer), 1.9 s, $0.00039, 1 query, reason: numbers not in any result: 90, 26.8, 2015
  > We don't have the data to give an accurate answer to that.
  - `SELECT round(100.0*sum(went_for_it)/sum(fourth_downs),1) AS go_rate, round(100.0*sum(converted)/sum(went_for_it),1) AS conv_rate, sum(fourth_downs) AS decisions, count(*) AS teams FROM team_fourth_down WHERE season = %s` params `[2025]`
- Run `20261018-202158`: ❌ FAIL (no answer), 1.2 s, $0.00035, 1 query, reason: numbers not in any result: 90
  > We don't have the data to give an accurate answer to that.
  - `select round(100*sum(went_for_it)::numeric/sum(fourth_downs),1) as go_pct, min(season) from team_fourth_down where season = 2025`

### 14. Across all games since 2015 that had a spread, how often did the home team cover?

*`home_cover_share`. Expected: states **47.7%** (at least 1 decimal).*

**Claude Haiku 5.5**: 0/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 5.2 s, $0.00042, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread FROM game_results_vs_spread WHERE season >= %s AND spread_line IS NOT NULL` params `['home', 'away', 'push', 2015]`
- Run `20261018-201603`: ❌ FAIL (no answer), 6.1 s, $0.00087, 2 queries, reason: numbers not in any result: 3026
  > We don't have the data to give an accurate answer to that.
  - `SELECT COUNT(*) FILTER (WHERE ats_result = 'home') AS home_covers, COUNT(*) FILTER (WHERE ats_result = 'away') AS away_covers, COUNT(*) FILTER (WHERE ats_result = 'push') AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = 'home') / NULLIF(COUNT(*) FILTER (WHERE ats_result IN ('home','away')), 0), 1) AS home_cover_pct_excl_push FROM game_results_vs_spread WHERE season >= 2015 AND game_type = 'REG' OR (season >= 2015 AND game_type <> 'REG')`
  - `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IN (%s, %s)), 0), 1) AS home_cover_pct_excl_push FROM game_results_vs_spread WHERE season >= %s` params `['home', 'away', 'push', 'home', 'home', 'away', 'home', '2015']`
- Run `20261018-202158`: ❌ FAIL (no answer), 6.4 s, $0.00091, 2 queries, reason: numbers not in any result: 3026
  > We don't have the data to give an accurate answer to that.
  - `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IN (%s, %s)), 0), 1) AS home_cover_pct_excl_pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct_all FROM game_results_vs_spread WHERE season >= %s" params=["home","away","push","home","home","away","home","2015"]` params `['home', 'away', 'push', 'home', 'home', 'away', 'home', '2015']`
  - `SELECT COUNT(*) FILTER (WHERE ats_result = %s) AS home_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS away_covers, COUNT(*) FILTER (WHERE ats_result = %s) AS pushes, COUNT(*) FILTER (WHERE ats_result IS NOT NULL) AS games_with_spread, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IN (%s, %s)), 0), 1) AS home_cover_pct_excl_pushes, ROUND(100.0 * COUNT(*) FILTER (WHERE ats_result = %s) / NULLIF(COUNT(*) FILTER (WHERE ats_result IS NOT NULL), 0), 1) AS home_cover_pct_all FROM game_results_vs_spread WHERE season >= 2015` params `['home', 'away', 'push', 'home', 'home', 'away', 'home']`

**GLM-5.3 Flash**: 2/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 7.5 s, $0.00103, 3 queries
  > We don't have the data to give an accurate answer to that.
  - `SELECT count(*) AS total_games, count(*) FILTER (WHERE ats_result = 'home') AS home_covers, count(*) FILTER (WHERE ats_result = 'away') AS away_covers, count(*) FILTER (WHERE ats_result = 'push') AS pushes, round(100.0 * count(*) FILTER (WHERE ats_result = 'home') / count(*), 1) AS home_cover_pct FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL`
  - `SELECT count(*) AS total_games, count(*) FILTER (WHERE ats_result = %s) AS home_covers, count(*) FILTER (WHERE ats_result <> %s) AS non_home_covers, round(100.0 * count(*) FILTER (WHERE ats_result = %s) / count(*), 1) AS home_cover_pct FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL` params `['home']`
  - `SELECT count(*) AS total_games, count(*) FILTER (WHERE ats_result = %s) AS home_covers, round(100.0 * count(*) FILTER (WHERE ats_result = %s) / count(*), 1) AS home_cover_pct FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL` params `['home', 'home', 'home']`
- Run `20261018-201603`: ✅ PASS, 2.0 s, $0.00060, 2 queries
  > Across all games since 2015 with a spread, the home team covered about 47.7% of the time (0.477).
  - `SELECT count(*) FILTER (WHERE ats_result='home')::numeric / count(*) AS home_cover_rate FROM game_results_vs_spread WHERE season >= 2015 AND ats_result IS NOT NULL`
  - `SELECT count(*) FILTER (WHERE ats_result=%s)::numeric / count(*) AS home_cover_rate FROM game_results_vs_spread WHERE season >= 2015 AND ats_result IS NOT NULL` params `['home']`
- Run `20261018-202158`: ✅ PASS, 2.1 s, $0.00059, 2 queries
  > Since 2015, there were 3,107 games with a spread, and the home team covered in 1,482 of them — about 47.7% of the time. So despite home-field advantage, home teams covered the spread slightly less often than they lost it.
  - `SELECT count(*) FILTER (WHERE ats_result='home')::float / count(*) FILTER (WHERE ats_result IS NOT NULL) AS home_rate, count(*) FILTER (WHERE ats_result='home'), count(*) FILTER (WHERE ats_result IS NOT NULL) FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL`
  - `SELECT count(*) FILTER (WHERE ats_result = %s)::float / count(*)::float AS home_rate, count(*) FILTER (WHERE ats_result = %s) AS home_covers, count(*) AS games FROM game_results_vs_spread WHERE season >= 2015 AND spread_line IS NOT NULL` params `['home', 'home']`

### 15. Who has been the best value quarterback for his cap share so far in 2026?

*`best_value_2026_so_far`. Expected: names **B.Purdy**; says the season is still in progress.*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 5.7 s, $0.00042, 1 query
  > So far in 2026, Brock Purdy (SF) ranks first on value, with an EPA per dropback of 0.41 on a cap share of about 7.9%, which is +0.36 above what QBs at that share usually produce. Those are estimates, since the 2026 season is still in progress and Purdy has 156 dropbacks. Lamar Jackson (BAL, +0.29) and Caleb Williams (CHI, +0.29) are next, with Purdy's lead holding in the current data.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, cap_share, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 5`
- Run `20261018-201603`: ✅ PASS, 3.6 s, $0.00043, 1 query
  > So far in 2026, Brock Purdy (SF) ranks first for value, at 0.41 EPA per dropback against 0.06 expected for his 7.9% cap share, or +0.36 over expected. Lamar Jackson (BAL) is second at +0.29, and Caleb Williams (CHI) third at +0.29. The 2026 season is still in progress, so these scores are estimates.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, is_season_complete FROM qb_contract_value WHERE season = %s AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 5` params `[2026]`
- Run `20261018-202158`: ✅ PASS, 3.7 s, $0.00044, 1 query
  > So far in 2026, Brock Purdy (SF) ranks as the best value for his cap share, at +0.36 EPA per dropback above expected on a 7.9% cap share. Lamar Jackson (BAL, +0.29) and Caleb Williams (CHI, +0.29) are next. These are estimates because the 2026 season is still in progress.
  - `SELECT passer_name, team, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 5`

**GLM-5.3 Flash**: 2/3 runs passed

- Run `20261018-201055`: ❌ FAIL (no answer), 12.7 s, $0.00044, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT qb_season_key, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, epa_over_expected, worth_it FROM qb_contract_value WHERE qb_season_key LIKE %s ORDER BY epa_over_expected DESC NULLS LAST` params `['%2026']`
- Run `20261018-201603`: ✅ PASS, 3.4 s, $0.00078, 1 query
  > So far in 2026 the best value is Brock Purdy of San Francisco: his 0.413 EPA per dropback is about +0.36 above what QBs paid his roughly 7.9% cap share usually produce, the highest epa_over_expected in the league. Lamar Jackson (+0.29) and Caleb Williams (+0.29) are next. Since the 2026 season is still in progress, these numbers are estimates and could shift.
  - `SELECT passer_name, team, dropbacks, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE season = 2026 AND epa_over_expected IS NOT NULL ORDER BY epa_over_expected DESC LIMIT 10`
- Run `20261018-202158`: ✅ PASS, 7.2 s, $0.00085, 1 query
  > Through the in-progress 2026 season, Brock Purdy has been the best value for his cap share: he's producing about 0.36 EPA per dropback above what QBs paid a similar share (about 7.9% of the cap) usually do, ahead of Lamar Jackson (+0.29) and Caleb Williams (+0.29). Since the season is still underway, these numbers are estimates.
  - `SELECT passer_name, team, dropbacks, epa_per_dropback, cap_share, expected_epa_per_dropback, epa_over_expected, is_cap_hit_for_team, is_season_complete FROM qb_contract_value WHERE season = 2026 ORDER BY epa_over_expected DESC NULLS LAST LIMIT 10`

### 16. How many touchdowns did Patrick Mahomes throw in 2024?

*`mahomes_touchdowns`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.1 s, $0.00015, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.5 s, $0.00015, 0 queries, reason: model: The tables cover QB efficiency per season (EPA per dropback, success rate, dropbacks, scrambles), QB contract value, game results against the spread, fourth-down decisions, and team EPA. None of them record passing touchdowns, so Patrick Mahomes's 2024 touchdown total cannot be answered from this data.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.4 s, $0.00015, 0 queries, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, dropbacks, scrambles), cap figures, game results against the spread, fourth-down decisions, and team EPA. None of them record touchdown passes, so Patrick Mahomes' 2024 touchdown total can't be answered from this data.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.4 s, $0.00067, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 3.1 s, $0.00047, 0 queries, reason: model: The available tables (QB EPA per dropback/success rate, QB contract value, team EPA, fourth-down decisions, and games vs. the spread) don't include passing touchdowns, so Mahomes' 2024 touchdown count isn't in this database.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 2.8 s, $0.00017, 0 queries, reason: model: The available tables only cover QB EPA per dropback, success rate, dropbacks, scrambles, and cap data — no touchdown counts for any quarterback or season.
  > We don't have the data to give an accurate answer to that.

### 17. Who will win the Super Bowl this season?

*`super_bowl_pick`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.8 s, $0.00013, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.6 s, $0.00014, 0 queries, reason: model: The tables cover regular-season results, betting spreads, QB efficiency, cap values, and team efficiency. They contain no playoff or Super Bowl results and no forecasts, so they can't say who will win this season's Super Bowl.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.9 s, $0.00018, 0 queries, reason: model: The tables cover past game results against the spread, QB efficiency and contract value, fourth-down decisions, and regular-season team EPA. They contain no playoff bracket, no Super Bowl forecast, and no data that could predict this season's Super Bowl winner.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 0.8 s, $0.00019, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 2.7 s, $0.00022, 0 queries, reason: model: The tables cover regular-season stats (EPA, fourth downs, ATS results, QB contracts) but contain nothing that predicts playoff or Super Bowl outcomes, so I can't name a winner.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 2.7 s, $0.00022, 0 queries, reason: model: The tables hold historical regular-season stats (QB and team EPA, fourth-down decisions, ATS results) but no predictive model, playoff data, or future results, so they cannot say who will win the Super Bowl.
  > We don't have the data to give an accurate answer to that.

### 18. Which college quarterback was the best value in 2025?

*`college_qb`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.2 s, $0.00011, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.7 s, $0.00011, 0 queries, reason: model: The tables cover NFL quarterbacks and teams only. They have no college football data, so a college quarterback's 2025 value can't be determined.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.6 s, $0.00012, 0 queries, reason: model: The tables cover NFL quarterbacks and teams only (QB season EPA, cap hits, and contract value). They contain no college football data, so college quarterback value in 2025 cannot be determined.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 15.2 s, $0.00087, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 0.7 s, $0.00018, 0 queries, reason: model: These tables cover NFL quarterbacks only (EPA per dropback, contract value, etc.) and contain no college quarterback data, so I can't answer who was the best value college QB in 2025.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 0.9 s, $0.00017, 0 queries, reason: model: The tables cover only NFL QB seasons and teams; there is no college quarterback data to answer this.
  > We don't have the data to give an accurate answer to that.

### 19. Which quarterback missed the most games to injury in 2025?

*`injuries`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.3 s, $0.00011, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.4 s, $0.00013, 0 queries, reason: model: The tables contain QB season efficiency (dropbacks, EPA, scrambles), contract cap data, game scores and spreads, team fourth-down and team EPA figures. None records injuries or games missed by a quarterback, so the 2025 injury question can't be answered.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.4 s, $0.00013, 0 queries, reason: model: The tables cover QB efficiency (EPA per dropback, success rate, scrambles), cap hits, game results against the spread, fourth-down decisions, and team EPA. None record injuries or games missed, so I can't say which quarterback missed the most games in 2025.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 7.4 s, $0.00019, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 5.1 s, $0.00018, 0 queries, reason: model: The nfl-dagster tables cover QB EPA per dropback, contract value, fourth-down decisions, team EPA, and ATS results — none of them track missed games or injury lists, so games missed to injury cannot be answered from this data.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 4.8 s, $0.00009, 0 queries, reason: model: The tables cover QB EPA per dropback, contract value, team efficiency, and fourth-down decisions, but nothing about games missed to injury, so injuries/missed games can't be measured.
  > We don't have the data to give an accurate answer to that.

### 20. What was Tom Brady's cap share in 2005?

*`brady_2005`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 3.7 s, $0.00040, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_name, cap_number, cap_share, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Brady%', 2005]`
- Run `20261018-201603`: ✅ PASS, 2.0 s, $0.00013, 0 queries, reason: model: The QB tables cover seasons 2015-2025 only (qb_contract_value and qb_season_epa), so there is no cap share for Tom Brady in 2005.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 4.5 s, $0.00033, 1 query, reason: model: The QB contract and cap tables have no row for Tom Brady in 2005. Their cap data covers 2015-2025 only, so no 2005 cap share is available.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_name, team, cap_number, cap_share FROM qb_contract_value WHERE passer_name LIKE %s AND season = 2005` params `['%Brady%']`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.6 s, $0.00037, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, cap_share, cap_number FROM qb_contract_value WHERE passer_name = %s AND season = 2005` params `['Tom Brady']`
- Run `20261018-201603`: ✅ PASS, 12.5 s, $0.00017, 0 queries, reason: answer without a query
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 5.2 s, $0.00055, 2 queries, reason: model: The database only covers the 2015-2025 seasons, so there is no row for Tom Brady's 2005 cap hit or cap share in qb_contract_value or qb_season_epa.
  > We don't have the data to give an accurate answer to that.
  - `SELECT qb_season_key, season, cap_number, cap_share, epa_per_dropback FROM qb_contract_value WHERE season = 2005 AND passer_name = %s` params `['Tom Brady']`
  - `SELECT qb_season_key, season, dropbacks, epa_per_dropback FROM qb_season_epa WHERE season = 2005 AND passer_name = %s` params `['Tom Brady']`

### 21. What is the over/under for the Chiefs' next game?

*`next_game_total`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.0 s, $0.00014, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 2.0 s, $0.00014, 0 queries, reason: model: The tables cover point spreads (spread_line and ATS results in game_results_vs_spread), but not over/under (total points) lines, so the Chiefs' next game's over/under isn't available here.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.7 s, $0.00012, 0 queries, reason: model: The tables hold point spreads (spread_line and ATS results) but no over/under (total points line) for any game, and no upcoming schedule, so the Chiefs' next game's over/under can't be found.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.4 s, $0.00052, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 5.9 s, $0.00018, 0 queries, reason: model: The tables have no betting totals (over/under lines) for upcoming games — game_results_vs_spread only covers played games and point spreads, not future games or totals.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 9.8 s, $0.00009, 0 queries, reason: model: The tables only cover played games and their betting spreads; there is no schedule of upcoming games and no over/under (total points) line data.
  > We don't have the data to give an accurate answer to that.

### 22. Who was the best value wide receiver in 2025?

*`wide_receiver`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.4 s, $0.00013, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.4 s, $0.00015, 0 queries, reason: model: The tables cover quarterbacks (qb_contract_value, qb_season_epa), teams, games against the spread, and fourth-down decisions. None include wide receivers, their stats, or their salaries, so I can't determine the best value wide receiver in 2025.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.7 s, $0.00014, 0 queries, reason: model: The tables cover quarterbacks (qb_contract_value, qb_season_epa), team efficiency, fourth-down decisions, and game ATS results. None include wide receiver stats, salaries, or value scores, so the best value wide receiver in 2025 can't be determined.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 2.0 s, $0.00036, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 0.9 s, $0.00017, 0 queries, reason: model: The database only covers quarterbacks (qb_season_epa, qb_contract_value); there is no wide receiver data.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 0.6 s, $0.00017, 0 queries, reason: model: The tables cover QB EPA and contract value, team EPA, and fourth downs — no wide receiver data.
  > We don't have the data to give an accurate answer to that.

### 23. How good a value was Johnny Fakeplayer in 2025?

*`made_up_player`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 4.2 s, $0.00033, 1 query
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_id, passer_name, team, cap_number, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%']`
- Run `20261018-201603`: ✅ PASS, 3.6 s, $0.00031, 1 query, reason: model: No QB named Johnny Fakeplayer has a 2025 season in qb_contract_value or qb_season_epa, so his contract value cannot be scored.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_id, passer_name, team, cap_number, cap_share, epa_per_dropback, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%']`
- Run `20261018-202158`: ✅ PASS, 5.3 s, $0.00049, 2 queries, reason: model: No QB named Johnny Fakeplayer has a 2025 season in qb_contract_value (searched by name, no rows returned), so his value score cannot be computed from these tables.
  > We don't have the data to give an accurate answer to that.
  - `SELECT season, passer_name, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%', 2025]`
  - `SELECT season, passer_name, team, epa_per_dropback, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name ILIKE %s AND season = 2025` params `['%Fakeplayer%']`

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 6.1 s, $0.00139, 2 queries
  > We don't have the data to give an accurate answer to that.
  - `SELECT qb_season_key, season, passer_id, passer_name, team, dropbacks, epa_per_dropback, cap_number, cap_share, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Johnny Fakeplayer', 2025]`
  - `SELECT DISTINCT passer_name FROM qb_contract_value WHERE passer_name ILIKE %s OR passer_name ILIKE %s` params `['%fakeplayer%', '%johnny%']`
- Run `20261018-201603`: ✅ PASS, 12.8 s, $0.00031, 2 queries, reason: model: No quarterback named Johnny Fakeplayer exists in qb_season_epa or qb_contract_value, so there is no 2025 season data to evaluate.
  > We don't have the data to give an accurate answer to that.
  - `SELECT passer_name, season, team, dropbacks, epa_per_dropback, cap_share, epa_over_expected, worth_it, is_season_complete FROM qb_contract_value WHERE passer_name = %s AND season = %s` params `['Johnny Fakeplayer', 2025]`
  - `SELECT DISTINCT passer_name FROM qb_contract_value WHERE passer_name ILIKE %s` params `['%Fakeplayer%']`
- Run `20261018-202158`: ✅ PASS, 20.8 s, $0.00023, 2 queries, reason: model: No player named "Johnny Fakeplayer" (or anything matching "Fake") exists in the qb_contract_value or qb_season_epa tables, so there's no data to assess his 2025 value.
  > We don't have the data to give an accurate answer to that.
  - `SELECT qb_season_key, passer_name, team, dropbacks, epa_per_dropback, is_season_complete, cap_number, cap_share, expected_epa_per_dropback, epa_over_expected, worth_it, is_cap_hit_for_team FROM qb_contract_value WHERE passer_name ILIKE %s AND season = %s` params `['%Fakeplayer%', 2025]`
  - `SELECT qb_season_key, passer_name, season, team, epa_per_dropback FROM qb_contract_value WHERE passer_name ILIKE %s LIMIT 20` params `['%Fake%']`

### 24. What was the weather in Buffalo for their last home game?

*`weather`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.3 s, $0.00012, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.3 s, $0.00012, 0 queries, reason: model: None of the tables record weather conditions. game_results_vs_spread has game dates, teams, scores, and betting lines, but no temperature, wind, precipitation, or other weather fields, so Buffalo's last home game weather can't be determined.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.4 s, $0.00013, 0 queries, reason: model: None of the tables record weather. game_results_vs_spread has game dates, teams, scores and spreads, but no temperature, wind, precipitation or conditions, so the Buffalo home game's weather can't be determined from this data.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.8 s, $0.00019, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 2.8 s, $0.00022, 0 queries, reason: model: No weather information exists in the available tables; game_results_vs_spread has scores and spread data but no weather columns for any game, including Buffalo's home games.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 3.7 s, $0.00017, 0 queries, reason: model: The available tables cover game results against the spread, QB EPA and contracts, fourth-down decisions, and team EPA, but none contain weather information (temperature, conditions, etc.) for any game.
  > We don't have the data to give an accurate answer to that.

### 25. What will Drake Maye's cap hit be in 2030?

*`future_cap_hit`. Expected: the no-data reply ("We don't have the data to give an accurate answer to that.").*

**Claude Haiku 5.5**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 1.5 s, $0.00013, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 1.6 s, $0.00014, 0 queries, reason: model: The tables hold Drake Maye's cap hits only for seasons already recorded (through the current 2026 season in progress). They contain no contract projections, so his cap hit for 2030 is not available.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 1.8 s, $0.00015, 0 queries, reason: model: The tables hold QB cap hits only for past and in-progress seasons (the latest season shown is 2026, in progress). They contain no projected or future contract figures, so Drake Maye's 2030 cap hit cannot be determined from this data.
  > We don't have the data to give an accurate answer to that.

**GLM-5.3 Flash**: 3/3 runs passed

- Run `20261018-201055`: ✅ PASS, 5.8 s, $0.00021, 0 queries
  > We don't have the data to give an accurate answer to that.
- Run `20261018-201603`: ✅ PASS, 9.3 s, $0.00022, 0 queries, reason: model: The qb_contract_value table only has one row per QB season actually played (2015-2025 with a cap hit). It contains no future contract years, so Drake Maye's projected or scheduled 2030 cap hit isn't in the data.
  > We don't have the data to give an accurate answer to that.
- Run `20261018-202158`: ✅ PASS, 6.0 s, $0.00019, 0 queries, reason: model: Drake Maye's 2030 cap hit is a future contract number; the database only has historical and current-season cap hits (through the 2025 season in progress) and doesn't contain future salary or projected cap figures.
  > We don't have the data to give an accurate answer to that.

## Every failure, with its recorded reason

(Reasons were recorded from the second run on.)

| Run | Model | Question | Failed check | Reason | Queries | Time |
| --- | --- | --- | --- | --- | --- | --- |
| 20261018-201055 | Claude Haiku 5.5 | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | (not recorded) | 1 | 4.3 s |
| 20261018-201055 | Claude Haiku 5.5 | Across all games since 2015 that had a spread, how often did the home team cover? | no answer | (not recorded) | 1 | 5.2 s |
| 20261018-201055 | GLM-5.3 Flash | Was Dak Prescott worth his contract in 2025? | no answer | (not recorded) | 2 | 4.1 s |
| 20261018-201055 | GLM-5.3 Flash | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | (not recorded) | 2 | 15.5 s |
| 20261018-201055 | GLM-5.3 Flash | Across all games since 2015 that had a spread, how often did the home team cover? | no answer | (not recorded) | 3 | 7.5 s |
| 20261018-201055 | GLM-5.3 Flash | Who has been the best value quarterback for his cap share so far in 2026? | no answer | (not recorded) | 1 | 12.7 s |
| 20261018-201603 | Claude Haiku 5.5 | Which team had the best net EPA per play in 2025? | no answer | numbers not in any result: 0.062 | 2 | 2.7 s |
| 20261018-201603 | Claude Haiku 5.5 | Across all games since 2015 that had a spread, how often did the home team cover? | no answer | numbers not in any result: 3026 | 2 | 6.1 s |
| 20261018-201603 | GLM-5.3 Flash | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | numbers not in any result: 90, 26.8, 2015 | 1 | 1.9 s |
| 20261018-202158 | Claude Haiku 5.5 | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | numbers not in any result: 90 | 1 | 3.8 s |
| 20261018-202158 | Claude Haiku 5.5 | Across all games since 2015 that had a spread, how often did the home team cover? | no answer | numbers not in any result: 3026 | 2 | 6.4 s |
| 20261018-202158 | GLM-5.3 Flash | What share of the salary cap was Jordan Love's cap hit in 2025? | no answer | query budget used up | 3 | 22.7 s |
| 20261018-202158 | GLM-5.3 Flash | What was Josh Allen's EPA per dropback in 2024? | no answer | query budget used up | 3 | 3.2 s |
| 20261018-202158 | GLM-5.3 Flash | How often did NFL teams go for it on fourth-and-short in competitive games in 2025? | no answer | numbers not in any result: 90 | 1 | 1.2 s |

## Who served GLM's requests

Every request asked OpenRouter for zero-data-retention, no-data-collection providers only.

- `20261018-201055`: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Parasail, PrimeIntellect, Together, Wafer
- `20261018-201603`: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Sail Research, Together, Wafer
- `20261018-202158`: Crusoe, DigitalOcean, InferenceNet, Modal, OpenInference, Sail Research, Wafer
