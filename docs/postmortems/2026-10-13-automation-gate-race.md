# Postmortem: an automation gate let a failed raw load trigger dbt rebuilds

> A blameless write-up of a bug found by deliberately injecting bad data. The design flaw was mine (the gate's original design); the point of this document is how it was found, understood, and fixed so it can't recur.

- **Date:** 2026-10-13, ~19:56 PDT
- **Found during:** Step 7, exercise 3 (deliberately injected bad data)
- **Severity:** would have been high in production (bad data reaching the marts automatically); actual impact this time: none on the marts (see Impact)
- **Status:** **resolved** 2026-10-13 ~20:10 PDT, commit `4e6c380` (write-audit-publish), locked in by tests in PR #2. See Resolution
- **Versions:** dagster 1.13.26, dagster-dbt 0.29.26, dagster-snowflake 0.29.26, dbt-core 1.12.5, dbt-snowflake 1.12.2

## Summary

The dbt models use a declarative automation condition meant to stop them from rebuilding while an upstream blocking check has failed:

```python
DBT_AUTOMATION_CONDITION = AutomationCondition.eager() & (
    ~AutomationCondition.any_deps_match(
        AutomationCondition.any_checks_match(
            AutomationCondition.check_failed(), blocking_only=True
        )
    )
).with_label("no_failed_blocking_checks_upstream")
```

A raw load with a duplicate play materialized `raw_pbp`, and its blocking check `raw_pbp_unique_plays` then failed. Even so, the automation sensor launched a rebuild of `staging/stg_pbp`, `marts/qb_season_epa`, and `marts/team_season_epa`. The sensor evaluated in the few seconds **after the asset materialized but before its check finished**, when `check_failed` was still false.

## What we did (exercise setup)

1. Temporarily added one duplicate row to `raw_pbp` in code (`df = pl.concat([df, df.head(1)])`), never committed.
2. Launched `current_season_refresh` for partition `2026` from the UI.
3. Expected: run fails on the blocking check; automation rebuilds the schedules branch but holds back the pbp branch.

## Timeline (PDT)

| Time | Event |
| --- | --- |
| 19:55:51 | `current_season_refresh` run starts (partition 2026) |
| ~19:56:1x | `raw_pbp` materializes (with the duplicate); `raw_pbp_unique_plays` starts |
| **19:56:18** | Sensor tick evaluates `staging/stg_pbp`: **requested 1** |
| ~19:56:20 | `raw_pbp_unique_plays` finishes: **failed** (`duplicate_rows: 1`) |
| 19:56:23 | Refresh run ends: **FAILURE** |
| 19:56:32 | Automation run starts: `stg_pbp`, `stg_schedules`, and the three marts. Ends **SUCCESS** |

## Evidence

`staging/stg_pbp` automation evaluation at 19:56:18 (from `assetConditionEvaluationRecordsOrError` via the Dagster GraphQL API; the asset's **Automation** tab shows the same tree), trimmed:

```
TRUE   (eager) AND (no_failed_blocking_checks_upstream)        requested 1
  TRUE   eager
    TRUE   any_deps_updated            raw_pbp newly_updated
    TRUE   NOT (any_deps_missing)
    TRUE   NOT (any_deps_in_progress)  raw_pbp in_progress = false   <- asset done, check still running
  TRUE   no_failed_blocking_checks_upstream
    false  raw_pbp:raw_pbp_unique_plays (check_failed)              <- check hadn't finished yet
```

Run events of the refresh run:

```
Materialization       raw_schedules
Materialization       raw_pbp
AssetCheckEvaluation  raw_schedules_scores_present passed
AssetCheckEvaluation  raw_pbp_unique_plays did not pass
ExecutionStepFailure  raw_pbp_raw_pbp_unique_plays
```

## Root cause

1. **The check runs after the asset's data is already published.** `raw_pbp` commits the season to Snowflake and emits its materialization *before* the check executes. From that moment, downstream automation can see "upstream updated".
2. **"In progress" refers to the asset, not its checks.** `any_deps_in_progress` / `in_progress` became false as soon as the asset materialized, even though the run (and its check) was still executing.
3. **`check_failed` is only true once a failed result exists.** In the gap between materialization and the check's result, there is no failure on record, so the gate passes.

The gate inspects check results from *outside* the run, so it is inherently exposed to this timing window. Sensor ticks are ~30s apart; whether the race happens depends on where a tick lands relative to a few seconds of check execution.

## Why "all blocking checks passed" is not a reliable fix

The obvious alternative is to require that every upstream blocking check **passed** against the latest materialization (instead of "none failed"). For partitioned checks (a preview feature in 1.13), status comes from `AssetCheckState` (`dagster/_core/storage/asset_check_state.py`, `_process_partition_records`):

- When a check is **planned** for a partition, that partition is added to `IN_PROGRESS`, but it is **not removed from `SUCCEEDED`**.
- The old status is only cleared when a record is "not current" (a newer materialization with a SUCCEEDED/FAILED record that doesn't target it).

So during the same gap, a partition can sit in both `IN_PROGRESS` and `SUCCEEDED`, and a "passed" gate could still read true from the *previous* run. (Not proven empirically; inferred from source. Worth a minimal repro before relying on it either way.)

## Impact

- **Raw:** `NFL.RAW.PBP` season 2026 contained 13,843 rows with **1 duplicate** (should be 13,842).
- **Staging / marts:** **not affected, by luck.** The duplicated row was row 1 of the season, the `GAME` start marker (`play_id 1`, `play_type` null, `desc 'GAME'`). `stg_pbp` keeps only `play_type in ('pass', 'run')`, so it was filtered out. `STAGING.STG_PBP` had 0 duplicates; all 16 dbt tests in the automation run passed.
- A duplicated pass or run play **would** have reached `stg_pbp` and the marts. The dbt `unique` test on `stg_pbp.play_key` would then have failed, but only after the marts were rebuilt with bad data.

## Clean-up done

- Fault removed (`git checkout -- src/nfl_dagster/assets/raw.py`), code location reloaded.
- Refreshed 2026 with the fixed code: the leftover duplicate is gone (13,842 rows, 0 duplicates).

## Proposed fix: write-audit-publish (validate before commit)

Move validation **inside the load transaction**, before the data becomes visible:

```
begin
delete season
copy into
validate (duplicates, score consistency, row count)   <- audit
commit   (only if validation passed; otherwise rollback + raise)
```

- On failure: `ROLLBACK` keeps the previous good season in Snowflake, and the asset raises, so **no materialization is recorded** and automation has nothing to react to. No race, because there is no "updated" event.
- Keep the asset checks: they remain the per-season report in the UI and the way to audit data at rest (`raw_data_checks` job).
- Keep the automation gate as defense in depth: it still blocks rebuilds whenever a failed check is already on record (e.g. from a standalone `raw_data_checks` run).

### Alternatives considered

| Option | Why not (or not alone) |
| --- | --- |
| Gate on "all blocking checks passed" | Same timing window for partitioned checks (see above) |
| Run dbt in the same run as the raw assets (blocking checks then stop it) | A job can't mix the partitioned raw assets with unpartitioned dbt assets |
| Delay automation (e.g. cron-based condition instead of eager) | Narrows the window, doesn't close it |
| Load into a separate table, check it, then swap/merge (full WAP with a staging table) | Valid and common at scale; more moving parts than an in-transaction audit for this size |

## Verification plan (exercise 3, second attempt)

1. Implement the in-transaction audit in `snowflake_load.py`.
2. Inject a duplicate **pass play** (not the `GAME` row) so it would reach the marts.
3. Refresh 2026. Expect: the asset step fails, `RAW.PBP` 2026 still has 13,842 rows and 0 duplicates, no automation run is launched, and the marts' `last_altered` time doesn't change.
4. Remove the fault, refresh 2026, and confirm automation rebuilds normally.

## Resolution

Implemented in `src/nfl_dagster/snowflake_load.py` (`load_parquet(..., expected_rows=, audits=)`, `AuditFailed`) and `src/nfl_dagster/assets/raw.py` (`AUDITS`, `load_to_snowflake`). The load is now: delete → copy → **audit** → commit, or rollback and raise `dg.Failure` with the audit results as metadata.

Audits (run inside the transaction, so they see the new rows before anyone else):
- `PBP.duplicate_plays`: `count(*) - count(distinct game_id, play_id)` for the season
- `SCHEDULES.mismatched_scores`: `count_if((home_score is null) <> (away_score is null))` for the season
- every table: `missing_or_extra_rows` = |rows loaded − rows in the file|, and rows loaded > 0

Audit results also appear in every successful materialization's metadata (e.g. `duplicate_plays: 0`).

### Verification (exercise 3, second attempt, ~20:07 PDT)

Injected one duplicated **pass play** (one that would reach `stg_pbp`) and refreshed 2026:

| Check | Before | After | |
| --- | --- | --- | --- |
| Step result | | `raw_pbp` failed: `RAW.PBP audits failed, load rolled back: {'duplicate_plays': 1}` | ✅ |
| `RAW.PBP` 2026 rows / duplicates | 13,842 / 0 | 13,842 / 0 | ✅ rolled back |
| Latest `raw_pbp` materialization | 20:05:47 | 20:05:47 (none recorded) | ✅ |
| `qb_season_epa` / `team_season_epa` last_altered | 20:06:14 / 20:06:15 | unchanged | ✅ not rebuilt |
| `game_results_vs_spread` | 20:06:14 | 20:08:14 | ✅ clean schedules branch still updated |
| `STAGING.STG_PBP` duplicates | 0 | 0 | ✅ |

Automation launched only `stg_schedules → game_results_vs_spread`; the pbp branch had no materialization to react to.

### Known side effect

The Parquet file (local and in the stage) is written **before** the audit, so a rejected delivery stays in the lake until the next successful load. That's acceptable here (it's the "as received" landing copy, useful for debugging, and the warehouse never published it), and a clean refresh replaced it (13,842 rows, 0 duplicates). If the lake ever becomes something other systems read, write to a temporary name and promote it only after the audit passes.

## Lessons

- A check that runs after data is published can **detect** bad data, but it can't **prevent** it from propagating. Prevention belongs before the commit.
- "The run failed" is not the same as "nothing downstream happened": automation reacts to materializations, which can be recorded before a later step fails.
- Test safety mechanisms by breaking things on purpose. The happy path never shows this.
- Read the evaluation tree, not just the outcome: it showed exactly which sub-condition let the run through.
- Interview line: *"Asset checks after the write can only alert. To stop bad data from propagating, I validate inside the load transaction and only commit clean data; Dagster's checks then report, and automation only ever reacts to data that passed."*

## Follow-ups

- [x] Implement write-audit-publish in `snowflake_load.py` and re-run exercise 3
- [x] Refresh 2026 to remove the leftover duplicate in `RAW.PBP`
- [x] Lock the fix in with tests: `tests/test_snowflake_load.py` fails if a failed audit, a row-count mismatch, or an empty load ever commits (PR #2; mutation-checked)
- [x] Run experiments like this one against a dev clone (`NFL_DEV`) instead of production (PR #1). This incident happened in the only environment at the time
- [ ] Write a minimal repro for the partitioned-check status behavior and, if it holds, open a Dagster GitHub issue
