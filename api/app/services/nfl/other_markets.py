"""One player's line-only markets for a week (item 52a): stored lines with longer history.

Display only. Values come from the same rule as the game page's line-only props, so
a kicker, a punter and a quarterback share one derivation and a missing stat stays
null rather than zero.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_line_only import line_only_value
from app.nfl.markets import NflLineOnlyMarket
from app.repositories import nfl as nfl_repo
from app.schemas.nfl import (
    NflOtherMarketGameSchema, NflOtherMarketLineSchema, NflOtherMarketSchema, NflOtherMarketsResponse,
)

RECENT_GAMES = 10

_MARKET_ORDER = {market.value: index for index, market in enumerate(NflLineOnlyMarket)}


def opponent_code(team: str | None, home_team: str, away_team: str) -> str | None:
    """The other side of the game; null when the player's team is neither side, never a guess."""
    if team == home_team:
        return away_team
    if team == away_team:
        return home_team
    return None


def _games(market: NflLineOnlyMarket, rows: Sequence[dict]) -> list[NflOtherMarketGameSchema]:
    ordered = sorted(rows, key=lambda row: (row["season"], row["week"]), reverse=True)
    return [
        NflOtherMarketGameSchema(
            season=row["season"], week=row["week"], game_date=row.get("game_date"),
            opponent=row["opponent"], value=line_only_value(market, row),
        )
        for row in ordered
    ]


def build_other_markets(
    player_id: int, season: int, week: int, opponent: str | None,
    lines: Sequence[dict], recent_rows: Sequence[dict], opponent_rows: Sequence[dict],
) -> NflOtherMarketsResponse:
    by_market: dict[str, list[dict]] = defaultdict(list)
    for line in lines:
        by_market[line["market"]].append(line)
    markets = []
    for name in sorted(by_market, key=lambda market: _MARKET_ORDER[market]):
        market = NflLineOnlyMarket(name)
        rungs = sorted(by_market[name], key=lambda line: (line["line"], line["odds_type"] or ""))
        markets.append(NflOtherMarketSchema(
            market=name, game_id=rungs[0]["game_id"],
            lines=[NflOtherMarketLineSchema(line=rung["line"], odds_type=rung["odds_type"], fetched_at=rung["fetched_at"]) for rung in rungs],
            recent=_games(market, recent_rows)[:RECENT_GAMES],
            opponent_games=_games(market, opponent_rows) if opponent is not None else [],
        ))
    return NflOtherMarketsResponse(player_id=player_id, season=season, week=week, opponent=opponent, markets=markets)


async def build_player_other_markets(db: AsyncSession, player_id: int, season: int, week: int) -> NflOtherMarketsResponse | None:
    """None for an unknown player; an empty market list when the player has no line-only line that week."""
    if not await nfl_repo.player_exists(db, player_id):
        return None
    lines = await nfl_repo.get_player_week_line_only_lines(db, player_id, season, week)
    if not lines:
        return build_other_markets(player_id, season, week, None, [], [], [])
    opponent = opponent_code(lines[0]["team"], lines[0]["home_team"], lines[0]["away_team"])
    recent = await nfl_repo.get_player_line_only_history(db, player_id, season, week, limit=RECENT_GAMES)
    meetings = await nfl_repo.get_player_line_only_history(db, player_id, season, week, opponent=opponent) if opponent else []
    return build_other_markets(player_id, season, week, opponent, lines, recent, meetings)
