"""The Real or Lucky? video's numbers as one JSON-ready dict: the RealOrLucky composition's input props."""
from __future__ import annotations

from typing import TypedDict

import pandas as pd

from lib.nfl_team_report import (ONE_SCORE_MARGIN, OpponentAdjustment, ScoringRun, SeasonSnapshot, UnbeatenHistory,
                                  nickname, played_between, points_record, real_verdict, standings, team_name)
from lib.real_or_lucky_posts import VERDICT_SENTENCES, chart_title, kicker_carries, record


class GameRow(TypedDict):
    week: int
    opponent: str
    home: bool
    scored: int
    allowed: int
    margin: int
    oneScore: bool


class LeagueDot(TypedDict):
    team: str
    nickname: str
    actualWins: float
    pythagoreanWins: float


class HistoryData(TypedDict):
    firstSeason: int
    lastSeason: int
    games: int
    starts: int
    pointsBelowPerfect: int
    morePoints: int
    restWinPct: int
    pythagoreanWins: list[float]
    fewerPoints: int
    fewerAllowed: int


class AdjustmentData(TypedDict):
    allowedBelow: float
    bestOpponent: str
    bestAllowed: int
    bestUsual: float


class KickerData(TypedDict):
    kickPoints: int
    points: int
    games: int
    allGames: bool    # the run covers the whole season, so the line says "their", not "their last"


class RealOrLuckyVideo(TypedDict):
    team: str
    nickname: str
    teamName: str
    season: int
    throughWeek: int
    record: str
    pointsRecord: str
    actualWins: float
    pythagoreanWins: float
    games: list[GameRow]
    oneScoreWins: int
    oneScoreLosses: int
    turnoverMargin: int
    turnoverMarginRank: int
    turnoverCarryover: float
    offenseEpaRank: int
    defenseEpaRank: int
    verdict: str
    verdictSentence: str
    source: str
    chartTitle: str
    league: list[LeagueDot]
    lastUnbeaten: bool
    history: HistoryData | None
    opponentAdjustment: AdjustmentData | None
    kicker: KickerData | None


def kicker_data(snapshot: SeasonSnapshot, scoring: ScoringRun | None) -> KickerData | None:
    """Only when the kicker scored at least half the run's points, the same rule as the posts."""
    if not kicker_carries(scoring):
        return None
    return KickerData(kickPoints=scoring.kick_points, points=scoring.points, games=scoring.games,
                      allGames=scoring.games == snapshot.games)


def league_dots(games: pd.DataFrame, snapshot: SeasonSnapshot) -> list[LeagueDot]:
    """Every team's dot on the record-vs-points chart, as on the feed chart."""
    table = standings(games, snapshot.season, snapshot.through_week)
    return [LeagueDot(team=str(code), nickname=nickname(str(code)), actualWins=float(row.wins + row.ties / 2),
                      pythagoreanWins=round(float(row.pythagorean_wins), 2))
            for code, row in table.sort_index().iterrows()]


def game_rows(games: pd.DataFrame, snapshot: SeasonSnapshot) -> list[GameRow]:
    played = played_between(games, snapshot.season, 1, snapshot.through_week)
    played = played[played["team"] == snapshot.team].sort_values("week")
    return [GameRow(week=int(row.week), opponent=nickname(row.opponent), home=bool(row.is_home),
                    scored=int(row.points_for), allowed=int(row.points_against), margin=int(row.margin),
                    oneScore=abs(int(row.margin)) <= ONE_SCORE_MARGIN)
            for row in played.itertuples()]


def history_data(history: UnbeatenHistory | None) -> HistoryData | None:
    if history is None or history.starts == 0:
        return None
    return HistoryData(firstSeason=history.first_season, lastSeason=history.last_season, games=history.games,
                       starts=history.starts, pointsBelowPerfect=history.points_below_perfect,
                       morePoints=history.more_points, restWinPct=round(history.rest_win_rate * 100),
                       pythagoreanWins=history.pythagorean_wins, fewerPoints=history.fewer_points,
                       fewerAllowed=history.fewer_allowed)


def video_data(snapshot: SeasonSnapshot, games: pd.DataFrame, *, turnover_carryover: float,
               history: UnbeatenHistory | None = None, last_unbeaten: bool = False,
               adjustment: OpponentAdjustment | None = None,
               scoring: ScoringRun | None = None) -> RealOrLuckyVideo:
    verdict = real_verdict(snapshot)
    return RealOrLuckyVideo(
        team=snapshot.team, nickname=nickname(snapshot.team), teamName=team_name(snapshot.team),
        season=snapshot.season, throughWeek=snapshot.through_week,
        record=record(snapshot), pointsRecord=points_record(snapshot.pythagorean_wins, snapshot.games),
        actualWins=snapshot.wins + snapshot.ties / 2, pythagoreanWins=round(snapshot.pythagorean_wins, 2),
        games=game_rows(games, snapshot),
        oneScoreWins=snapshot.one_score_wins, oneScoreLosses=snapshot.one_score_losses,
        turnoverMargin=snapshot.turnover_margin, turnoverMarginRank=snapshot.turnover_margin_rank,
        turnoverCarryover=round(turnover_carryover, 2),
        offenseEpaRank=snapshot.offense_epa_rank, defenseEpaRank=snapshot.defense_epa_rank,
        verdict=verdict, verdictSentence=VERDICT_SENTENCES[verdict],
        source=f"Source: nflverse · data through week {snapshot.through_week}, {snapshot.season}",
        chartTitle=chart_title(snapshot), league=league_dots(games, snapshot),
        lastUnbeaten=last_unbeaten, history=history_data(history),
        opponentAdjustment=None if adjustment is None else AdjustmentData(
            allowedBelow=adjustment.allowed_below, bestOpponent=nickname(adjustment.best_opponent),
            bestAllowed=adjustment.best_allowed, bestUsual=adjustment.best_usual),
        kicker=kicker_data(snapshot, scoring),
    )
