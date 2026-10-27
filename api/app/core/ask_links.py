"""Lineform page paths that Ask Lineform tool results cite.

Paths are router paths without the `#`; the web's HashRouter adds it when it
renders a link. `test_ask_links.py` pins every builder to the web's routes.
"""
from __future__ import annotations

import datetime as dt
from typing import Literal

AskSport = Literal["nba", "nfl", "tennis"]
PlayerSport = Literal["nfl", "tennis"]
BoardSport = Literal["nba", "tennis"]

_SLATE: dict[AskSport, str] = {"nba": "/nba", "nfl": "/nfl", "tennis": "/"}


def slate_path(
    sport: AskSport,
    *,
    date: dt.date | None = None,
    season: int | None = None,
    week: int | None = None,
) -> str:
    """NBA slates take an Eastern date, NFL a season and week; the tennis slate takes neither."""
    base = _SLATE[sport]
    if sport == "nba" and date is not None:
        return f"{base}?date={date.isoformat()}"
    if sport == "nfl" and season is not None and week is not None:
        return f"{base}?season={season}&week={week}"
    return base


def game_path(sport: AskSport, game_id: int) -> str:
    if sport == "tennis":
        return f"/tennis/match/{game_id}"
    return f"/{sport}/game/{game_id}"


def player_path(sport: PlayerSport, player_id: int) -> str:
    return f"/{sport}/player/{player_id}"


def model_path(sport: AskSport) -> str:
    return f"/{sport}/model"


def board_path(sport: BoardSport, date: dt.date | None = None) -> str:
    base = f"/{sport}/board"
    if sport == "nba" and date is not None:
        return f"{base}?date={date.isoformat()}"
    return base
