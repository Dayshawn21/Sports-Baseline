"""Why a tennis prop line could go over or under, from numbers already on hand.

Recent values come from the player's completed matches, read the way the prop
check settles a line (`prop_settlement`), so a chart bar and a graded line can
never disagree about what happened.

Pure: no database, no clock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, median
from typing import Callable, Literal, Sequence

from app.core.box_score_join import BoxScoreCandidate
from app.core.prop_projection import normalize_stat_type
from app.core.prop_settlement import BOX_SCORE_STATS, SETTLEABLE_STATS, actual_value, box_score_value, parse_sets
from app.core.rolling_stats import SMALL_SAMPLE_MATCHES
from app.core.tennis_grading import is_completed_score

REASONS_VERSION = "reasons-v1"
WINDOW = 10
SPLIT_WINDOW = 20
MIN_VALUES = 3
LEAN_SHARE = 0.6
MIN_SURFACE_VALUES = 3
MIN_TREND_VALUES = 8
SMALL_RECENT_VALUES = 5
MAX_REASONS = 3
MAX_CAVEATS = 2
# Best of five only adds volume to counts that grow with match length; a set
# count or a first-set figure is priced for the format already.
VOLUME_STATS = frozenset({"total_games", "total_games_won", "aces", "double_faults", "break_points_won"})
# Comparisons at a threshold should not flip on float noise (8.0 - 7.5 vs 0.5).
_EPS = 1e-9

Side = Literal["over", "under"]
ReasonKey = Literal["projection", "hit_rate", "center", "trend", "surface", "format", "opponent"]
CaveatKey = Literal["no_player", "no_history", "small_sample", "stale_stats", "thin_margin", "thin_projection_gap"]


@dataclass(frozen=True)
class LogMatch:
    """One completed match from the player's log, its score oriented to the player."""

    match_id: int
    match_date: date
    opponent_name: str
    surface: str | None
    best_of: int
    score: str | None
    box: BoxScoreCandidate | None


@dataclass(frozen=True)
class RecentValue:
    match_date: date
    opponent_name: str
    surface: str | None
    best_of: int
    value: int


def _value(stat: str, match: LogMatch) -> int | None:
    if stat in SETTLEABLE_STATS:
        return actual_value(stat, parse_sets(match.score), player_is_p1=True)
    return box_score_value(stat, match.box) if match.box else None


def recent_values(
    stat_type: str, log: Sequence[LogMatch], exclude_match_id: int | None, before: date | None = None,
) -> list[RecentValue]:
    """The stat's value in each recent completed match, newest first, at most `SPLIT_WINDOW`.

    A retirement or walkover would understate a volume stat, so it is skipped,
    and so is the prop's own match, which must never explain its own line.
    `before` drops matches dated on or after it, so an old line is explained
    only by what was known when it was posted.
    """
    stat = normalize_stat_type(stat_type)
    values: list[RecentValue] = []
    for match in sorted(log, key=lambda m: m.match_date, reverse=True):
        if match.match_id == exclude_match_id or not is_completed_score(match.score, match.best_of):
            continue
        if before is not None and match.match_date >= before:
            continue
        value = _value(stat, match)
        if value is None:
            continue
        values.append(RecentValue(match.match_date, match.opponent_name, match.surface, match.best_of, value))
        if len(values) == SPLIT_WINDOW:
            break
    return values


@dataclass(frozen=True)
class ReasonInput:
    stat_type: str
    line: float
    recent: Sequence[RecentValue]
    """Newest first, as `recent_values` returns them."""
    player_linked: bool
    projection: float | None
    """The board's projection, only when its status is ok."""
    rolling_matches: int | None
    opponent_figure: float | None
    opponent_matches: int | None
    surface: str | None
    best_of: int | None
    stats_stale: bool


@dataclass(frozen=True)
class Reason:
    key: ReasonKey | CaveatKey
    text: str


@dataclass(frozen=True)
class RecentSummary:
    matches: int
    over: int
    under: int
    push: int
    average: float
    median: float


@dataclass(frozen=True)
class PropReasons:
    over: tuple[Reason, ...]
    under: tuple[Reason, ...]
    caveats: tuple[Reason, ...]
    summary: RecentSummary | None


Found = tuple[Side, Reason] | None


def thin_margin(line: float) -> float:
    return max(0.5, 0.05 * line)


def _num(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _day(value: date) -> str:
    return f"{value:%b} {value.day}"


def _within(gap: float, line: float) -> bool:
    return abs(gap) < thin_margin(line) - _EPS


def _counts(values: Sequence[int], line: float) -> tuple[int, int, int]:
    over = sum(1 for v in values if v > line)
    under = sum(1 for v in values if v < line)
    return over, under, len(values) - over - under


def summarize(recent: Sequence[RecentValue], line: float) -> RecentSummary | None:
    values = [v.value for v in recent[:WINDOW]]
    if len(values) < MIN_VALUES:
        return None
    over, under, push = _counts(values, line)
    return RecentSummary(len(values), over, under, push, mean(values), median(values))


def _lean(over: int, under: int) -> Side | None:
    decided = over + under
    if decided == 0:
        return None
    if over / decided >= LEAN_SHARE - _EPS:
        return "over"
    if over / decided <= 1 - LEAN_SHARE + _EPS:
        return "under"
    return None


def _projection(data: ReasonInput, summary: RecentSummary | None) -> Found:
    if data.projection is None:
        return None
    gap = data.projection - data.line
    if _within(gap, data.line):
        return None
    side: Side = "over" if gap > 0 else "under"
    word = "above" if side == "over" else "below"
    return side, Reason("projection", f"Model projects {_num(data.projection)}, {_num(abs(gap))} {word} the line")


def _hit_rate(data: ReasonInput, summary: RecentSummary | None) -> Found:
    if summary is None:
        return None
    side = _lean(summary.over, summary.under)
    decided = summary.over + summary.under
    if side == "over":
        return side, Reason("hit_rate", f"Cleared the line in {summary.over} of {decided} recent matches")
    if side == "under":
        return side, Reason("hit_rate", f"Stayed under the line in {summary.under} of {decided} recent matches")
    return None


def _center(data: ReasonInput, summary: RecentSummary | None) -> Found:
    if summary is None:
        return None
    avg, mid, line = _num(summary.average), _num(summary.median), _num(data.line)
    avg_over, mid_over = summary.average > data.line, summary.median > data.line
    if avg_over and mid_over:
        return "over", Reason("center", f"Average {avg} and median {mid}, both above the {line} line")
    if not avg_over and not mid_over:
        return "under", Reason("center", f"Average {avg} and median {mid}, both below the {line} line")
    if mid_over:
        return "over", Reason("center", f"Median {mid} is above the line; its lowest values pull the average down to {avg}")
    return "under", Reason("center", f"Median {mid} is below the line; its highest values lift the average to {avg}")


def _trend(data: ReasonInput, summary: RecentSummary | None) -> Found:
    window = [v.value for v in data.recent[:WINDOW]]
    if len(window) < MIN_TREND_VALUES:
        return None
    last5, longer = mean(window[:5]), mean(window)
    change = last5 - longer
    if _within(change, data.line):
        return None
    side: Side = "over" if change > 0 else "under"
    word = "up" if side == "over" else "down"
    return side, Reason("trend", f"Last 5 average {_num(last5)}, {word} from {_num(longer)} over {len(window)}")


def _surface(data: ReasonInput, summary: RecentSummary | None) -> Found:
    if not data.surface:
        return None
    today = data.surface.lower()
    games = [v for v in data.recent[:SPLIT_WINDOW] if (v.surface or "").lower() == today]
    if len(games) < MIN_SURFACE_VALUES:
        return None
    over, under, _ = _counts([v.value for v in games], data.line)
    side = _lean(over, under)
    if side is None:
        return None
    count = over if side == "over" else under
    since = _day(min(v.match_date for v in games))
    return side, Reason("surface", f"On {today}: {side} in {count} of {over + under} since {since}")


def _format(data: ReasonInput, summary: RecentSummary | None) -> Found:
    window = data.recent[:WINDOW]
    if normalize_stat_type(data.stat_type) not in VOLUME_STATS or data.best_of is None or len(window) < MIN_VALUES:
        return None
    five_set_share = sum(1 for v in window if v.best_of == 5) / len(window)
    if data.best_of == 5 and five_set_share < 0.5:
        return "over", Reason("format", "Best of five today; most recent matches were best of three")
    if data.best_of == 3 and five_set_share >= 0.5:
        return "under", Reason("format", "Best of three today; most recent matches were best of five")
    return None


def _opponent(data: ReasonInput, summary: RecentSummary | None) -> Found:
    figure, matches = data.opponent_figure, data.opponent_matches
    if figure is None or matches is None or matches < SMALL_SAMPLE_MATCHES:
        return None
    gap = figure - data.line
    if _within(gap, data.line):
        return None
    side: Side = "over" if gap > 0 else "under"
    return side, Reason("opponent", f"Opponent typically gives up {_num(figure)} per match")


_RULES: tuple[Callable[[ReasonInput, RecentSummary | None], Found], ...] = (
    _projection, _hit_rate, _center, _trend, _surface, _format, _opponent,
)


def _sample_caveat(data: ReasonInput) -> Reason | None:
    if 0 < len(data.recent) < SMALL_RECENT_VALUES:
        return Reason("small_sample", f"Only {len(data.recent)} completed matches in the sample")
    if data.rolling_matches is not None and data.rolling_matches < SMALL_SAMPLE_MATCHES:
        return Reason("small_sample", f"The model's rolling stats rest on {data.rolling_matches} matches")
    return None


def readable(stat_type: str) -> bool:
    """Whether a match's score or box score can say what this stat was."""
    stat = normalize_stat_type(stat_type)
    return stat in SETTLEABLE_STATS or stat in BOX_SCORE_STATS


def _history_caveat(data: ReasonInput) -> Reason | None:
    if not data.player_linked:
        return Reason("no_player", "Player not linked, so recent matches are unavailable")
    if not readable(data.stat_type):
        return Reason("no_history", "Scores and box scores do not record this market, so there is no recent history")
    if not data.recent:
        return Reason("no_history", "No recent completed matches for this market")
    return None


def _caveats(data: ReasonInput, summary: RecentSummary | None) -> list[Reason]:
    margin = _num(thin_margin(data.line))
    found: list[Reason | None] = [
        _history_caveat(data),
        _sample_caveat(data),
        Reason("stale_stats", "Rolling stats are out of date") if data.stats_stale else None,
    ]
    if summary is not None and _within(summary.average - data.line, data.line):
        found.append(Reason("thin_margin", f"Average {_num(summary.average)} sits within {margin} of the line"))
    if data.projection is not None and _within(data.projection - data.line, data.line):
        found.append(Reason("thin_projection_gap", f"Model projection {_num(data.projection)} is within {margin} of the line"))
    return [reason for reason in found if reason is not None]


def build_reasons(data: ReasonInput) -> PropReasons:
    """Up to three reasons per side, in rule order, and up to two caveats.

    Every rule speaks for at most one side, so the two lists never repeat a key.
    """
    summary = summarize(data.recent, data.line)
    sides: dict[Side, list[Reason]] = {"over": [], "under": []}
    for rule in _RULES:
        found = rule(data, summary)
        if found is not None and len(sides[found[0]]) < MAX_REASONS:
            sides[found[0]].append(found[1])
    return PropReasons(
        over=tuple(sides["over"]),
        under=tuple(sides["under"]),
        caveats=tuple(_caveats(data, summary)[:MAX_CAVEATS]),
        summary=summary,
    )
