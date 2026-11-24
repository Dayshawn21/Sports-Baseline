"""Ask Lineform one question from the command line, against the local database
and the real Anthropic API, and print the answer, each tool call and the token
usage. Needs ANTHROPIC_API_KEY in api/app/.env; every run is a paid request.

    python -m app.services.ask.chat who plays in the NBA tonight?
    python -m app.services.ask.chat "What are the top tennis picks today?"
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import anthropic

from app.config import settings
from app.core.production_settings import is_production
from app.db.pool import SessionLocal, engine
from app.ml.registry import ModelRegistry
from app.services.ask.client import AskNotConfigured, make_client
from app.services.ask.loop import AskEvent, AskOutcome, TextDelta, ToolStarted, run_ask
from app.services.ask.tools import ToolContext

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def question_from(args: list[str]) -> str:
    question = " ".join(args).strip()
    if not question:
        raise ValueError("ask a question, e.g. who plays in the NBA tonight?")
    return question


def format_event(event: AskEvent) -> str:
    if isinstance(event, ToolStarted):
        return f"-> {event.name} {json.dumps(event.input)}"
    line = f"<- {event.name} {'ok' if event.ok else 'error'}"
    return f"{line}: {event.note}" if event.note else line


def format_outcome(outcome: AskOutcome) -> str:
    usage = outcome.usage
    lines = [outcome.text or "(no answer)", "", f"stop: {outcome.stop}", f"tools: {len(outcome.tool_calls)}"]
    for call in outcome.tool_calls:
        status = "error" if call.is_error else "ok"
        lines.append(f"  {call.name} {json.dumps(call.input)}  {status}  {call.ms} ms")
    lines.append(
        f"usage: {usage.requests} requests, {usage.input_tokens:,} input, {usage.output_tokens:,} output, "
        f"{usage.cache_read_input_tokens:,} cache read, {usage.cache_creation_input_tokens:,} cache write"
    )
    return "\n".join(lines)


async def print_event(event: AskEvent) -> None:
    if isinstance(event, TextDelta):
        print(event.text, end="", flush=True)
        return
    print(format_event(event), file=sys.stderr)


async def _main(question: str) -> int:
    try:
        client = make_client(settings)
    except AskNotConfigured as error:
        print(f"{error}: add it to api/app/.env", file=sys.stderr)
        return 2
    try:
        async with SessionLocal() as db:
            ctx = ToolContext(db, ModelRegistry(MODELS_DIR), dt.datetime.now(dt.UTC), is_production(settings.api_env))
            outcome = await run_ask(client, question, ctx, settings, on_event=print_event)
    except anthropic.APIError as error:
        print(f"Anthropic API error: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    finally:
        await client.close()
        await engine.dispose()
    print(format_outcome(outcome))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="+", help="the question; quotes are optional")
    args = parser.parse_args()
    try:
        question = question_from(args.question)
    except ValueError as error:
        parser.error(str(error))
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(question)))


if __name__ == "__main__":
    main()
