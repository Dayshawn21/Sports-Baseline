"""PrizePicks NFL prop-line ingest, run through the shared pipeline in `prizepicks_props`.

NFL schedule and performance data stay in API-Sports. This module only snapshots
the player lines that PrizePicks publishes, and only for supported markets.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter

from app.core.prop_sports import board_leagues, market_for_stat
from app.ingest import prizepicks_props
from app.ingest.prizepicks_props import PrizePicksRateLimited
from app.nfl.markets import NFL_PROPS, SUPPORTED_NFL_PROP_MARKETS, NflPropMarket, NflPropSegment, segment_for_league_name
from app.services.sport_registry import prop_source


def market_for_prizepicks_stat(stat_type: str) -> NflPropMarket | None:
    """The modelled market for a PrizePicks stat; a line-only market is None here."""
    market = market_for_stat(stat_type, NFL_PROPS)
    return NflPropMarket(market) if market in SUPPORTED_NFL_PROP_MARKETS else None


def unmapped_stat_counts(items: list[dict]) -> Counter[str]:
    """Stat names the ingest skips, so a provider rename shows up in the log."""
    return prizepicks_props.unmapped_stat_counts(items, NFL_PROPS)


def is_full_game_nfl_league(name: str) -> bool:
    return segment_for_league_name(name) is NflPropSegment.FULL_GAME


def board_nfl_leagues(leagues: list[dict]) -> list[tuple[int, str, NflPropSegment]]:
    return [
        (league_id, name, NflPropSegment(segment))
        for league_id, name, segment in board_leagues(leagues, NFL_PROPS)
    ]


async def run(dry_run: bool = False) -> int:
    return await prizepicks_props.run(prop_source("nfl"), dry_run)


async def relink() -> int:
    """Re-resolve stored NFL lines to players and games without a provider request."""
    return await prizepicks_props.relink(prop_source("nfl"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Snapshot supported PrizePicks NFL prop lines")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--relink",
        action="store_true",
        help="re-resolve stored lines to players and games without fetching from the provider",
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.relink:
        print(asyncio.run(relink()))
        raise SystemExit(0)
    try:
        print(asyncio.run(run(args.dry_run)))
    except PrizePicksRateLimited as exc:
        print(exc)
        raise SystemExit(75)
