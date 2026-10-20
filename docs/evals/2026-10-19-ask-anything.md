# Ask page evaluation: "ask anything about the NFL" (2026-10-19)

What changed since [the structured-answers report](2026-10-19-haiku-structured-answers.md): the
page now invites any NFL question, so the instructions say "the NFL" instead of "quarterbacks and
teams"; the future (predictions, drafts, future contracts) is called out as never in the tables;
broad questions are answered with the best-fitting measure, named with its season (the latest
complete season, or the current one for "right now", "this season", "so far"); and a
definition's thresholds go in words ("in competitive game states"), not numbers. 14 golden
questions were added: the page's 5 example questions, 3 broad questions, a team's wins from
scores, and 5 more out-of-scope questions (41 in all). Haiku only, dev serving database.

## Summary

1. **No regression, and the page's examples are reliable.** The latest instructions pass 40/40 on
   the questions they touch (5 runs) and 111/114 on the full set (3 runs, see 4).
2. **The "90" false alarm is gone.** The model used to restate the fourth-down mart's definition
   ("win probability 10-90%"), which the number check blocks, so a suggested question
   (`example_fourth_down`) got "we don't have the data" 1 time in 3. After the threshold rule:
   `example_fourth_down` and `league_go_rate_2025` pass 8/8 each.
3. **Season choice is explicit.** Main's instructions already answered every broad question, but
   picked seasons inconsistently: "best QB right now" got 2026-to-date (fine), "most aggressive
   on fourth down" pooled 2015-2026. Now an undated question uses the latest complete season, a
   question about now uses the current season with the in-progress caveat (`broad_best_qb` checks
   it), and the answer names the measure and season.
4. **The dev database changed during the runs.** Four marts from the player/roster work
   (`player_season_efficiency`, `team_player_leaders`, `team_rosters`, `team_offensive_line`) were
   published to dev mid-session. With them, `mahomes_touchdowns`, `rushing_yards` and
   `wide_receiver` become answerable, and the model answered them correctly (Mahomes 26 TDs in
   2024, Barkley 2,005 rushing yards), which this branch's golden file scores as failures. They
   are left out of the totals below; prod serves only the original 5 marts, where they are still
   out of scope. The marts branch updates these questions when it ships.
5. **Cost:** $0.00050 per question (was $0.00045), 4.3 s on average.

## Results

| Run | Instructions | Questions | Passed | Misses |
| --- | --- | --- | --- | --- |
| 3 full runs | first draft of this PR | 41 x 3 | 119/123 | `home_cover_share` 2, `league_go_rate_2025` 1, `example_fourth_down` 1 |
| 3 runs, 14 new questions | main (before this PR) | 14 x 3 | 41/42 | `example_fourth_down` 1 |
| 5 targeted runs | final | 8 x 5 | 40/40 | none |
| 3 full runs | final | 38 x 3 (3 dev-only answerable left out) | 111/114 | `home_cover_share` 2, `example_ats_2024` 1 |

The targeted questions: `example_fourth_down`, `league_go_rate_2025`, `go_for_it_leader_2025`,
`broad_best_qb`, `broad_best_defense`, `broad_most_improved`, `best_value_2026_so_far`,
`example_prescott`.

## Remaining misses

- `home_cover_share` (2 of 3): ambiguous, as in the previous report: whether pushes count in the
  total changes the share. Once, the model quoted "3026" (a game count it computed in a way the
  checker couldn't match) and was blocked.
- `example_ats_2024` (1 of 3): a scoring bug, not a wrong answer. The answer named "the LA
  Chargers" (LAC, correct), but the truth query returned no team name to match the nickname
  against. The truth now carries `team_name`, as `ats_regular_season_2024`'s does on the marts
  branch.
