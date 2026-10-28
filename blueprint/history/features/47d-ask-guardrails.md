# Current Feature

**Feature:** 47d. Ask Lineform: guardrails and cost
**Type:** Feature
**Branch:** `feature/47d-ask-guardrails`
**Build plan line:** per-IP daily question limit, in-memory global daily
spend cap, max_tokens cap, per-request token and estimated-cost logging; then
enable in production.

## Goal

Make Ask Lineform safe to leave on for anonymous visitors. Before a question
reaches Claude, the API refuses it when the visitor has used today's 20
questions or the whole app has spent today's budget; every question that runs
adds its estimated cost to that budget and writes one log line with its token
usage and cost. Then the 47c production guard comes out and the owner turns
Ask on in Render.

The owner may take any step by saying so. By default **the owner writes the
loop's usage change (Step 3, a few lines in `loop.py`)**, as in 47b and 47c;
Claude writes its tests first and coaches.

## In scope

- Pure cost estimate from `AskUsage` and per-token prices held in `Settings`.
- In-memory, per-process guardrails: a UTC-day spend total and a per-IP
  question counter (20 a day by default).
- `POST /ask` refuses before the stream opens: 503 when the daily budget is
  spent, 429 with `Retry-After` when the visitor's daily questions are used.
- Usage recorded for every question that reached Claude: answered, errored
  or cancelled by a client disconnect.
- One structured log line per question (stop, requests, tokens by kind,
  estimated cost, tool names, duration, today's running total). No question
  text, answer text or IP address in the log.
- Bounds on `ask_max_tokens` and `ask_max_tool_iterations` in `Settings`.
- `validate_production_settings`: delete the 47c "ASK_ENABLED is on before
  47d's limits exist" check and replace it with checks that Ask, when on in
  production, has a key and sane limits.
- Web: error copy for the two new refusals.
- `render.yaml`: `ANTHROPIC_API_KEY` (`sync: false`) and `ASK_ENABLED`.
- Docs: `AGENTS.md` Ask section, local interview guide if present.
- Enabling in production (owner actions, each with its own yes).

## Out of scope

- A persisted cap or counter (a table and a manual migration; open question
  65 accepts in-memory for v1). A restart resets both.
- Fixing `X-Forwarded-For` spoofing of the per-IP limit (37d's accepted
  limit); the global cap and the Console limit bound the damage.
- Reserving budget for questions in flight (see Notes: bounded overshoot).
- Showing the remaining question count in the drawer, or extending
  `GET /ask/status`.
- How it works page copy about the chat; prompt or tool changes; evals (47e).
- Any change to a probability, edge, rank, sort, pick or `SPORT_STATUS`.

## Build loop

Small steps on `feature/47d-ask-guardrails`. Each step shows its diff, ships
its tests, and runs the relevant half of Verify; Step 7 runs the full Verify
command. Step 8 touches remote services and needs a separate yes for each
action.

## Build steps

- [x] **Step 1 - Cost estimate (pure)** - new `app/core/ask_cost.py`:
  `AskPrices` (frozen dataclass: `input`, `output`, `cache_read`,
  `cache_write`, all USD per million tokens) and
  `estimate_cost_usd(usage: AskUsage, prices: AskPrices) -> float`, summing
  each token kind times its price. `Settings` gains
  `ask_price_input_per_mtok = 0.10`, `ask_price_output_per_mtok = 0.50`,
  `ask_price_cache_read_per_mtok = 0.01`,
  `ask_price_cache_write_per_mtok = 0.125`, and a helper
  `ask_prices(settings) -> AskPrices` beside `make_client` in
  `services/ask/client.py`.
  *Done when:* tests pin the cost of a fixed usage (each token kind alone and
  combined), zero usage is 0.0, and the prices are read from `Settings`, not
  constants.

- [x] **Step 2 - Guardrails state (in-memory)** - new
  `app/services/ask/guardrails.py`:
  - `DailySpend`: `spent(today: dt.date) -> float`,
    `record(today, cost_usd) -> float` (returns the new total), and
    `exhausted(today, cap_usd) -> bool` (`spent >= cap`). A new UTC date
    starts from zero; older days are dropped.
  - `question_retry_after(client_ip: str, per_day: int) -> int | None`:
    counts one question through the existing moving-window limiter
    (`retry_after_seconds` with `RateRule(f"{per_day}/day", "ask_daily")`),
    returning seconds until the next allowed question or None.
  - Module-level `spend = DailySpend()`, one per process (one Render
    instance, like the rate limiter).
  `Settings` gains `ask_daily_questions_per_ip = 20` and
  `ask_daily_spend_cap_usd = 1.0`.
  *Done when:* tests with fixed dates show spend accumulates within a day,
  resets on the next UTC date, `exhausted` flips exactly at the cap; the 21st
  question from one IP gets a positive retry-after while another IP still
  gets None (limiter storage reset between tests).

- [x] **Step 3 - Usage survives errors and cancellation (owner writes the
  loop part, coached)** - `run_ask` takes an optional caller-owned
  `usage: AskUsage | None = None` and adds each round into it (creating its
  own when None, so `chat.py`, `preview` and every existing caller are
  unchanged). Claude then changes `ask_frames` to own that `AskUsage`, and in
  its `finally` (done, error frame or disconnect alike) to:
  - skip recording when `usage.requests == 0` (nothing reached Claude);
  - otherwise estimate the cost, `spend.record(today, cost)`, and log one
    line at INFO:
    `ask question stop=<stop|error|cancelled> requests= input= output=
    cache_read= cache_write= cost_usd=<6dp> spent_today_usd=<4dp>
    tools=<comma-joined names> ms=`.
  Tests are written first: a fake that raises on the second round still
  records round one's usage; a cancelled stream (47c's `HangingStream`)
  after one completed round records it with `stop=cancelled`; the log line
  carries none of the question text, answer text or client IP.
  *Done when:* those tests pass, every existing loop and route test passes
  unchanged, and `run_ask` with no `usage` argument returns the same
  `AskOutcome` as before.

- [x] **Step 4 - Refuse before the stream opens** - in `routers/ask.py`, a
  dependency `require_ask_budget` runs after `require_ask_enabled` and body
  validation, before `make_client`:
  1. `spend.exhausted(today, cap)` -> 503 `"Ask Lineform has reached today's
     limit. It resets at midnight UTC."` (checked first, so a refused
     question does not use one of the visitor's 20);
  2. `question_retry_after(client_ip, per_day)` -> 429 `"You've used today's
     <N> questions. Try again tomorrow."` with `Retry-After`.
  `client_ip` is `request.client.host` (the middleware's rule; "unknown"
  when absent). The per-minute heavy limit in the middleware stays.
  *Done when:* ASGITransport tests show: the 21st question from one client
  is a 429 with `Retry-After` and no client was constructed; a spent budget
  is a 503 that does not count against the client's daily questions; a 422
  or disabled 404 counts nothing; a normal question still streams 47c's
  exact frames. No test needs a key or a database.

- [x] **Step 5 - Settings bounds and the production check** -
  - `ask_max_tokens: int = Field(1024, ge=256, le=4096)`,
    `ask_max_tool_iterations: int = Field(5, ge=1, le=8)`,
    `ask_daily_questions_per_ip: int = Field(20, ge=1, le=200)`,
    `ask_daily_spend_cap_usd: float = Field(1.0, gt=0, le=20)`.
  - `validate_production_settings` loses the 47c guard and its comment. With
    `ask_enabled` in production it reports `ANTHROPIC_API_KEY is empty while
    ASK_ENABLED is on`. Its signature takes `anthropic_api_key` too; `main.py`
    passes it.
  *Done when:* tests show production starts with Ask on and a key, refuses
  Ask on without a key, still allows Ask off without a key, dev is never
  checked, and out-of-range values fail `Settings` validation.

- [x] **Step 6 - Web copy for the refusals** - `askErrorMessage(status,
  detail)`: for 429 and 503 it shows the API's `detail` when present (both
  are fixed server copy), falling back to today's text; the hook passes
  `AskHttpError.message`. A per-minute 429 from the middleware keeps its
  own detail ("Too many requests. Try again shortly.").
  *Done when:* Vitest covers the daily 429, the cap 503, the
  not-configured 503, and a missing detail falling back; `npm run build`
  typechecks.

- [x] **Step 7 - Docs, render.yaml and the final gate** -
  - `render.yaml` (`sportapp-api`): `ANTHROPIC_API_KEY` with `sync: false`,
    and `ASK_ENABLED` with `sync: false` so it is set in the dashboard, not
    turned on by a deploy.
  - `AGENTS.md` Ask section: remove "Production refuses to start with it on
    ... 47d deletes that check"; document the two refusals, the four new
    settings, the log line, the restart reset and the Console backstop. Keep
    "never set it in `render.yaml`" accurate (the value lives in the
    dashboard).
  - Local interview guide if present: guardrails, cost estimate, why
    in-memory, the overshoot bound.
  - Local free checks: with `ASK_DAILY_QUESTIONS_PER_IP=2` the third
    question from the browser shows the daily copy; with
    `ASK_DAILY_SPEND_CAP_USD` tiny and one owner-approved paid question, the
    log line appears and the next question shows the cap copy.
  *Done when:* the full Verify command passes and both local checks are
  recorded in this spec.
  - Verify (2026-10-28): web typecheck, tests and build; 4,704 API tests.
  - Daily limit (owner, local browser, 2026-10-28,
    `ASK_DAILY_QUESTIONS_PER_IP=2`): two NBA questions answered with tool
    status and internal links; the third ("what about the lal vs lac") showed
    "You've used today's 2 questions. Try again tomorrow." with Retry.
  - Spend cap (owner, local, 2026-10-28, `ASK_DAILY_SPEND_CAP_USD=0.0001`):
    "Who plays in the NBA tonight?" answered (one `get_slate` call, 12
    linked games); the next request returned 503 `{"detail": "Ask Lineform
    has reached today's limit. It resets at midnight UTC."}`. The answer
    again said "13 NBA games" above 12 (47c's miscount, reproduced; 47e).

- [x] **Step 7a - Repair: make app INFO logs visible (found in Step 7)** -
  the spend-cap check refused correctly but printed no cost line: nothing
  configured logging, uvicorn sets up only its own loggers, and Python's
  last-resort handler shows WARNING and above, so every `app.*` INFO line was
  dropped locally and on Render. `configure_app_logging()` in `app/main.py`
  gives the `app` logger INFO and one stream handler (`INFO:     <logger> -
  <message>`); ingest CLIs never import `app.main` and keep their own
  `basicConfig`. Route tests now pin the cap and daily limit so a local
  `.env` cannot decide them.
  *Done when:* tests show `app.*` INFO is enabled with exactly one handler,
  Verify passes, and a restarted local API prints the `ask question` line
  for one answered question.
  - Verify (2026-10-28): 974 web tests and build; 4,706 API tests.
  - Owner, restarted local API, default limits, one question:
    `INFO:     app.services.ask.answer_stream - ask question stop=truncated
    requests=2 input=3305 output=1075 cache_read=3207 cache_write=3207
    cost_usd=0.001301 spent_today_usd=0.0013 tools=get_slate ms=5679`.
    The cost matches the four token kinds at the configured prices by hand.
    The answer hit `ask_max_tokens = 1024` (`stop=truncated`; thinking counts
    toward it on Haiku 5.5).

- [x] **Step 7b - Owner-approved follow-ups from the live runs (2026-10-28)**
  - `ask_max_tokens` default 1024 -> 2048 (inside the 256-4,096 bound): the
    Step 7a question hit 1024 with thinking counted. At most about $0.0005
    more a question, only when used.
  - Retry is hidden when sending the same question again cannot work soon:
    `askRetryable(status, detail, retryAfter)` in `utils/askError.ts`
    returns false for 404, 422, a 429 whose `Retry-After` is over 60 s (the
    daily limit; the per-minute limit keeps Retry) and a 503 carrying an API
    detail (spending cap, no key); a proxy 503 without one keeps Retry.
    `AskHttpError` carries `retryAfter`; `AskTurn` gains `retryable`.
  *Done when:* Vitest covers every retry case and the reducer's
  `retryable`; Verify passes (984 web tests and build; 4,706 API tests).

- [ ] **Step 8 - Enable in production (owner, separate yes per action;
  open at completion, see Completion evidence)** -
  after `/complete` merges, in order:
  1. Owner sets a monthly spend limit on the Anthropic Console (the
     backstop; record the amount, not the key).
  2. Push `master` (separate yes); Render redeploys with Ask still off
     because `ASK_ENABLED` is unset.
  3. Owner enters `ANTHROPIC_API_KEY` and `ASK_ENABLED=true` in the Render
     dashboard; the service restarts.
  4. Hosted smoke: `GET /ask/status` reads enabled, the Ask button shows on
     the public site, one owner-approved paid question streams an answer with
     internal links, and the Render log shows its cost line.
  *Done when:* those four are recorded with dates. If any fails, unset
  `ASK_ENABLED` in the dashboard (Ask goes dark without a deploy).

## Files / areas

| Area | Files |
|---|---|
| API core | `app/core/ask_cost.py` (new), `app/core/production_settings.py` |
| API services | `app/services/ask/guardrails.py` (new), `answer_stream.py`, `client.py`, `loop.py` (owner, Step 3) |
| API route / config | `app/routers/ask.py`, `app/config.py`, `app/main.py` |
| API tests | `test_ask_cost.py`, `test_ask_guardrails.py` (new), `test_ask_loop.py`, `test_ask_route.py`, `test_production_settings.py` |
| Web | `utils/askError.ts` (+ test), `hooks/useAskSession.ts` |
| Ops / docs | `render.yaml`, `AGENTS.md`, local interview guide |

## Data / contracts

No schema, migration or new dependency.

**Load-bearing (extends 47c's `POST /ask` contract):**

```text
POST /ask
  404 disabled | 422 bad question
  503 {"detail": "Ask Lineform has reached today's limit. It resets at midnight UTC."}
  429 {"detail": "You've used today's 20 questions. Try again tomorrow."} + Retry-After
  429 {"detail": "Too many requests. Try again shortly."} + Retry-After   (per-minute, middleware)
  503 {"detail": "Ask Lineform is not configured"}                         (no key)
  200 text/event-stream, frames unchanged from 47c
```

- Order: enabled, body, spend cap, per-IP daily, client. A refused question
  never constructs a client or costs anything.
- `run_ask(..., usage: AskUsage | None = None)`; `AskOutcome` unchanged, so
  47e reads `usage` as before and can price it with `estimate_cost_usd`.
- **47e reuses `estimate_cost_usd` and the `Settings` prices** for its total
  cost; prices live in one place.
- The log line's field names are stable so Render log searches keep working.

## Testing

- Test gate on: Steps 1-6 ship pytest or Vitest tests; Step 7 adds browser
  evidence; Step 8 is hosted evidence.
- Fixed dates and an explicit `today` argument, never the wall clock;
  limiter storage reset in a fixture so tests do not leak counts.
- Route tests reuse 47c's fake client, fake sessions and `HangingStream`;
  CI stays keyless.
- Paid questions only with owner approval per batch (about a tenth of a cent
  each at 47b's measurement).
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Prices (confirmed on the live pricing page, 2026-10-28):** Haiku 5.5 for
  prompts up to 100K is $0.10 input, $0.125 5-minute cache write, $0.01
  cache hit and $0.50 output per million tokens. Over 100K is 5x; Ask
  prompts stay far under it, so only the standard rates are modelled.
- **Bounded overshoot, not a hard cap:** the check reads spend before a
  question runs, so concurrent questions can pass together. Overshoot is at
  most (questions in flight) times one question's maximum cost
  (`ask_max_tool_iterations + 1` rounds at `ask_max_tokens` output). Record
  that bound in the interview guide; the Console limit is the hard stop.
- **A cancelled round is not counted:** a disconnect mid-stream loses that
  round's usage (no final message). State it in the log docs; it is cents.
- **No user data:** the log never carries the question, answer or IP, in line
  with "stores no user data or conversation".
- **One process:** the cap and counters assume Render's single instance; a
  second instance would need shared storage (out of scope, note it).
- **Coach Step 3, don't write it** unless the owner asks. Write the failing
  tests first, review with a hint before a fix.
- **Production:** never set `ASK_ENABLED` to true in a committed file. Step 8
  is the only place Ask goes live, and each remote action needs its own yes.
- No em dashes in new code, comments or docs.
- **For 47e (found in Step 7's live run, 2026-10-28):** asked "what are best
  plays in mia and atl", the answer said "The model's signal for the game is
  'none'", exposing the internal `signal` field. An eval case: answers never
  name internal fields (`signal`, `none`, `reference_only`).

## Completion evidence (2026-10-28)

- **Built:** Steps 1-7b. The owner wrote Step 3's loop change (`run_ask`
  takes a caller-owned `usage`) against tests written first; review edits
  were whitespace only. Two deviations from the spec, both reviewed: the
  budget check is a function called in the endpoint, not a dependency
  (dependencies run before body validation, so a 422 would use a question);
  `AskHttpError` carries `detail` separately, so a non-JSON proxy 503 never
  shows its status text.
- **Found while checking:** app INFO logs were invisible locally and on
  Render (Step 7a); a live answer hit 1024 max tokens and Retry showed on
  refusals that cannot clear (Step 7b, owner-approved).
- **Verify:** 984 web tests and build; 4,706 API tests.
- **Live local runs (owner, paid, 2026-10-28):** daily limit at 2, spend cap
  at $0.0001, and the cost line at default limits (recorded under Step 7 and
  7a; cost matches token counts by hand).
- **Not verified:** the hidden Retry in a browser (unit tests and build
  only); anything on Render.
- **Step 8 is an owner follow-up, not done:** Ask stays off in production
  until the owner sets the Anthropic Console spend limit, approves the push,
  enters `ANTHROPIC_API_KEY` and `ASK_ENABLED=true` in the Render dashboard,
  and runs the hosted smoke (status enabled, one paid question, the Render
  log's `ask question` line). Each action needs its own yes.
- **Known limits:** in-memory totals reset on restart; in-flight questions
  can overshoot the cap by one question's maximum cost each; the per-client
  count is spoofable through `X-Forwarded-For`; a round cut off by a
  disconnect is not counted. The Console limit is the hard stop.
- **For 47e:** "13 NBA games" above 12, reproduced on 2026-10-28; the
  internal `signal` field named in an answer.
