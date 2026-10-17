"""NBA season labels, the regular-season week, and ESPN season types (item 20a).

The week is NBA's prop period: the shared ranking rule needs four whole
periods, so a week keeps that minimum a month of games, as for NFL.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

# ESPN season types: 1 preseason (never stored), 2 regular, 3 playoffs, 5 play-in.
_GAME_TYPES = {2: "REG", 3: "PST", 5: "PIN"}
REGULAR_SEASON = "REG"
# Stored from ESPN's site API only, never projected or graded.
PRESEASON = "PRE"
ESPN_PRESEASON_TYPE = 1
# ESPN's codes for the 30 franchises. Preseason also schedules overseas clubs
# (London Lions in 2026), which are not NBA teams and are never stored.
NBA_TEAM_CODES = frozenset({
    "ATL", "BKN", "BOS", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GS", "HOU", "IND", "LAC", "LAL", "MEM",
    "MIA", "MIL", "MIN", "NO", "NY", "OKC", "ORL", "PHI", "PHX", "POR", "SA", "SAC", "TOR", "UTAH", "WSH",
})


def stored_season(file_season: int) -> int:
    """hoopR and ESPN name a season by the year it ends; we store the year it starts."""
    return file_season - 1


def file_season(season: int) -> int:
    return season + 1


def current_nba_season(today: date) -> int:
    """The season in progress, or the one just finished before the next starts.

    Playoffs end in June and the next season opens in October, so a new season
    is counted from August, after the draft and Summer League.
    """
    return today.year if today.month >= 8 else today.year - 1


def game_type(espn_season_type: int) -> str | None:
    return _GAME_TYPES.get(espn_season_type)


def opening_night(regular_season_dates: Iterable[date]) -> date:
    return min(regular_season_dates)


def nba_week(game_date: date, opening: date) -> int:
    """Monday-to-Sunday week number, where week 1 holds opening night."""
    first_monday = opening - timedelta(days=opening.weekday())
    if game_date < first_monday:
        raise ValueError(f"{game_date} is before the week of opening night {opening}")
    return (game_date - first_monday).days // 7 + 1
