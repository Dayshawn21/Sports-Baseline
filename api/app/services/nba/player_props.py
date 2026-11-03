"""One player's NBA props on a slate date: the board's lines regrouped by market (item 53a).

Display only. Every model field comes from `props_response`, so this view cannot
disagree with the board or the game page.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import cast

from app.core.nba_line_only import line_only_value
from app.core.nba_names import espn_team_code
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaHistoryRow
from app.nba.markets import NBA_MARKETS, nba_market
from app.schemas.nba import (
    NbaInjuryReportSchema, NbaLineOnlyLineSchema, NbaPlayerGameRefSchema, NbaPlayerGameSchema, NbaPlayerMarketSchema,
    NbaPlayerPropsResponse, NbaPlayerRungSchema, NbaPropLineSchema, NbaTeamStatsContextSchema,
)
from app.services.nba.injuries import injury_index
from app.services.nba.line_only_props import line_only_props
from app.services.nba.props import props_response

OPPONENT_GAMES_LIMIT = 20
RECENT_GAMES_LIMIT = 10

_MARKET_ORDER = {market.value: index for index, market in enumerate(NBA_MARKETS)}


def player_props_response(
    player: Mapping[str, object],
    date: dt.date,
    game: Mapping[str, object] | None,
    modelled_lines: Sequence[Mapping[str, object]],
    line_only_lines: Sequence[Mapping[str, object]],
    prior: Mapping[int, Sequence[NbaHistoryRow]],
    recent_rows: Sequence[Mapping[str, object]],
    opponent_rows: Sequence[Mapping[str, object]],
    report: NbaInjuryReportSchema | None = None,
    team_stats: NbaTeamStatsContextSchema | None = None,
) -> NbaPlayerPropsResponse:
    report = report if report is not None else NbaInjuryReportSchema()
    player_id = int(str(player["player_id"]))
    if game is None:
        return NbaPlayerPropsResponse(
            player_id=player_id, name=str(player["name"]), position=cast(str | None, player["position"]),
            team=cast(str | None, player["team"]), date=date, game=None, opponent=None,
            model_version=NBA_PROJECTION_MODEL_VERSION, injury_report=report, markets=[],
        )
    game_id = int(str(game["game_id"]))
    modelled = props_response(game_id, modelled_lines, prior, recent_rows, report, team_stats).lines
    line_only = line_only_props(game_id, line_only_lines, recent_rows, report, team_stats).lines
    team = resolve_team(player, [*modelled_lines, *line_only_lines])
    opponent = opponent_code(team, game)
    return NbaPlayerPropsResponse(
        player_id=player_id, name=str(player["name"]), position=cast(str | None, player["position"]),
        team=team, date=date, game=_game_ref(game), opponent=opponent,
        model_version=NBA_PROJECTION_MODEL_VERSION,
        injury=injury_index(report).get((player_id, team)) if team is not None else None,
        injury_report=report, team_stats=team_stats,
        markets=_markets([*modelled, *line_only], opponent_rows if opponent is not None else []),
    )


def resolve_team(player: Mapping[str, object], lines: Sequence[Mapping[str, object]]) -> str | None:
    """The ESPN team on the player's lines, else the team of their latest loaded game."""
    codes = (espn_team_code(cast(str | None, line["team"])) for line in lines)
    return next((code for code in codes if code is not None), cast(str | None, player["team"]))


def _game_ref(game: Mapping[str, object]) -> NbaPlayerGameRefSchema:
    return NbaPlayerGameRefSchema(
        game_id=int(str(game["game_id"])), away_team=str(game["away_team"]), home_team=str(game["home_team"]),
        start_utc=cast(dt.datetime | None, game["start_utc"]), status=str(game["status"]),
    )


def opponent_code(team: str | None, game: Mapping[str, object]) -> str | None:
    """The other side of the game; null when the player's team is neither, never a guess."""
    away, home = str(game["away_team"]), str(game["home_team"])
    if team == home:
        return away
    return home if team == away else None


def _markets(
    lines: Sequence[NbaLineOnlyLineSchema], opponent_rows: Sequence[Mapping[str, object]],
) -> list[NbaPlayerMarketSchema]:
    by_market: dict[str, list[NbaLineOnlyLineSchema]] = {}
    for line in lines:
        by_market.setdefault(line.market, []).append(line)
    markets = []
    for name in sorted(by_market, key=_MARKET_ORDER.__getitem__):
        rungs = sorted(by_market[name], key=lambda line: (line.line, line.odds_type or ""))
        first = rungs[0]
        projected = first if isinstance(first, NbaPropLineSchema) else None
        markets.append(NbaPlayerMarketSchema(
            market=name, kind="modelled" if projected else "line-only",
            projection=projected.projection if projected else None,
            games_in_sample=projected.games_in_sample if projected else None,
            prior_minutes=projected.prior_minutes if projected else None,
            lines=[_rung(line) for line in rungs],
            recent=[
                NbaPlayerGameSchema(game_date=row.game_date, opponent=row.opponent, value=row.value)
                for row in first.recent[:RECENT_GAMES_LIMIT]
            ],
            opponent_games=_opponent_games(name, opponent_rows),
        ))
    return markets


def _rung(line: NbaLineOnlyLineSchema) -> NbaPlayerRungSchema:
    if not isinstance(line, NbaPropLineSchema):
        return NbaPlayerRungSchema(line=line.line, odds_type=line.odds_type, fetched_at=line.fetched_at)
    return NbaPlayerRungSchema(
        line=line.line, odds_type=line.odds_type, fetched_at=line.fetched_at, gap=line.gap, p_over=line.p_over,
        p_under=line.p_under, over_probability_version=line.over_probability_version, flags=line.flags,
    )


def _opponent_games(market: str, rows: Sequence[Mapping[str, object]]) -> list[NbaPlayerGameSchema]:
    kind = nba_market(market)
    return [
        NbaPlayerGameSchema(
            game_date=cast(dt.date, row["game_date"]), opponent=cast(str | None, row["opponent"]),
            value=line_only_value(kind, cast(Mapping[str, int | bool | None], row)),
        )
        for row in rows[:OPPONENT_GAMES_LIMIT]
    ]
