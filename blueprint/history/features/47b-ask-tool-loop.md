# Feature: Ask Lineform tool loop

**From build-plan:** feature 47b (parent 47, Ask Lineform)
**Status:** complete (2026-10-28)
**Branch:** `feature/47b-ask-tool-loop` (from 47a's `466b2df`, which
fast-forwards onto `master` first)

## Goal

Turn one question into one answer: send the question to Claude with 47a's
tools and system prompt, run every tool Claude asks for through `run_tool`,
hand the results back, and repeat until Claude answers or a limit is hit. The
result records the answer, how it stopped, every tool call and the token
usage, so 47c can stream it and 47d can price it.

This is the owner's learning feature. **The owner writes the loop code; Claude
coaches, writes the fake client and the tests that define each step's
behaviour, and reviews.** Each step's review explains the idea behind it.

## In scope

- An `ask_effort` setting (default `"low"`) beside 47a's four `ask_*` fields.
- Pure message helpers in `app/core/ask_messages.py`: the dated user turn, the
  `tool_result` block, usage totals, stop-reason mapping.
- An Anthropic client factory that reads the key only through `Settings`.
- `run_ask` in `app/services/ask/loop.py`: the Messages API tool loop, covering
  `stop_reason` handling, `tool_result` blocks, parallel calls, tool errors,
  unknown tools and the iteration limit.
- An optional async event callback for tool status, which 47c streams.
- Mocked-client tests built from real SDK types. No test calls the API.
- A developer CLI, `python -m app.services.ask.chat "<question>"`, for a live
  run with the owner's key: answer, tool trace, usage and cache reads.

## Out of scope

- Streaming, `POST /ask`, SSE and any web code (47c). 47b calls
  `messages.create`; 47c moves the model call to `messages.stream` and keeps the
  loop's shape.
- Follow-up questions and multi-turn history. v1 is one question per call, and
  the plan stores no conversation. If 47c's drawer sends prior turns, 47c's spec
  extends `run_ask`'s input.
- Rate limits, the spend cap and cost logging (47d). 47b only *returns* usage.
- Evals (47e). Prompt or tool changes, except a bug fix the loop exposes,
  which is raised at review first.
- The SDK's beta tool runner. The plan chose a hand-written loop so the owner
  sees every step.
- Running tools concurrently (see Notes: one `AsyncSession` per request).

## Build loop

Build one step at a time, never the whole feature at once.

1. Plan mode lays out the step before any code.
2. The AI implements just that step.
3. It shows the diff (not full files); you read it and understand it.
4. You approve, then choose whether to commit a checkpoint or roll straight on.
   Checkpoints are optional; `/complete` makes the real feature-level commit at the end.

Never accept a step you haven't read. If a diff is too big to review, the step was too big, so split it.

**In this feature:** for each step Claude first writes the failing tests and
explains the concept; the owner writes the code until they pass; Claude then
reviews the owner's diff (correctness, edge cases, project conventions) and
the step is approved as usual.

## Build steps

- [x] **Step 1 - Message helpers** - `app/core/ask_messages.py`, pure:
  - `user_turn(question, now) -> str`: `"Today is Tuesday, October 27, 2026,
    3:05 PM CT.\n\n<question>"`, with the date and time in `America/Chicago`
    (the prompt says the message starts with them).
  - `tool_result_block(tool_use_id, content, is_error=False)`: a
    `ToolResultBlockParam` dict; `is_error` is set only when true.
  - `AskUsage` (dataclass: `requests`, `input_tokens`, `output_tokens`,
    `cache_read_input_tokens`, `cache_creation_input_tokens`) with
    `add(usage)` that treats a missing or `None` cache field as 0.
  - `stop_for(stop_reason) -> AskStop` (see contracts).
  *Concept:* the conversation is a list the client owns and resends; the
  model keeps no state between calls. *Done when:* `test_ask_messages.py`
  passes, covering the CT clock across the daylight-saving change, blank
  `is_error`, usage summing with missing cache fields and every listed
  stop reason plus an unknown one.

- [x] **Step 2 - Client, request shape and the no-tool answer** - add
  `ask_effort` to `Settings`. `app/services/ask/client.py`:
  `make_client(settings) -> AsyncAnthropic`, raising `AskNotConfigured` when
  `anthropic_api_key` is empty (timeout 60 s, `max_retries` 2). `run_ask`'s
  first version sends one request and handles a final answer:
  `model`, `max_tokens`, `output_config={"effort": ...}` from Settings;
  `system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control":
  {"type": "ephemeral"}}]`; `tools=TOOLS`; no `temperature` or `thinking`
  (Haiku 5.5 400s on sampling parameters and thinks adaptively by default).
  The answer is the joined `text` blocks, read by block type, never
  `content[0]`. `end_turn` returns `answered`; `max_tokens` returns
  `truncated` with any text so far; `refusal` returns `refused` with a fixed
  sentence; anything else returns `error`.
  *Concept:* the cache breakpoint on the system block covers tools then
  system, the stable prefix; the dated question sits after it.
  *Done when:* tests with a fake client show the captured request (cache
  breakpoint present, `TOOLS` sent unchanged, no sampling parameters), a
  thinking-then-text response returns only the text, the three non-tool stops
  map as above, and an empty key raises `AskNotConfigured`.

- [x] **Step 3 - One tool round, then parallel calls** - on `tool_use`, append
  the assistant turn with its full `content` (thinking blocks included,
  unmodified), run each `tool_use` block through `run_tool` **in order, one at
  a time**, and send **all** results back in **one** user message as
  `tool_result` blocks whose content is `ToolResult.model_dump_json()`. Loop
  until a non-tool stop. Record each call as a `ToolCallRecord`.
  *Concept:* `tool_use_id` pairing, and why parallel results go in one
  message (splitting them teaches the model to stop calling in parallel).
  *Done when:* tests show a one-tool round trip ends `answered`; two
  `tool_use` blocks in one turn yield one user message with two results in
  the blocks' order and matching ids; the second request's messages are
  user, assistant (with its thinking block), user; and `tool_calls` lists
  both calls.

- [x] **Step 4 - Tool errors and unknown tools** - `UnknownToolError` and
  `ToolInputError` become `is_error` results carrying their message (written
  for the model to correct). Any other exception from a tool is logged with
  its traceback, the session is rolled back (`await ctx.db.rollback()`) so
  later tools can still query, and the model gets a fixed `is_error` text
  ("<tool> failed on the server; tell the user this data could not be
  checked."), never the exception text (37d's rule). A `max_tokens` stop
  whose content holds a `tool_use` block runs no tool (its input may be cut
  off) and returns `truncated`.
  *Concept:* errors are data for the model, not crashes for the user.
  *Done when:* tests show an unknown tool and a bad input each come back as
  `is_error` with their message and the loop continues to an answer; a
  raising executor triggers one rollback, returns the fixed text and leaks
  no exception text; and a truncated tool call runs nothing.

- [x] **Step 5 - Iteration limit** - at most `ask_max_tool_iterations` (5)
  tool rounds. If the model still asks for tools after the last round, send
  one final request with `tool_choice={"type": "none"}` so it answers from
  what it has; that answer returns stop `iteration_limit`. At most
  `ask_max_tool_iterations + 1` requests per question.
  *Concept:* bounding cost and latency, and degrading to a partial answer
  instead of an error. *Done when:* a fake that always asks for a tool
  produces exactly 5 tool rounds and 6 requests, the last with
  `tool_choice` none, and returns `iteration_limit` with its text; a limit
  of 1 behaves the same with 2 requests.

- [x] **Step 6 - Tool-status events** - optional
  `on_event: Callable[[AskEvent], Awaitable[None]] | None`. Before each tool
  runs, emit `ToolStarted(name, input)`; after, `ToolFinished(name, ok,
  note)`. `note` is the `ToolResult.note` (or None), never data rows. An
  `on_event` exception propagates (47c's disconnect handling decides).
  *Done when:* tests show the event order for a two-call turn, `ok` false for
  an `is_error` result, and the loop behaves identically with no callback.

- [x] **Step 7 - Developer chat CLI and live smoke** -
  `python -m app.services.ask.chat "<question>"` builds a real `ToolContext`
  (local database, model registry, `now`, `production` false), runs
  `run_ask`, and prints the answer, the stop, each tool call (name, input,
  ok, ms) and the usage. It never prints the key. Document it under "Ask
  Lineform" in `AGENTS.md`. *Done when:* a test covers its argument parsing
  and output formatting with a stubbed `run_ask` (no API call), and the owner
  runs two different questions with their key and sees an answer citing
  Lineform paths and `cache_read_input_tokens > 0` on the second run (the
  shared tools-plus-system prefix is far above Haiku 5.5's 512-token cache
  minimum). The live run is manual evidence, never part of Verify or CI.

## Files / areas

- `api/app/config.py` (`ask_effort`)
- New: `api/app/core/ask_messages.py`
- New: `api/app/services/ask/client.py`, `loop.py`, `chat.py`
- New tests: `api/tests/test_ask_messages.py`, `test_ask_loop.py`,
  `test_ask_chat.py`
- `AGENTS.md` (chat CLI), and the local interview guide if it exists (the
  hand-written tool loop is a strong interview example)

## Data / contracts

No schema or migration. No new dependency (`anthropic==2.3.0` from 47a).

**Load-bearing for 47c, 47d and 47e:**

```text
async def run_ask(
    client: AsyncAnthropic, question: str, ctx: ToolContext,
    settings: Settings, on_event: Callable[[AskEvent], Awaitable[None]] | None = None,
) -> AskOutcome

AskOutcome
  text: str                     # the answer; "" only for stop "error"
  stop: AskStop                 # answered | truncated | refused | iteration_limit | error
  tool_calls: list[ToolCallRecord]
  usage: AskUsage               # summed over every request (47d prices it)

ToolCallRecord
  name: str
  input: dict[str, object]      # as the model sent it
  is_error: bool
  ms: int

AskEvent = ToolStarted(name, input) | ToolFinished(name, ok, note)
```

- `stop_for` maps `end_turn` to `answered`, `max_tokens` to `truncated`,
  `refusal` to `refused`, `tool_use` to continue, and everything else
  (`pause_turn`, `stop_sequence`, unknown) to `error`. There are no server
  tools, so `pause_turn` is unexpected here.
- SDK errors (`RateLimitError`, `APIStatusError`, `APIConnectionError`)
  propagate from `run_ask` unchanged; 47c maps them to a user-safe message.
- 47e's evals read `tool_calls` (expected tools) and `text` (required facts).

## Testing

- The test gate is on. Steps 1-6 ship pytest tests; Step 7 tests the CLI's
  pure parts.
- **The fake client** lives in `test_ask_loop.py`: an object with
  `messages.create(**kwargs)` that records each call's kwargs and returns
  scripted responses built from real SDK types (`anthropic.types.Message`,
  `TextBlock`, `ThinkingBlock`, `ToolUseBlock`, `Usage`), so a shape mistake
  fails the test. `run_tool` is stubbed with a fake executor table so no
  database is touched; one test uses the real `run_tool` with a bad input to
  prove the `ToolInputError` path end to end.
- No test needs `ANTHROPIC_API_KEY`; CI stays keyless with its dummy
  `DATABASE_URL`.
- Final gate: `npm --prefix web run verify && cd api && python -m pytest`.

## Notes for the AI

- **Coach, don't write the loop.** Write the tests and the fake client, explain
  the concept, then let the owner write `loop.py`, `client.py` and
  `ask_messages.py`. Review their diff like any other: point to the line and
  the failing case, and offer a hint before a fix. Write code only when the
  owner asks for it, and say so in the review.
- **Load the `claude-api` skill** before reviewing Steps 2-5; the shapes come
  from it, not memory (Haiku 5.5: adaptive thinking on by default, effort
  default `medium`, sampling parameters 400, prefill 400, refusals with no
  server-side fallback, forced `tool_choice` accepted but unused here).
- **Thinking blocks go back unmodified** in the assistant turn, even when
  their text is empty; editing or dropping them invalidates the cache and
  later thinking. Never rebuild the assistant turn from the text alone.
- **Tools run one at a time.** Every tool shares `ctx.db`, and an
  `AsyncSession` is not safe for concurrent use. Parallel calls are still
  answered in one user message; they just execute sequentially. Revisit only
  with a session per tool, which is out of scope.
- **`effort` low** keeps thinking short so `ask_max_tokens = 1024` leaves room
  for the answer; 47e can tune it. Changing effort or `TOOLS` mid-request
  breaks the cache, so both are fixed per request.
- **No `os.environ`.** The key comes from `Settings` and is never logged,
  printed or returned. Error responses carry no exception text.
- **Signal honesty is unchanged:** the loop passes `ToolResult` JSON through
  untouched, so 47a's `signal` labels reach the model as built.
- No em dashes in new code, comments or docs.

## Completion evidence (2026-10-28)

- **Built as planned.** The owner wrote `ask_messages.py`, `client.py`,
  `loop.py` and `chat.py` against tests written first; reviews made only
  whitespace and import-order tidies. The SDK's `omit` sentinel leaves
  `tool_choice` out of normal rounds, so their requests stay byte-identical.
  `model_context_window_exceeded`, a stop reason the spec did not list, maps
  to `error` with the other unknown reasons.
- **Tests:** `test_ask_messages.py` (16), `test_ask_loop.py` (33),
  `test_ask_chat.py` (8). None needs `ANTHROPIC_API_KEY`.
- **Verify:** `npm --prefix web run verify && cd api && python -m pytest`
  passed (web typecheck, tests and build; 4,626 API tests).
- **Live run** (`python -m app.services.ask.chat`, local database,
  `claude-haiku-5-5`, effort low):
  - "who plays in the NBA tonight?": one `get_slate` call, 13 games listed
    with `/nba/game/...` links and "no validated picks"; 2 requests, 2,725
    input, 576 output, 3,207 cache read, 3,207 cache write.
  - "how has the NBA model done this season?": one
    `get_model_track_record` call, every slice reported as accruing with
    its sample and break-even; 2 requests, 943 input, 421 output, 6,414
    cache read, 0 cache write.
  - The cached tools-plus-system prefix is 3,207 tokens. Each question cost
    about a tenth of a cent.
- **Latency for 47c:** the cold track-record tool took 15.0 s and the slate
  tool 4.5 s (service time, not the loop), so the chat panel needs the
  Step 6 tool-status events.
- **Not verified:** no hosted run; `ask_enabled` and `POST /ask` are 47c.
