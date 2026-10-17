# Coding Standards

> Rewritten by `/adopt` to describe the conventions this codebase actually
> follows, not a default template. Where the code is inconsistent, that is called
> out rather than papered over.

## Python (api/)

- Python 3.11. `from __future__ import annotations` at the top of modules that use
  forward-referenced or union type hints.
- Full type hints on function signatures. `Optional[X]` and `X | None` both appear;
  prefer `X | None` in new code.
- `@dataclass` for internal transfer objects (`PredictionOutput`, `EnsembleInput`,
  `EnsembleResult`). Pydantic models only at the API boundary.
- Module-level docstrings on modules whose purpose is not obvious from the name.
  Skip them on thin modules.
- No `Any`. Reach for a concrete type or a `TypedDict`.

## Backend architecture

The layering is consistent and worth preserving:

| Layer | Directory | Rule |
|---|---|---|
| Routers | `app/routers/` | Thin. Parse and validate input, call a service, shape the response. No business logic. |
| Services | `app/services/tennis/` | Orchestration. Fetches via repositories, builds features, runs models. |
| Core | `app/core/` | Pure functions. No DB, no I/O, no model loading. Fully unit-testable. |
| Repositories | `app/repositories/` | All SQL. Nothing else touches the database. |
| Schemas | `app/schemas/` | Pydantic request and response models. |
| Ingest | `app/ingest/` | Standalone entry points, each runnable as `python -m app.ingest.<name>`. |

**The `core/` purity rule is load-bearing.** `ensemble.py` documents it explicitly:
"No DB calls, no model loading, pure math." That is what makes the ensemble
testable without fixtures. Do not introduce I/O into `core/`.

**Repositories own SQL.** Routers and services must not build queries directly.

## Database

- PostgreSQL with async SQLAlchemy 2.0 over psycopg3.
- Alembic for every schema change: `alembic revision` then `alembic upgrade head`.
  Never modify the schema out of band.
- Migrations are numbered sequentially (`0001` through `0012`) and are never
  edited once applied.
- `AsyncSession` is passed into repository functions, never created inside them.
- Some indexes rely on `NULLS NOT DISTINCT`, which requires PostgreSQL 15 or newer.

## Configuration and secrets

- All config flows through `Settings` in `app/config.py` (pydantic-settings),
  loaded from `api/app/.env`.
- Never read `os.environ` directly in application code.
- Never commit `.env`. Never hardcode an API key.
- Routes that mutate data, trigger a scrape, or spend paid API quota must depend on
  `require_api_key` from `app/security.py`.

## TypeScript / React (web/)

- Strict mode on. No `any`; use `unknown` and narrow.
- Functional components only. Hooks for state and effects.
- Interfaces for props, API responses, and models. Shared types live in
  `src/types/`.
- Import via the `~/*` alias (`~/utils/format`), not deep relative paths.

## Frontend organization

- Components: `src/components/[feature]/ComponentName.tsx`
- Pages: `src/pages/NamePage.tsx`
- Data-fetching hooks: `src/hooks/useThing.ts`
- API transport: `src/api/[feature].ts`, all through the shared axios `client`
- Pure helpers: `src/utils/thing.ts`
- Types: `src/types/[feature].ts`

## Data fetching

- TanStack Query for all server state. No manual `useEffect` fetch loops.
- Every endpoint gets a typed function in `src/api/` and a hook in `src/hooks/`.
  Components call the hook, never axios directly.
- Query keys are arrays that include their parameters:
  `['tennis', 'today', { date, tour }]`.
- Set `staleTime` deliberately. The existing convention is 5 minutes for slate data.
- Loading and error states use the shared `LoadingState` and `ErrorState`
  components.

## Styling

Three mechanisms coexist here, on purpose:

- **CSS custom properties** in `src/index.css` define the theme (colors, fonts).
  New theme values belong there, not scattered through components.
- **Tailwind v4**, CSS-first via `@import "tailwindcss"`. No `tailwind.config.js`.
- **Ant Design 5** for structural and interactive components.

Inline `style` objects are used throughout for Ant Design layout components, and
that is the established pattern. Do not treat inline styles as a violation here,
but prefer theme variables over hardcoded hex values so the palette stays in one
place. Dark mode is the only mode.

## Error handling

- API: raise `HTTPException` with a real status code and a message the client can
  show. Do not return error strings with a 200.
- Web: let TanStack Query surface errors, render `ErrorState`.
- Ingest scripts: use `tenacity` for retry on transient network failures, and log
  rather than crash the whole run on a single bad record.

## Testing

The test gate is **on**. `AGENTS.md` declares test commands for both sides, which
per the Blueprint switch means a step that adds logic must ship a passing test in
the same diff.

`pytest` is declared in `api/requirements.txt`. In this managed Codex shell, the
bare `pytest` command may not be on PATH; use the local venv equivalent
`.venv\Scripts\python.exe -m pytest` from `api/` when needed.

**What to test** - pure logic where a wrong answer is possible:

- `app/core/` modules (odds math, Kelly, Poisson, prop EV, format inference)
- `app/services/tennis/ensemble.py` and other pure blending or scoring logic
- Parsers in `app/ingest/`
- `web/src/utils/` formatters and derivations

**What not to test** - React components, route integration, anything driving a
real browser, external API calls. Verify those by running the app.

**Conventions**

- Python tests live in `api/tests/` as `test_*.py`, run with `pytest` from `api/`.
- Web tests live beside their source as `thing.test.ts`, run with `vitest`.
- Mock external dependencies; use fixed timestamps rather than `Date.now()` so
  time-dependent assertions stay stable. `web/src/utils/format.test.ts` is the
  reference example: it passes an explicit `NOW` rather than mocking the clock.
- An empty suite should fail, not pass, so "no tests ran" never reads as "passed".

## Verification

The gate is the `Verify` command in `AGENTS.md`, run from the repo root with
the API venv active:

- `npm --prefix web run verify && cd api && python -m pytest`

`.github/workflows/verify.yml` runs the same command on every pull request and
push to `master`, beside a gitleaks secret scan (exceptions live in
`.gitleaks.toml`, one path each with a reason). To find which half failed, run
the pieces separately:

- `cd web && npm run build` (runs `tsc -b`, so it typechecks too)
- `cd web && npm run test`
- `cd api && pytest`

## Code Quality

- No commented-out code unless specified
- No unused imports or variables
- Keep functions under 50 lines when possible
- One-off diagnostic scripts do not belong in `api/`; preserve any future
  forensic helpers outside the live app tree.

## Comments

Write code that explains itself; comment only what the code cannot say.
Over-commenting is a common AI tell, so resist it.

- Comment the **why**, not the **what**. Delete any comment that restates the code.
- No banner/header blocks, section dividers, or step-by-step narration of obvious
  code. A file does not need a comment announcing each region.
- A comment earns its place only when it captures something the code can't: a
  non-obvious decision, a gotcha or workaround, why a value is what it is, or a
  link to a spec or issue.
- Prefer self-documenting names and small functions over explanatory comments.
- Keep doc comments minimal: a one-line purpose on an exported type or function is
  plenty; don't write JSDoc that just repeats the signature.
- When in doubt, leave the comment out.

The existing codebase does this well. `predictor.py` explains why `tour_label` is
separate from `tour` (WTA 125 arrives mislabeled) and why `best_of` is defaulted.
Those comments carry information the code cannot. Match that bar.

## Writing

- No em dashes (U+2014) in generated content: docs, comments, commit messages,
  READMEs, specs. They read as AI-generated.
- Use a hyphen for `term - description` separators; rephrase prose with commas,
  parentheses, or a colon. Avoid en dashes and the ellipsis character too.

> Note: existing source files do contain em dashes in comments and docstrings.
> This rule applies to new generated content; do not sweep the codebase for them.
