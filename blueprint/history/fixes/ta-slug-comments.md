# Fix: Stale slug comments after the flagged-players move (F-66)

**Type:** Fix
**Fixes:** F-66
**Branch:** `fix/ta-slug-comments`
**Completed:** 2026-11-18. Merged to master by PR at the user's request; API suite 6553 passed.

### The problem

The 2026-11-18 re-review kept F-66 at `fixed`: the move of the slug helper to
`core/ta_slug.py` left two comments naming the removed `_slug`
(`api/app/routers/admin.py:87`, `api/app/schemas/admin.py:26`), and the moved
comments carried em dashes and arrows.

### The fix

Comments only: both now name `ta_slug`, and `core/ta_slug.py` and
`ingest/player_stats.py:650` use plain punctuation. No code change.

### Build steps

- [x] **Step 1 - comments.** Done when: no `_slug(` reference remains in
  `api/app`, and the API suite passes.
