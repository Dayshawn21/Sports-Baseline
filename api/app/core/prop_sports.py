"""Per-sport PrizePicks prop configuration and league selection (17c).

A new sport adds one `SportPropConfig`; league selection and market mapping
read it instead of assuming NFL.

Pure: no DB, no I/O.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

FULL_GAME_SEGMENT = "full_game"


@dataclass(frozen=True)
class SportPropConfig:
    code: str
    # PrizePicks league name for the full game; segments append a suffix (NFL1H).
    league_prefix: str
    # Normalized league suffix -> segment, e.g. "1H" -> "first_half".
    segment_suffixes: Mapping[str, str]
    board_segments: frozenset[str]
    # Lowercased provider stat name -> market.
    market_aliases: Mapping[str, str]
    # What the sport's grading period is called in reports: "week" for NFL.
    period_label: str


def _normalize(name: str) -> str:
    return re.sub(r"[\s_-]+", "", name.strip().upper())


def segment_for_league_name(name: str, config: SportPropConfig) -> str | None:
    """The segment a PrizePicks league covers, or None if the league is not this sport's.

    An unknown suffix is None rather than full game, so a new provider league
    (NFLDRAFT) is never read as game lines. The prefix must start the name, so
    a WNBA league never matches an NBA config.
    """
    normalized = _normalize(name)
    prefix = _normalize(config.league_prefix)
    if not normalized.startswith(prefix):
        return None
    suffix = normalized[len(prefix):]
    if not suffix:
        return FULL_GAME_SEGMENT
    return config.segment_suffixes.get(suffix)


def board_leagues(leagues: Iterable[dict], config: SportPropConfig) -> list[tuple[int, str, str]]:
    """(league id, name, segment) for every catalog league in one of the sport's board segments."""
    selected: list[tuple[int, str, str]] = []
    for item in leagues:
        name = (item.get("attributes") or {}).get("name", "")
        segment = segment_for_league_name(name, config)
        if segment in config.board_segments:
            selected.append((int(item["id"]), name, segment))
    return selected


def market_for_stat(stat_type: str, config: SportPropConfig) -> str | None:
    return config.market_aliases.get(stat_type.strip().lower())
