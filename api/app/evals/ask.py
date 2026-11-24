"""Run the Ask Lineform evals (47e): every question in ask_questions.json through
the real tool loop, against the local database and the real Anthropic API, then
check each answer and print a pass rate and the estimated cost. Every real run
is a paid request, so it needs --confirm-spend. Never part of Verify or CI.

    python -m app.evals.ask --dry-run
    python -m app.evals.ask --confirm-spend
    python -m app.evals.ask --confirm-spend --only nba-slate-tonight --out
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, settings
from app.core.ask_cost import AskPrices, estimate_cost_usd
from app.core.ask_eval import CaseResult, EvalCase, EvalFileError, OutcomeView, ToolCallView, check_case, parse_cases
from app.core.ask_messages import CENTRAL, AskUsage
from app.core.production_settings import is_production
from app.ml.registry import ModelRegistry
from app.services.ask.client import AskNotConfigured, ask_prices, make_client
from app.services.ask.loop import AskOutcome, run_ask
from app.services.ask.tools import EXECUTORS, ToolContext

QUESTIONS_PATH = Path(__file__).with_name("ask_questions.json")
API_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = API_DIR / "data" / "ask-evals"
MODELS_DIR = API_DIR / "models"

Answer = Callable[[EvalCase, AskUsage], Awaitable[AskOutcome]]
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class SetupError(Exception):
    """A problem found before any question is asked; the CLI exits 2."""


@dataclass
class CaseRun:
    case: EvalCase
    usage: AskUsage
    cost_usd: float
    outcome: AskOutcome | None = None
    result: CaseResult | None = None
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.result is not None and self.result.passed


def load_cases(path: Path = QUESTIONS_PATH) -> list[EvalCase]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SetupError(f"cannot read {path.name}: {error}") from error
    try:
        return parse_cases(raw, EXECUTORS.keys())
    except EvalFileError as error:
        raise SetupError(f"{path.name}: {error}") from error


def select_cases(cases: Sequence[EvalCase], only: str | None) -> list[EvalCase]:
    if not only:
        return list(cases)
    wanted = [part.strip() for part in only.split(",") if part.strip()]
    known = {case.id for case in cases}
    unknown = [case_id for case_id in wanted if case_id not in known]
    if unknown:
        raise SetupError(f"--only names unknown cases: {', '.join(unknown)}")
    return [case for case in cases if case.id in wanted]


def outcome_view(outcome: AskOutcome) -> OutcomeView:
    return OutcomeView(
        text=outcome.text,
        stop=outcome.stop,
        tool_calls=tuple(ToolCallView(c.name, c.input, c.is_error, c.content) for c in outcome.tool_calls),
    )


def make_answer(
    client: AsyncAnthropic, config: Settings, sessions: SessionFactory,
    registry: ModelRegistry | None, now: dt.datetime,
) -> Answer:
    """Each case gets its own database session, so one case's failed
    transaction never leaks into the next."""
    async def answer(case: EvalCase, usage: AskUsage) -> AskOutcome:
        async with sessions() as db:
            ctx = ToolContext(db, registry, now, is_production(config.api_env))
            return await run_ask(client, case.question, ctx, config, usage=usage)
    return answer


async def run_case(case: EvalCase, answer: Answer, prices: AskPrices) -> CaseRun:
    usage = AskUsage()
    try:
        outcome = await answer(case, usage)
    except anthropic.APIError as error:
        # Usage is shared with the loop, so tokens spent before the failure still count.
        return CaseRun(case, usage, estimate_cost_usd(usage, prices), error=f"{type(error).__name__}: {error}")
    return CaseRun(
        case, usage, estimate_cost_usd(usage, prices),
        outcome=outcome, result=check_case(case, outcome_view(outcome)),
    )


async def run_cases(
    cases: Sequence[EvalCase], answer: Answer, prices: AskPrices,
) -> AsyncIterator[CaseRun]:
    for case in cases:
        yield await run_case(case, answer, prices)


def total_tokens(usage: AskUsage) -> int:
    return (usage.input_tokens + usage.output_tokens
            + usage.cache_read_input_tokens + usage.cache_creation_input_tokens)


def format_case(run: CaseRun) -> str:
    if run.error is not None:
        return f"ERROR {run.case.id}\n    ! {run.error}"
    assert run.outcome is not None and run.result is not None
    tools = ", ".join(call.name for call in run.outcome.tool_calls) or "none"
    lines = [
        f"{'PASS' if run.passed else 'FAIL'} {run.case.id}  {run.outcome.stop}  tools: {tools}  "
        f"{run.usage.requests} req  {total_tokens(run.usage):,} tok  ${run.cost_usd:.4f}"
    ]
    lines += [f"    - {failure}" for failure in run.result.failures]
    if run.result.ungrounded_numbers:
        lines.append(f"    ? ungrounded numbers: {', '.join(run.result.ungrounded_numbers)}")
    return "\n".join(lines)


def run_stamp(now: dt.datetime) -> str:
    local = now.astimezone(CENTRAL)
    return f"{local:%Y-%m-%d} {local.hour % 12 or 12}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'} CT"


def format_summary(runs: Sequence[CaseRun], model: str, now: dt.datetime) -> str:
    usage = AskUsage()
    for run in runs:
        usage.requests += run.usage.requests
        usage.input_tokens += run.usage.input_tokens
        usage.output_tokens += run.usage.output_tokens
        usage.cache_read_input_tokens += run.usage.cache_read_input_tokens
        usage.cache_creation_input_tokens += run.usage.cache_creation_input_tokens
    passed = sum(run.passed for run in runs)
    errors = sum(run.error is not None for run in runs)
    return "\n".join([
        f"Passed {passed} of {len(runs)}" + (f" ({errors} error{'s' if errors != 1 else ''})" if errors else ""),
        f"Requests {usage.requests}, input {usage.input_tokens:,}, output {usage.output_tokens:,}, "
        f"cache read {usage.cache_read_input_tokens:,}, cache write {usage.cache_creation_input_tokens:,}",
        f"Estimated cost ${sum(run.cost_usd for run in runs):.4f}",
        f"Run {run_stamp(now)}, model {model}",
    ])


def results_json(runs: Sequence[CaseRun], model: str, now: dt.datetime) -> dict[str, object]:
    return {
        "run_at": now.isoformat(),
        "model": model,
        "passed": sum(run.passed for run in runs),
        "total": len(runs),
        "cost_usd": round(sum(run.cost_usd for run in runs), 6),
        "cases": [
            {
                "id": run.case.id,
                "question": run.case.question,
                "passed": run.passed,
                "error": run.error,
                "stop": run.outcome.stop if run.outcome else None,
                "answer": run.outcome.text if run.outcome else None,
                "tool_calls": [
                    {"name": c.name, "input": c.input, "is_error": c.is_error}
                    for c in (run.outcome.tool_calls if run.outcome else [])
                ],
                "failures": list(run.result.failures) if run.result else [],
                "ungrounded_numbers": list(run.result.ungrounded_numbers) if run.result else [],
                "requests": run.usage.requests,
                "tokens": total_tokens(run.usage),
                "cost_usd": round(run.cost_usd, 6),
            }
            for run in runs
        ],
    }


def exit_code(runs: Sequence[CaseRun]) -> int:
    return 0 if runs and all(run.passed for run in runs) else 1


def write_results(runs: Sequence[CaseRun], model: str, now: dt.datetime) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{now.astimezone(CENTRAL):%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(results_json(runs, model, now), indent=2), encoding="utf-8")
    return path


async def _run(cases: list[EvalCase], out: bool) -> int:
    # Imported here so --dry-run and the tests never build a database engine.
    from app.db.pool import SessionLocal, engine

    try:
        client = make_client(settings)
    except AskNotConfigured as error:
        print(f"{error}: add it to api/app/.env", file=sys.stderr)
        return 2
    now = dt.datetime.now(dt.UTC)
    answer = make_answer(client, settings, SessionLocal, ModelRegistry(MODELS_DIR), now)
    runs: list[CaseRun] = []
    try:
        async for run in run_cases(cases, answer, ask_prices(settings)):
            runs.append(run)
            print(format_case(run), flush=True)
    finally:
        await client.close()
        await engine.dispose()
    print()
    print(format_summary(runs, settings.ask_model, now))
    if out:
        print(f"Results: {write_results(runs, settings.ask_model, now)}")
    return exit_code(runs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="validate the questions; no API call")
    parser.add_argument("--confirm-spend", action="store_true", help="required for a real, paid run")
    parser.add_argument("--only", help="comma-separated case ids to run")
    parser.add_argument("--out", action="store_true", help="also write results JSON to api/data/ask-evals/")
    args = parser.parse_args(argv)
    try:
        cases = select_cases(load_cases(), args.only)
    except SetupError as error:
        print(error, file=sys.stderr)
        return 2
    if args.dry_run:
        for case in cases:
            print(f"{case.id}: {case.question}")
        print(f"\n{len(cases)} case{'s' if len(cases) != 1 else ''} valid; no API call made")
        return 0
    if not args.confirm_spend:
        print(f"{len(cases)} cases would each make paid API requests: pass --confirm-spend", file=sys.stderr)
        return 2
    return asyncio.run(_run(cases, args.out))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(main())
