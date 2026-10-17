"""The NBA slate: one Eastern date's games with records and the latest market (item 20e1).

Display only: nothing here projects, rates or ranks.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_slate import Record, adjacent_dates, slate_date, team_records
from app.repositories import nba as nba_repo
from app.schemas.nba import (
    NbaLineMoveSchema, NbaMoneylineSchema, NbaRecordSchema, NbaSlateGameSchema, NbaSlateResponse, NbaSpreadSchema, NbaTotalSchema,
)


def _oriented(row: Mapping[str, object], first: str) -> tuple[int, int, float]:
    """The odds and first-side probability, with the `first` side (home or over) first."""
    first_odds, second_odds, probability = int(row["first_odds"]), int(row["second_odds"]), float(row["first_market_prob"])
    if row["first_side"] == first:
        return first_odds, second_odds, probability
    return second_odds, first_odds, 1.0 - probability


def _markets(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    markets: dict[str, object] = {"moneyline": None, "spread": None, "total": None}
    for row in rows:
        book, fetched_at = str(row["book"]), row["fetched_at"]
        if row["market"] == "moneyline":
            home, away, probability = _oriented(row, "home")
            markets["moneyline"] = NbaMoneylineSchema(book=book, home_odds=home, away_odds=away, home_win_probability=probability, fetched_at=fetched_at)
        elif row["market"] == "spread" and row["line"] is not None:
            home, away, _ = _oriented(row, "home")
            # A stored line is the first side's; the away side's line is its negation.
            line = float(row["line"]) if row["first_side"] == "home" else -float(row["line"])
            markets["spread"] = NbaSpreadSchema(book=book, home_line=line, home_odds=home, away_odds=away, fetched_at=fetched_at)
        elif row["market"] == "total" and row["line"] is not None:
            over, under, _ = _oriented(row, "over")
            markets["total"] = NbaTotalSchema(book=book, line=float(row["line"]), over_odds=over, under_odds=under, fetched_at=fetched_at)
    return markets


def _record(records: Mapping[str, Record], team: str) -> NbaRecordSchema:
    record = records.get(team, Record())
    return NbaRecordSchema(wins=record.wins, losses=record.losses)


def slate_game(
    game: Mapping[str, object],
    market_rows: Sequence[Mapping[str, object]],
    records: Mapping[str, Record],
    movement_rows: Sequence[Mapping[str, object]] = (),
    prop_line_count: int = 0,
) -> NbaSlateGameSchema:
    return NbaSlateGameSchema(
        **game,
        away_record=_record(records, str(game["away_team"])),
        home_record=_record(records, str(game["home_team"])),
        prop_line_count=prop_line_count,
        line_movement=[NbaLineMoveSchema(**{key: value for key, value in row.items() if key != "game_id"}) for row in movement_rows],
        **_markets(market_rows),
    )


def _by_game(rows: Sequence[Mapping[str, object]]) -> dict[object, list[Mapping[str, object]]]:
    grouped: dict[object, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(row["game_id"], []).append(row)
    return grouped


def slate_games(
    games: Sequence[Mapping[str, object]],
    market_rows: Sequence[Mapping[str, object]],
    records_by_season: Mapping[int, Mapping[str, Record]],
    movement_rows: Sequence[Mapping[str, object]] = (),
    prop_line_counts: Mapping[int, int] | None = None,
) -> list[NbaSlateGameSchema]:
    markets_by_game, movement_by_game = _by_game(market_rows), _by_game(movement_rows)
    counts = prop_line_counts or {}
    return [
        slate_game(
            game, markets_by_game.get(game["game_id"], []), records_by_season.get(int(str(game["season"])), {}),
            movement_by_game.get(game["game_id"], []), counts.get(int(str(game["game_id"])), 0),
        )
        for game in games
    ]


async def build_slate(db: AsyncSession, requested: dt.date | None, today: dt.date) -> NbaSlateResponse:
    game_dates = await nba_repo.get_game_dates(db)
    date = slate_date(requested, today, game_dates)
    previous_date, next_date = adjacent_dates(date, game_dates)
    games = await assemble_games(db, await nba_repo.get_games_on(db, date), date)
    return NbaSlateResponse(date=date, previous_date=previous_date, next_date=next_date, games=games)


async def assemble_games(db: AsyncSession, games: Sequence[Mapping[str, object]], date: dt.date) -> list[NbaSlateGameSchema]:
    """Games on one date with records, market, movement and prop counts; shared by the slate and game page."""
    if not games:
        return []
    seasons = sorted({int(str(game["season"])) for game in games})
    results = await nba_repo.get_completed_results(db, seasons)
    records_by_season = {season: team_records(results, season, date) for season in seasons}
    game_ids = [int(str(game["game_id"])) for game in games]
    return slate_games(
        games, await nba_repo.get_latest_market_rows(db, game_ids), records_by_season,
        await nba_repo.get_line_movement(db, game_ids), await nba_repo.get_prop_line_counts(db, game_ids),
    )
