"""Run one Ask Lineform tool against the local database and print exactly what
the model would receive, with its size.

    python -m app.services.ask.preview get_top_props sport=nba limit=3
    python -m app.services.ask.preview find sport=nfl query=mahomes

Arguments are key=value pairs because Windows PowerShell strips the inner
quotes from a JSON argument. A single JSON object still works from bash.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from pydantic import JsonValue

from app.config import settings
from app.core.production_settings import is_production
from app.db.pool import SessionLocal, engine
from app.ml.registry import ModelRegistry
from app.services.ask.tools import ToolContext, ToolInputError, UnknownToolError, run_tool

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"


def parse_arguments(args: list[str]) -> dict[str, JsonValue]:
    """`key=value` pairs, or one JSON object. Values stay strings; the tool's
    input model converts them (e.g. "3" to 3, "2026-10-27" to a date)."""
    if len(args) == 1 and args[0].lstrip().startswith("{"):
        parsed = json.loads(args[0])
        if not isinstance(parsed, dict):
            raise ValueError("the JSON input must be an object")
        return parsed
    pairs: dict[str, JsonValue] = {}
    for arg in args:
        key, sep, value = arg.partition("=")
        if not sep or not key:
            raise ValueError(f"expected key=value, got {arg!r}")
        pairs[key] = value
    return pairs


async def _main(name: str, args: list[str]) -> int:
    try:
        raw = parse_arguments(args)
    except ValueError as error:
        print(f"invalid arguments: {error}", file=sys.stderr)
        return 2
    registry = ModelRegistry(MODELS_DIR) if raw.get("sport") == "tennis" else None
    try:
        async with SessionLocal() as db:
            ctx = ToolContext(db, registry, dt.datetime.now(dt.UTC), is_production(settings.api_env))
            result = await run_tool(name, raw, ctx)
    except (UnknownToolError, ToolInputError) as error:
        # Exactly the text the model receives as an is_error tool_result.
        print(error, file=sys.stderr)
        return 2
    finally:
        await engine.dispose()
    print(result.model_dump_json(indent=1))
    print(f"\n{len(result.model_dump_json())} characters (compact)", file=sys.stderr)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tool")
    parser.add_argument("arguments", nargs="*", help="key=value pairs, e.g. sport=nba limit=3")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.exit(asyncio.run(_main(args.tool, args.arguments)))


if __name__ == "__main__":
    main()
