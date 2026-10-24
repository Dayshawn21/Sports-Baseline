"""One stored NHL date, assembled identically for the slate and game detail."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.slate_dates import adjacent_dates, slate_date
from app.repositories import nhl
from app.schemas.nhl import NhlSlateGameSchema, NhlSlateResponse
from app.services.nhl.context import load_contexts, unavailable_context


def _oriented(row: Mapping[str, object], first: str) -> tuple[int, int, float]:
    first_odds, second_odds = int(str(row["first_odds"])), int(str(row["second_odds"]))
    probability = float(str(row["first_market_prob"]))
    return (first_odds, second_odds, probability) if row["first_side"] == first else (
        second_odds, first_odds, 1.0 - probability,
    )


def _markets(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    markets: dict[str, object] = {"moneyline": None, "spread": None, "total": None}
    for row in rows:
        market = str(row["market"])
        common = {"book": row["book"], "fetched_at": row["fetched_at"]}
        if market == "moneyline":
            home, away, probability = _oriented(row, "home")
            markets[market] = {**common, "home_odds": home, "away_odds": away, "home_win_probability": probability}
        elif market == "spread" and row["line"] is not None:
            home, away, _ = _oriented(row, "home")
            home_line = float(str(row["line"])) * (1 if row["first_side"] == "home" else -1)
            markets[market] = {**common, "home_line": home_line, "home_odds": home, "away_odds": away}
        elif market == "total" and row["line"] is not None:
            over, under, _ = _oriented(row, "over")
            markets[market] = {**common, "line": row["line"], "over_odds": over, "under_odds": under}
    return markets


def _by_game(rows: Sequence[Mapping[str, object]]) -> dict[int, list[Mapping[str, object]]]:
    grouped: dict[int, list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(int(str(row["game_id"])), []).append(row)
    return grouped


def slate_games(
    games: Sequence[Mapping[str, object]], markets: Sequence[Mapping[str, object]],
    movements: Sequence[Mapping[str, object]], counts: Mapping[int, int],
) -> list[NhlSlateGameSchema]:
    markets_by_game, movements_by_game = _by_game(markets), _by_game(movements)
    return [
        NhlSlateGameSchema.model_validate({
            **game, **_markets(markets_by_game.get(int(str(game["game_id"])), [])),
            "prop_line_count": counts.get(int(str(game["game_id"])), 0),
            "line_movement": movements_by_game.get(int(str(game["game_id"])), []),
            "context": unavailable_context(str(game["away_team"]), str(game["home_team"])),
        })
        for game in games
    ]


async def assemble_games(
    db: AsyncSession, games: Sequence[Mapping[str, object]], *, as_of: dt.datetime | None = None,
) -> list[NhlSlateGameSchema]:
    clock = as_of if as_of is not None else dt.datetime.now(dt.timezone.utc)
    if not games:
        return []
    game_ids = [int(str(game["game_id"])) for game in games]
    assembled = slate_games(
        games, await nhl.get_latest_market_rows(db, game_ids),
        await nhl.get_line_movement(db, game_ids), await nhl.get_prop_line_counts(db, game_ids),
    )
    contexts = await load_contexts(db, assembled, clock)
    return [game.model_copy(update={"context": contexts[game.game_id]}) for game in assembled]


async def build_slate(
    db: AsyncSession, requested: dt.date | None, today: dt.date, *, as_of: dt.datetime | None = None,
) -> NhlSlateResponse:
    clock = as_of if as_of is not None else dt.datetime.now(dt.timezone.utc)
    dates = await nhl.get_game_dates(db)
    selected = slate_date(requested, today, dates)
    previous_date, next_date = adjacent_dates(selected, dates)
    return NhlSlateResponse(
        date=selected, previous_date=previous_date, next_date=next_date,
        games=await assemble_games(db, await nhl.get_games_on(db, selected), as_of=clock),
    )
