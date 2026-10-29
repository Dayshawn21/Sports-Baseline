"""Which live tennis PrizePicks lines are picks under 48e's adopted slices (48g).

A live line is keyed, excluded and collapsed exactly as the 48e grader treats
a frozen one, so a line ranks only when the slice the grader adopted is the
slice the line would have been graded in.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import replace
from datetime import date, datetime

from app.core.prop_ranking_rule import FrozenCall, Pick, one_pick_per_bet, to_pick
from app.core.tennis_prop_check import (
    TENNIS_PROP_CHECK_RULE, CheckResult, TennisFrozenLine, TennisSlice, period_of, slice_key, to_frozen_call,
)
from app.core.tennis_prop_check import adopted as adopted_slices

JsonObject = dict[str, object]

# The outcome a live line carries before it settles.
UNSETTLED = "unsettled"
# report_snapshots is keyed by season, and tennis grading spans seasons.
ADOPTION_SEASON = 0
_ANCHORS = ("book", "model")
_SIDES = ("over", "under")


def _live_call(line: TennisFrozenLine) -> FrozenCall | None:
    # 48e's own exclusions and push-excluded probabilities. The placeholder
    # outcome and the line's own week as "finished" only get it past the
    # settlement checks; ranking never reads `Pick.hit`.
    call = to_frozen_call(replace(line, outcome="over"), {period_of(line.start_time)})
    return call if isinstance(call, FrozenCall) else None


def adoption_report(version: str) -> str:
    """One stored row per projection version, so a v4 grade never overwrites v3."""
    return f"tennis_prop_adoption:{version}"


def to_payload(result: CheckResult, version: str, as_of: date, computed_at: datetime) -> JsonObject:
    """Adopted slice keys and counts only: no slice's hit rate leaves the grader."""
    return {
        "rule": TENNIS_PROP_CHECK_RULE,
        "projectionVersion": version,
        "asOf": as_of.isoformat(),
        "computedAt": computed_at.isoformat(),
        "finishedWeeks": result.finished_weeks,
        "decidedSlices": sum(1 for r in result.slices.values() if r.verdict != "insufficient"),
        "adopted": [
            {"stat": key.stat, "tour": key.tour, "anchor": key.anchor, "oddsType": key.odds_type, "side": key.side}
            for key in sorted(adopted_slices(result))
        ],
    }


def _slice_from(entry: object) -> TennisSlice | None:
    if not isinstance(entry, dict):
        return None
    stat, tour, anchor, odds_type, side = (entry.get(k) for k in ("stat", "tour", "anchor", "oddsType", "side"))
    if not (isinstance(stat, str) and isinstance(tour, str) and isinstance(odds_type, str)):
        return None
    if anchor not in _ANCHORS or side not in _SIDES:
        return None
    return TennisSlice(stat, tour, "book" if anchor == "book" else "model", odds_type,
                       "over" if side == "over" else "under")


def adopted_from_payload(payload: JsonObject, version: str) -> frozenset[TennisSlice] | None:
    """The adopted slices a stored payload serves for `version`, or None when it must not be trusted."""
    if payload.get("rule") != TENNIS_PROP_CHECK_RULE or payload.get("projectionVersion") != version:
        return None
    entries = payload.get("adopted")
    if not isinstance(entries, list):
        return None
    slices = [_slice_from(entry) for entry in entries]
    if any(key is None for key in slices):
        return None
    return frozenset(key for key in slices if key is not None)


def adopted_picks(
    lines: Sequence[TennisFrozenLine], adopted: Collection[TennisSlice], now: datetime,
) -> dict[int, Pick]:
    """The pick for each line whose surviving ladder rung falls in an adopted slice, by line id.

    The rule graded pre-start snapshots only, so a started line is never a pick.
    """
    if not adopted:
        return {}
    pending = [line for line in lines if line.start_time > now]
    calls = [call for line in pending if (call := _live_call(line)) is not None]
    picks = [pick for call in calls if (pick := to_pick(call)) is not None]
    by_id = {line.line_id: line for line in pending}
    return {
        bet.call.line_id: bet for bet in one_pick_per_bet(picks)
        if slice_key(by_id[bet.call.line_id], bet.side) in adopted
    }
