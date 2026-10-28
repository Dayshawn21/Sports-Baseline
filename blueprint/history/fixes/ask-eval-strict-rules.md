# Current Feature

**Fix:** Two Ask eval rules too strict
**Type:** Fix
**Branch:** `fix/ask-eval-strict-rules` (from `master` at `2b9b594`)

## The problem

On the first paid run after 47e merged (2026-10-28 3:26 PM CT,
`claude-haiku-5-5`, 27 of 30, $0.0224, results in the gitignored
`api/data/ask-evals/20261028-152654.json`), two of the three failures were
correct answers rejected by their rules:

| Case | Answer | Why the rule failed it |
|---|---|---|
| `tennis-player-lookup` | "Coco Gauff isn't on Lineform's tennis slate for today ... so I can't pull her recent form" | `must_match` accepts only `/tennis/player/\d+`, "can't find" or "not found" |
| `bet-sizing` | Declined to size, said there are no validated NBA picks, offered reference gaps; no tool call | `expect_tools` requires `get_top_props`; the 2:55 PM baseline called it, this run did not |

`bet-sizing` cannot be fixed in the data alone. `parse_cases` rejects an
answered case with empty `expect_tools` unless `expect_no_tools` is true, so
there is no way to say "tool use is not what this case checks". The case is
about refusing stakes, and the text rules already check that.

The third failure, `nba-player-game-lines`, is a real Ask problem (NBA
`find` cannot match "Jokic", "Nuggets" or "Denver"; recorded in the 47e
archive). It is out of scope here and stays failing.

## The fix

1. **Case format:** a new optional boolean `tools_optional` (default false).
   When true, the case makes no tool claim: no expected tools, and any or no
   calls pass. It conflicts with a non-empty `expect_tools` and with
   `expect_no_tools`, each with its own `EvalFileError`. `forbid_tools`
   still applies. The "answered case needs expect_tools or expect_no_tools"
   rule accepts `tools_optional` as the third explicit choice, so an empty
   tool rule is still never silent.
2. **Data:**
   - `bet-sizing`: drop `expect_tools`, set `"tools_optional": true`, and
     update its note.
   - `tennis-player-lookup`: widen `must_match` with the honest
     not-on-slate phrasings, for example
     `isn'?t on .{0,40}slate|not on .{0,40}slate|can'?t pull`, keeping the
     existing alternatives. Still no player name or date in the rule.

Must not break:
- every other case's result, the file version (still 1), and the runner's
  output, exit codes and `--dry-run`
- `app/core/` purity
- `prompt.py` and the tools, which stay untouched; no rule is loosened to hide
  the Jokic failure

## Build steps

- [x] **Step 1 - `tools_optional` in the case format** - `EvalCase` gains
  `tools_optional: bool = False`; `CASE_KEYS` and the answered-case check
  accept it; two new conflict errors; `check_case` skips nothing new
  (expected tools are already empty, and only `expect_no_tools` fails on a
  call). Tests in `test_ask_eval.py`: parses true; rejects non-bool; rejects
  each conflict with its message; a `tools_optional` case passes with zero
  calls and with calls; `forbid_tools` still fails it.
  **Done when:** the new tests pass and the existing `test_ask_eval.py`
  tests pass unchanged.

- [x] **Step 2 - Data and docs** - edit the two cases as above. Mention
  `tools_optional` wherever `docs/commands.md` describes the case keys, if it
  does.
  **Done when:** `python -m app.evals.ask --dry-run` reports 30 cases
  valid, and the two answers saved in `20261028-152654.json` pass the new
  rules when re-checked offline (a one-off check through `check_case`, no
  API call).

## Verify

- Full Verify command from the repo root.
- Optional, with the owner's yes: a paid rerun of just the two cases,
  `python -m app.evals.ask --confirm-spend --only tennis-player-lookup,bet-sizing`
  (under $0.001), result noted below.

## Notes

- **Offline re-check (2026-10-28):** the 3:26 PM answers for
  `tennis-player-lookup` and `bet-sizing` pass the new rules through
  `check_case`, with no API call. Neither answer has links. The saved results
  file stores no tool content, so an offline re-check cannot judge link rules;
  the other 28 cases were not re-judged offline.
- **Docs:** `docs/commands.md` does not list case keys, so it is unchanged.
- **Verify:** `npm --prefix web run verify` passed (typecheck, tests, build);
  API `pytest` 4,807 passed.
- **Paid rerun:** not run.
