# Current Feature

**Feature:** 47c. Ask Lineform: streaming endpoint and chat panel
**Type:** Feature
**Branch:** `feature/47c-ask-stream-and-panel`
**Build plan line:** `POST /ask` streaming text and tool-status events over
SSE, behind an `ask_enabled` setting that stays off in production until 47d;
a top-bar chat drawer with starter questions, internal-link-only citations,
loading, error and accessible states.

## Goal

Put 47b's tool loop in front of a visitor. A question typed in a top-bar chat
drawer goes to `POST /ask`; the API streams tool status ("Checking the NBA
slate") and the answer's text as it is written; the drawer renders the answer
with links only to Lineform pages. The whole surface is off unless
`ask_enabled` is true, and production refuses to start with it on until 47d's
limits exist.

This stays a learning feature. **The owner writes the loop's streaming change
(Step 2); Claude coaches it, writes its tests first, and writes the endpoint
and web code.** The owner can take any other step by saying so.

## In scope

- `messages.stream` in the loop, with a new `TextDelta` event; the loop's
  shape, stops and `AskOutcome` are unchanged.
- `ask_enabled: bool = False` in `Settings`; a production startup check that
  refuses `ask_enabled=true` (47d removes that check when it enables
  production).
- `GET /ask/status` and `POST /ask` (SSE) in a new `app/routers/ask.py`.
- `/ask` on the heavy per-client rate limit (10 a minute), the only abuse
  guard until 47d.
- Web: an SSE reader over `fetch`, pure helpers for SSE parsing, tool-status
  labels and safe answer rendering, a status hook, and an `AskDrawer` opened
  from a top-bar button on desktop and phone.
- Starter questions per active sport; one question at a time with the
  session's earlier answers kept in component state (lost on reload).

## Out of scope

- Per-IP daily limit, global spend cap, cost logging, enabling production
  (47d). 47c logs nothing beyond what 47b already logs.
- Evals (47e). Prompt or tool changes, except a bug the panel exposes.
- Multi-turn history: each question is sent alone; earlier drawer answers are
  display only and never sent back. The plan stores no conversation.
- Full markdown. Answers render paragraphs, `- ` bullet lines and internal
  links only (see Step 4).
- Any change to a probability, edge, rank, sort, pick or `SPORT_STATUS`.
- How it works page copy about the chat (after 47d, when it is public).

## Build loop

Small steps on `feature/47c-ask-stream-and-panel`. Each step shows its diff,
ships its tests, and runs the relevant half of Verify; the last step runs the
full Verify command.

## Build steps

- [x] **Step 1 - Stream contract (no I/O)** - `TextDelta(text: str)` joins
  `AskEvent` in `loop.py` (unused until Step 2). New
  `app/services/ask/stream.py`, kept in services because it imports the
  loop's event types (core never imports services):
  `sse_frame(event: str, data: dict[str, object]) -> str` (`event:
  <name>\ndata: <compact JSON>\n\n`), `SSE_PING = ": ping\n\n"`,
  `event_frame(event: AskEvent) -> str`, `done_frame(outcome: AskOutcome)`,
  and `error_frame(kind: Literal["busy", "unavailable", "failed"])` with
  fixed user-safe copy. `ToolStarted` sends only `name` and the input's
  `sport` (or null), never the rest of the model's input.
  *Done when:* tests pin each frame byte-for-byte, a multi-line `text` delta
  stays one `data:` line (JSON escapes the newline), `tool_start` never
  carries keys other than `name` and `sport`, and `done` carries only `stop`
  and `text`.

- [x] **Step 2 - Loop streams text (owner writes, coached)** - in
  `run_ask`, replace `client.messages.create(...)` with
  `async with client.messages.stream(...) as stream`, forward each text delta
  to `on_event(TextDelta(text))`, then take `await stream.get_final_message()`
  as `response`; everything after that line is unchanged. Claude first
  extends the fake client in `test_ask_loop.py` with a `messages.stream`
  context manager that yields scripted text events and returns the scripted
  `Message`, and writes the failing tests.
  *Done when:* every existing loop test passes on the stream fake; new tests
  show text deltas from each round arrive in order before `done`, a
  tool-only round emits no `TextDelta`, and with `on_event=None` the outcome
  is identical. `chat.py` prints deltas live (optional, owner's call).

- [x] **Step 3 - Setting, production guard and status route** -
  `ask_enabled: bool = False` in `Settings`;
  `validate_production_settings` gains an `ask_enabled` argument and reports
  "ASK_ENABLED is on before 47d's limits exist". New
  `app/routers/ask.py` mounted at `/ask` with `GET /ask/status` returning
  `{"enabled": bool}` (true only when `ask_enabled` and
  `anthropic_api_key` are both set). Add `/ask` to `HEAVY_PATHS`
  (`/ask/status` stays on the default bucket).
  *Done when:* tests show production refuses `ask_enabled=true` and dev
  allows it, status reads false with the key missing, and `rule_for_path`
  gives `/ask` the heavy rule and `/ask/status` the default.

- [x] **Step 4 - `POST /ask` streaming** - body `AskRequest { question: str }`
  (stripped, 1 to 500 characters, else 422). Disabled returns 404; enabled
  without a key returns 503 "Ask Lineform is not configured". Otherwise a
  `StreamingResponse` (`text/event-stream`, `Cache-Control: no-cache`,
  `X-Accel-Buffering: no`) whose generator:
  - opens its **own** `SessionLocal()` (FastAPI 0.115 closes `yield`
    dependencies before a streamed body runs, so `Depends(get_db)` would hand
    the loop a closed session) and its own client from `make_client`, both
    closed in `finally`;
  - runs `run_ask` as a task feeding an `asyncio.Queue` through `on_event`,
    and yields frames from the queue, plus `SSE_PING` after 10 s of silence
    (cold tools take up to 15 s; proxies drop idle streams);
  - ends with one `done` frame, or one `error` frame when `run_ask` raises
    (the router classifies: `RateLimitError` or a 529 `APIStatusError` is
    `busy`, any other `anthropic.APIError` `unavailable`, anything else
    `failed`; logged with `logger.exception`, never sent);
  - cancels the task when the client disconnects (generator closed), so the
    Anthropic stream and the session close.
  The client factory is injectable (`Depends(ask_client_factory)`) so tests
  override it with the fake.
  *Done when:* `httpx.AsyncClient` over `ASGITransport` tests, with the fake
  client and a stubbed `run_tool`, read the exact frame sequence for a
  two-tool question, an `error` frame with no exception text for a raised
  `APIStatusError`, 404 when disabled, 422 for empty and 501-character
  questions, and that the session and client are closed after a cancelled
  stream. No test needs `ANTHROPIC_API_KEY` or a database.

- [ ] **Step 5 - Web transport and pure helpers** -
  - `web/src/types/ask.ts`: the event union below.
  - `web/src/utils/askStream.ts`: `parseSseChunks(buffer) -> { events,
    rest }`, tolerant of frames split across reads, CRLF, comment lines
    (`: ping`) and unknown events (ignored).
  - `web/src/utils/askAnswer.ts`: `answerBlocks(text)` into paragraphs and
    bullet lists of segments `{ kind: 'text' | 'link', ... }`. A
    `[label](path)` becomes a link only when the path is internal
    (`/`-rooted, no `//`, no scheme) **and** matches a known route pattern
    (`/`, `/nba`, `/nfl`, `/nba/game/:id`, `/nfl/game/:id`,
    `/tennis/match/:id`, `/nfl/player/:id`, `/tennis/player/:id`,
    `/{sport}/model`, `/{nba|tennis}/board`, with the query strings
    `ask_links.py` emits). Anything else, including `https://...`,
    `javascript:` and unknown paths, renders as its label in plain text.
    `**bold**` markers are dropped, not rendered.
  - `web/src/utils/askStatus.ts`: `toolLabel(name, sport)` ("Checking the
    NBA slate", "Reading the NFL model's track record", "Searching
    Lineform"), with a fallback for an unknown tool.
  - `web/src/api/ask.ts`: `getAskStatus()` through the axios client and
    `streamAsk(question, { signal, onEvent })` over `fetch` (EventSource
    cannot POST), using `resolveApiBaseUrl`; a non-2xx response becomes a
    thrown error carrying the status and the API's `detail`.
  - `web/src/hooks/useAskStatus.ts`: `['ask', 'status']`, `staleTime` 5
    minutes, no retry on 404.
  *Done when:* Vitest covers split frames, pings, unknown events, every
  route pattern accepted, and external, `javascript:`, protocol-relative
  and unknown paths rejected; `toolLabel` covers all six tools plus the
  fallback. `npm run build` typechecks.

- [x] **Step 6 - Drawer, happy path** - `web/src/components/ask/AskDrawer.tsx`
  (+ `ask.css`) and a top-bar "Ask" button in `TopBar` and the mobile
  header, rendered only when `useAskStatus` reads enabled.
  - Ant `Drawer` (right on desktop, full width on phones), title "Ask
    Lineform", a one-line note: "Answers come from Lineform's data. NBA and
    NFL numbers are reference only, not picks."
  - Empty state: three starter questions for the active sport (from
    `shellNav`), a general set elsewhere; clicking one sends it.
  - Input: textarea, 500-character counter, Enter sends, Shift+Enter new
    line, disabled while a question runs.
  - While running: tool-status lines (spinner then check or "couldn't
    check") and the streamed text; on `done` the text is replaced by
    `done.text`, rendered through `answerBlocks` with router `Link`s.
  *Done when:* `npm run build` passes and one owner-approved paid question
  in a local browser run (`ask_enabled=true`) shows the button, starters,
  tool lines, streamed text and a working internal link.

- [x] **Step 7 - Drawer, unhappy paths and accessibility**
  - A Stop button aborts the fetch.
  - On `done`: the streamed text is replaced by `done.text` (authoritative:
    it drops a pre-tool "let me check" and applies the refusal text);
    `truncated` and `iteration_limit` add a gray note; `error` or a thrown
    fetch error shows `ErrorState`-style copy with Retry.
  - Links are react-router `Link`s; following one closes the drawer.
    Closing the drawer or sending a new question aborts any running stream.
  - Accessibility: the answer region is `aria-live="polite"` and
    `aria-busy` while running (status lines announced, deltas not
    re-announced token by token); focus goes to the input on open and back
    to the Ask button on close; Escape closes; every control has a label;
    text at least 11px; theme variables only, no green or red (nothing in
    the answer is a signal).
  *Done when:* with `ask_enabled=true` locally and a real key (owner
  approval, each question is paid), a desktop and a 390px browser run show
  the button, starters, tool status, streamed answer, working internal
  links, Stop, an error state (API stopped mid-question), and keyboard-only
  use; with `ask_enabled=false` the button is absent and `POST /ask` is 404.
  Screenshots in `blueprint/reference/47c/`.

- [x] **Step 8 - Docs and final gate** - `AGENTS.md` Ask section
  (`ask_enabled`, routes, production guard, a curl example for the stream)
  and the local interview guide if present (streaming tool loop, SSE over
  POST, link allow-list). The overview refresh stays `/overview`'s job.
  *Done when:* the full Verify command passes and the docs name the guard
  that 47d must remove.

## Files / areas

| Area | Files |
|---|---|
| API core | `app/core/production_settings.py`, `app/core/rate_limits.py` |
| API services | `app/services/ask/stream.py` (new), `app/services/ask/loop.py` (owner, Step 2), `app/services/ask/chat.py` (optional) |
| API route | `app/routers/ask.py` (new), `app/main.py`, `app/config.py`, `app/schemas/ask.py` (new) |
| API tests | `test_ask_stream.py`, `test_ask_loop.py`, `test_ask_route.py`, `test_production_settings.py`, rate-limit tests |
| Web | `types/ask.ts`, `utils/askStream.ts`, `utils/askAnswer.ts`, `utils/askStatus.ts` (+ tests), `api/ask.ts`, `hooks/useAskStatus.ts`, `components/ask/AskDrawer.tsx`, `ask.css`, `App.tsx` |
| Docs | `AGENTS.md`, local interview guide |

## Data / contracts

No schema, migration or new dependency.

**Load-bearing for 47d and 47e:**

```text
GET  /ask/status -> 200 {"enabled": bool}
POST /ask {"question": str (1-500 chars)}
  404 disabled | 422 bad question | 503 no key | 429 rate limit (47d adds daily)
  200 text/event-stream, frames in order:
    event: tool_start  data: {"name": str, "sport": "nba"|"nfl"|"tennis"|null}
    event: tool_end    data: {"name": str, "ok": bool}
    event: text        data: {"delta": str}
    : ping                                   (comment, every 10 s of silence)
  then exactly one of:
    event: done        data: {"stop": AskStop, "text": str}
    event: error       data: {"message": str}   (fixed copy, never exception text)
```

- `done.text` is authoritative over the concatenated deltas.
- No usage, token counts, tool inputs beyond `sport`, or tool data rows ever
  reach the client. 47d logs usage server-side from `AskOutcome`.
- `AskEvent` gains `TextDelta(text)`; `ToolStarted`, `ToolFinished` and
  `AskOutcome` are unchanged, so 47e reads `tool_calls` and `text` as before.
- 47d's per-IP limit and spend cap wrap `POST /ask` before the stream opens,
  so a refused question costs nothing.

## Testing

- Test gate on. Steps 1-5 ship pytest or Vitest tests; Steps 6-7 are UI and
  ride on browser evidence and the build.
- Route tests use the 47b fake client (now with `messages.stream`), a
  stubbed `run_tool`, and a patched session factory; CI stays keyless with
  its dummy `DATABASE_URL`.
- Live checks spend real money (about a tenth of a cent a question at 47b's
  measurement); ask before each batch.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Coach Step 2, don't write it.** Load the `claude-api` skill first for the
  `messages.stream` shapes (text events, `get_final_message`, thinking
  blocks preserved on the final message). Write the fake and tests, explain,
  review the owner's diff with a hint before a fix.
- **Thinking blocks still go back unmodified:** use the final message's
  `content`, never a list rebuilt from deltas.
- **One session per request, tools sequential** (47b's rule). Never share the
  request's session across concurrent questions.
- **Signal honesty:** the drawer adds no color, ranking or pick wording; the
  model's text is the only claim, and its tools carry 47a's `signal`.
- **Production stays off.** Do not touch `render.yaml` or Render env vars.
  The guard in `validate_production_settings` is the enforcement; 47d
  deletes it in the same diff that adds the limits.
- **Vite proxy:** confirm `/api/ask` streams unbuffered in dev; if it buffers,
  fix in `vite.config.ts`, not by polling.
- **Reference-only wording** in the drawer note must match `SPORT_STATUS`;
  if they ever disagree, `SPORT_STATUS` wins.
- No em dashes in new code, comments or docs. Text at least 11px.
- **For 47e (found in Step 6's live run, 2026-10-28):** asked "Who plays in
  the NBA tonight?", the model wrote "13 NBA games" above a correct list of 12;
  `get_slate` returned 12 rows, untruncated (checked with the preview CLI). A
  count stated in prose must match the tool's rows: a required-fact eval case,
  not a 47c bug.

## Completion evidence (2026-10-28)

- **Built as planned, with one deliberate change:** the textarea stays
  editable while an answer runs (only sending is blocked), so keyboard focus
  is never dropped mid-answer. The owner wrote Step 2's streaming change in
  `loop.py` and `chat.py` against tests written first; review edits were
  whitespace only.
- **Verify:** web typecheck, 974 web tests and build; 4,668 API tests.
- **Live paid run** (owner, `claude-haiku-5-5`): "Who plays in the NBA
  tonight?" streamed one `get_slate` status line and the answer; all 12
  matchups rendered as internal links, one navigated to `#/nba/game/21261`
  and closed the drawer; the answer stated no validated picks. List bullets
  were missing (Tailwind base styles) and were fixed in Step 6.
- **Free browser run** (`ANTHROPIC_BASE_URL` pointed at a local socket that
  never answers): focus on open, NFL starters on `/nfl`, Thinking state with
  live region and `aria-busy`, Stop, the server `error` frame with fixed copy
  and Retry (traceback only in the server log), Escape returning focus to the
  Ask button, 390px phone (full-width drawer, no horizontal scroll, smallest
  text 11px). With Ask off: no button, `{"enabled":false}`, `POST /ask` 404.
  Screenshots: `blueprint/reference/47c/01` to `06`.
- **Not verified live:** the `truncated` and `iteration_limit` notes (unit
  tests only); behaviour on Render (production refuses `ask_enabled` until
  47d).
- **Known limits:** with the Vite dev proxy, a dead API reads as a 500
  ("Something went wrong"); in production it is a network failure ("Couldn't
  reach Lineform"). Crossing the phone breakpoint starts an empty drawer.
  `askAnswer.ts` route patterns must track `ask_links.py`.
