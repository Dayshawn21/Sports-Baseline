---
name: neon-migrate
description: Apply or check an Alembic migration against the shared Neon database, one command at a time with owner approval. Use only when the user explicitly runs /neon-migrate or invokes $neon-migrate.
disable-model-invocation: true
argument-hint: "[upgrade | downgrade-check | current]"
---

# Neon migration

The Neon database is shared with the GitHub Actions crons and the hosted API,
so every write here is a production write. `alembic.ini` is untracked, so this
skill builds a scratch one.

## Rules

- **Run one command per tool call** and show its output before the next.
- **Get a separate explicit yes** before each `upgrade` or `downgrade`. Approving
  a diff or a step does not approve a migration.
- Never print `DATABASE_URL` or any secret. `env.py` reads it from `Settings`
  (`api/app/.env`), so no URL goes in the ini.
- Never edit an applied migration (`api/app/db/migrations/versions/`); a hook
  refuses it anyway.
- If a migration is destructive (drops or renames), check the cron workflows
  that touch the affected tables first: a cron on older code can break until the
  branch is pushed (see `nfl-prop-lines.yml` in the overview).

## Steps

1. **Scratch ini.** Copy [alembic.ini.template](alembic.ini.template) to the
   session scratchpad as `alembic.ini`, replacing `{{SCRIPT_LOCATION}}` with the
   absolute path to `api/app/db/migrations` (forward slashes).
2. **Heads.** From `api/`: `.venv/Scripts/python.exe -m alembic -c <scratch ini> heads`.
   Exactly one head is expected.
3. **Current.** `... -m alembic -c <scratch ini> current`. Report the revision.
4. Depending on `$ARGUMENTS`:
   - `current` (default): stop after step 3.
   - `upgrade`: show the pending revisions, ask for a yes, then
     `... upgrade head`, then `current` again.
   - `downgrade-check`: for a newly added, additive migration only. With a yes
     for each command: `upgrade head`, `downgrade -1`, confirm the change is gone
     (for example `to_regclass('<table>')` is null), `upgrade head`, `current`.
5. **Record** the commands and resulting revisions under Testing in
   `blueprint/context/current-feature.md` when a feature or fix is active.
