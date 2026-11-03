"""One player's stored lines for a slate date with recent and opponent results."""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_names import nhl_team_code
from app.core.nhl_player_values import GOALIE_MARKETS, NHL_FIRST_HISTORY_SEASON, nhl_stat_value, player_props_date
from app.core.slate_dates import slate_date
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl import (
    NhlPlayerGameRefSchema, NhlPlayerGameSchema, NhlPlayerInjurySchema, NhlPlayerLineSchema,
    NhlPlayerMarketSchema, NhlPlayerPropsResponse,
)
from app.schemas.nhl_context import NhlGameContextSchema, NhlGoalieContext
from app.services.nhl.slate import assemble_games

RECENT_GAMES = 10
_MARKET_ORDER = {market: index for index, market in enumerate(NhlLineOnlyMarket)}
_ODDS_ORDER = {"standard": 0, "goblin": 1, "demon": 2}


def game_sides(game: Mapping[str, object], lines: Sequence[Mapping[str, object]]) -> tuple[str | None, str | None]:
    """The player's team and opponent from the provider team; null unless it is one of the game's two."""
    sides = (str(game["home_team"]), str(game["away_team"]))
    for line in lines:
        team = nhl_team_code(cast(str | None, line["team"]))
        if team in sides:
            return team, sides[1] if team == sides[0] else sides[0]
    return None, None


def _games(market: NhlLineOnlyMarket, rows: Sequence[Mapping[str, object]], limit: int | None) -> list[NhlPlayerGameSchema]:
    ordered = sorted(rows, key=lambda row: cast(dt.date, row["game_date"]), reverse=True)
    return [
        NhlPlayerGameSchema(
            game_date=cast(dt.date, row["game_date"]), opponent=cast("str | None", row["opponent"]),
            value=nhl_stat_value(market, row),
        )
        for row in ordered[:limit]
    ]


def _markets(
    lines: Sequence[Mapping[str, object]], recent: Sequence[Mapping[str, object]],
    against: Sequence[Mapping[str, object]],
) -> list[NhlPlayerMarketSchema]:
    by_market: dict[NhlLineOnlyMarket, list[NhlPlayerLineSchema]] = {}
    for line in lines:
        by_market.setdefault(NhlLineOnlyMarket(str(line["market"])), []).append(
            NhlPlayerLineSchema.model_validate({
                "line": line["line"], "odds_type": line["odds_type"], "fetched_at": line["fetched_at"],
            }),
        )
    return [
        NhlPlayerMarketSchema(
            market=market,
            lines=sorted(rungs, key=lambda rung: (rung.line, _ODDS_ORDER[rung.odds_type])),
            recent=_games(market, recent, RECENT_GAMES), opponent_games=_games(market, against, None),
        )
        for market, rungs in sorted(by_market.items(), key=lambda item: _MARKET_ORDER[item[0]])
    ]


def _context(player_id: int, context: NhlGameContextSchema | None) -> tuple[NhlPlayerInjurySchema, NhlGoalieContext | None]:
    if context is None:
        return NhlPlayerInjurySchema(), None
    injuries = context.injuries
    entry = next((row for row in (*injuries.away, *injuries.home) if row.player_id == player_id), None)
    return NhlPlayerInjurySchema(
        fetched_at=injuries.fetched_at, source_timestamp=injuries.source_timestamp,
        freshness=injuries.freshness, entry=entry,
    ), context.goalies


def player_props_response(
    player: Mapping[str, object], date: dt.date, game: Mapping[str, object] | None,
    lines: Sequence[Mapping[str, object]], recent: Sequence[Mapping[str, object]],
    against: Sequence[Mapping[str, object]], context: NhlGameContextSchema | None,
) -> NhlPlayerPropsResponse:
    player_id = int(str(player["player_id"]))
    identity = {
        "player_id": player_id, "name": str(player["name"]),
        "position": cast("str | None", player["position"]), "date": date,
    }
    if game is None or not lines:
        return NhlPlayerPropsResponse(
            **identity, team=None, game=None, opponent=None, injury=NhlPlayerInjurySchema(), goalies=None, markets=[],
        )
    team, opponent = game_sides(game, lines)
    injury, goalies = _context(player_id, context)
    return NhlPlayerPropsResponse(
        **identity, team=team, game=NhlPlayerGameRefSchema.model_validate(game), opponent=opponent,
        injury=injury, goalies=goalies, markets=_markets(lines, recent, against if opponent is not None else []),
    )


async def build_player_props(
    db: AsyncSession, player_id: int, requested: dt.date | None, today: dt.date, *, as_of: dt.datetime | None = None,
) -> NhlPlayerPropsResponse | None:
    player = await nhl.get_player(db, player_id)
    if player is None:
        return None
    clock = as_of if as_of is not None else dt.datetime.now(dt.timezone.utc)
    default = slate_date(None, today, await nhl.get_game_dates(db))
    date = player_props_date(requested, default, await nhl.get_player_line_dates(db, player_id))
    lines = await nhl.get_player_lines(db, player_id, date)
    game = await nhl.get_game(db, int(str(lines[0]["game_id"]))) if lines else None
    if game is None:
        return player_props_response(player, date, None, [], [], [], None)
    (assembled,) = await assemble_games(db, [game], as_of=clock)
    goalie = any(NhlLineOnlyMarket(str(line["market"])) in GOALIE_MARKETS for line in lines)
    history = {"goalie": goalie, "before": date, "first_season": NHL_FIRST_HISTORY_SEASON}
    recent = await nhl.get_player_played_games(db, player_id, limit=RECENT_GAMES, **history)
    _, opponent = game_sides(game, lines)
    against = [] if opponent is None else await nhl.get_player_played_games(db, player_id, opponent=opponent, **history)
    return player_props_response(player, date, game, lines, recent, against, assembled.context)
