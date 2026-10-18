"""Settle stored NFL PrizePicks lines against results and grade the model's calls.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from statistics import median
from typing import Literal

from app.core.nfl_over_probability_calibration import CalibrationPair, CalibrationReport, calibrate
from app.core.prop_settlement import settle
from app.nfl.markets import STANDARD_ODDS_TYPE, NflPropMarket

LineOutcome = Literal["over", "under", "push", "void_dnp", "week_not_loaded", "unsettleable_segment"]
EdgeBucket = Literal["small", "medium", "large"]

# The weekly-stats column each market settles on. Anytime TD settles on scoring
# touchdowns (rushing plus receiving) against its 0.5 line, and fantasy on
# PrizePicks' own formula, not NFLverse PPR (27f).
STAT_COLUMN_BY_MARKET: dict[NflPropMarket, str] = {
    NflPropMarket.PASSING_YARDS: "passing_yards",
    NflPropMarket.PASSING_ATTEMPTS: "passing_attempts",
    NflPropMarket.PASSING_COMPLETIONS: "passing_completions",
    NflPropMarket.RUSHING_YARDS: "rushing_yards",
    NflPropMarket.RUSHING_ATTEMPTS: "rushing_attempts",
    NflPropMarket.RECEIVING_YARDS: "receiving_yards",
    NflPropMarket.RECEPTIONS: "receptions",
    NflPropMarket.ANYTIME_TOUCHDOWN: "touchdowns",
    NflPropMarket.FANTASY_POINTS: "prizepicks_fantasy_points",
}


@dataclass(frozen=True)
class GradeableLine:
    line_id: int
    season: int
    week: int
    game_id: int
    player_id: int
    market: str
    segment: str
    odds_type: str | None
    line: float
    fetched_at: datetime
    # The market's stat from nfl_player_weekly_stats; None means the player has no row.
    stat_value: float | None
    offense_snaps: int | None
    game_has_stats: bool


@dataclass(frozen=True)
class LineResult:
    line: GradeableLine
    outcome: LineOutcome
    actual: float | None


@dataclass(frozen=True)
class RateSummary:
    """Over/under/push counts across settled lines; rates are over decided lines only."""

    over: int
    under: int
    push: int

    @property
    def decided(self) -> int:
        return self.over + self.under

    @property
    def over_rate(self) -> float | None:
        return self.over / self.decided if self.decided else None

    @property
    def standard_error(self) -> float | None:
        return _standard_error(self.over_rate, self.decided)


@dataclass(frozen=True)
class HitSummary:
    """How often the model's OVER/UNDER call was right; a push is neither."""

    hits: int
    misses: int
    pushes: int

    @property
    def calls(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.calls if self.calls else None

    @property
    def standard_error(self) -> float | None:
        return _standard_error(self.hit_rate, self.calls)


SETTLED_OUTCOMES = frozenset({"over", "under", "push"})


def _standard_error(rate: float | None, n: int) -> float | None:
    return sqrt(rate * (1 - rate) / n) if rate is not None and n else None


def settle_line(line: GradeableLine) -> LineResult:
    """Settle one line, or say why it cannot be.

    NFLverse weekly stats hold only players who recorded something, so a player
    with snaps and no stat row recorded zero. With neither, the player sat, and
    PrizePicks voids the line rather than grading it as an under. Both readings
    hold only once the game's stats file is loaded, so a game without any stat
    row settles nothing yet (its outcome keeps the API's `week_not_loaded` name).
    """
    if line.segment != "full_game":
        return LineResult(line, "unsettleable_segment", None)
    if not line.game_has_stats:
        return LineResult(line, "week_not_loaded", None)
    actual = line.stat_value
    if actual is None and line.offense_snaps:
        actual = 0.0
    if actual is None:
        return LineResult(line, "void_dnp", None)
    return LineResult(line, settle(actual, line.line), actual)


def rate(results: Iterable[LineResult]) -> RateSummary:
    outcomes = [result.outcome for result in results]
    return RateSummary(outcomes.count("over"), outcomes.count("under"), outcomes.count("push"))


def reference_lines(lines: Iterable[GradeableLine]) -> dict[str, float]:
    """Median standard full-game line per market, the denominator the prop board ranks by."""
    by_market: dict[str, list[float]] = {}
    for line in lines:
        if line.segment == "full_game" and line.odds_type == STANDARD_ODDS_TYPE and line.line > 0:
            by_market.setdefault(line.market, []).append(line.line)
    return {market: median(values) for market, values in by_market.items()}


def edge_bucket(edge: float, reference_line: float) -> EdgeBucket:
    share = abs(edge) / reference_line
    if share < 0.05:
        return "small"
    if share < 0.15:
        return "medium"
    return "large"


def model_hits(
    results: Iterable[LineResult], edges: Mapping[int, float], references: Mapping[str, float],
) -> dict[EdgeBucket | Literal["all"], HitSummary]:
    """Hit rate of the model's calls overall and by edge size.

    A line counts only when it settled and the model made a call on it: an edge
    exists and is not zero. A line in a market with no reference counts toward
    "all" only.
    """
    tallies: dict[EdgeBucket | Literal["all"], list[int]] = {}
    for result in results:
        edge = edges.get(result.line.line_id)
        if edge is None or edge == 0 or result.outcome not in SETTLED_OUTCOMES:
            continue
        called_over = edge > 0
        if result.outcome == "push":
            slot = 2
        elif called_over == (result.outcome == "over"):
            slot = 0
        else:
            slot = 1
        keys: list[EdgeBucket | Literal["all"]] = ["all"]
        reference = references.get(result.line.market)
        if reference:
            keys.append(edge_bucket(edge, reference))
        for key in keys:
            tallies.setdefault(key, [0, 0, 0])[slot] += 1
    return {key: HitSummary(*counts) for key, counts in tallies.items()}


FORWARD_RELIABILITY_BINS = 5


@dataclass(frozen=True)
class OverProbabilityRead:
    """How P(over) held up on settled lines; `report` is None when nothing was scored."""

    scored: int
    # Settled over or under, but the slate served no P(over) for the line.
    unscored: int
    report: CalibrationReport | None

    @property
    def mean_predicted(self) -> float | None:
        return sum(b.n * b.mean_predicted for b in self.report.bins) / self.scored if self.report else None

    @property
    def over_rate(self) -> float | None:
        return sum(b.n * b.observed for b in self.report.bins) / self.scored if self.report else None

    @property
    def standard_error(self) -> float | None:
        return _standard_error(self.over_rate, self.scored)


def over_probability_reads(
    results: Iterable[LineResult], p_overs: Mapping[int, float],
) -> dict[str, OverProbabilityRead]:
    """P(over) against outcomes, by odds type and overall.

    Only lines that settled over or under count: a push has no over to score,
    and v1 serves no P(over) on the integer lines that can push.
    """
    pairs: dict[str, list[CalibrationPair]] = {}
    unscored: dict[str, int] = {}
    for result in results:
        if result.outcome not in ("over", "under"):
            continue
        keys = ("all", result.line.odds_type or "unknown")
        predicted = p_overs.get(result.line.line_id)
        for key in keys:
            if predicted is None:
                unscored[key] = unscored.get(key, 0) + 1
            else:
                pairs.setdefault(key, []).append(CalibrationPair(predicted, result.outcome == "over"))
    return {
        key: OverProbabilityRead(
            scored=len(pairs.get(key, [])), unscored=unscored.get(key, 0),
            report=calibrate(pairs[key], FORWARD_RELIABILITY_BINS) if key in pairs else None,
        )
        for key in sorted(set(pairs) | set(unscored))
    }
