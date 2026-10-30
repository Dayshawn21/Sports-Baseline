"""Fit the 49b line anchor on 2026 weeks 1-8 standard receptions lines.

Projects each settled line's player-game with `nfl-volume-v1`, pairs the
projection's chance of going over the line with the outcome, and fits the
two-parameter blend registered in `app/core/nfl_volume_anchor.py`. The fit
window, market and minimum sample are constants there, so this takes no
options: a different run would be a different rule.

Everything printed about the fit weeks is in-sample and carries no verdict. The
adoption rule is applied to weeks 9 onward in 49d.

It reads and prints. Nothing is stored, and nothing feeds a projection.

Run from api/: python -m app.backtest.nfl_volume_anchor
"""
from __future__ import annotations

import argparse
import asyncio
import math
import sys
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.nfl_volume_anchor import (
    ANCHOR_FIT_FIRST_WEEK,
    ANCHOR_FIT_LAST_WEEK,
    ANCHOR_FIT_SEASON,
    ANCHOR_MARKET,
    ANCHOR_MIN_FIT_PAIRS,
    AnchorFit,
    anchored_probability,
    clamp_q,
    conditional_over,
    fit_anchor,
    require_anchorable,
)
from app.core.nfl_volume_backtest import VolumeCase, VolumeHistory, build_cases
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION, NFL_VOLUME_V1_PARAMETERS, project_player
from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE, MIN_PICK_MARGIN, pick_side

if TYPE_CHECKING:
    from app.repositories.nfl_volume_anchor import AnchorLine

UNSETTLED = "unsettled (no result yet, or did not play)"
NO_CASE = "no player-game with closing lines"
NO_PROJECTION = "no volume forecast"
PUSH = "push (receptions equal the line)"
IN_SAMPLE = "IN-SAMPLE: fitted on these lines, so no verdict is read from them"
CALIBRATION_BINS = 5


@dataclass(frozen=True)
class AnchorPair:
    line_id: int
    week: int
    game_id: int
    q_vol: float
    p_push: float
    went_over: bool


def build_pairs(lines: Sequence[AnchorLine], cases: Sequence[VolumeCase]) -> tuple[list[AnchorPair], Counter[str]]:
    """One pair per settled, projectable, non-push line; every other line is counted by reason."""
    require_anchorable(ANCHOR_MARKET, NFL_VOLUME_MODEL_VERSION)
    by_player_game = {(case.player_id, case.game_id): case for case in cases}
    pairs: list[AnchorPair] = []
    excluded: Counter[str] = Counter()
    for line in lines:
        if line.receptions is None:
            excluded[UNSETTLED] += 1
            continue
        case = by_player_game.get((line.player_id, line.game_id))
        if case is None:
            excluded[NO_CASE] += 1
            continue
        distribution = project_player(case.position, case.history, case.game, NFL_VOLUME_V1_PARAMETERS).distributions.get(ANCHOR_MARKET)
        if distribution is None:
            excluded[NO_PROJECTION] += 1
            continue
        if line.receptions == line.line:
            excluded[PUSH] += 1
            continue
        probability = distribution.p_over(line.line)
        pairs.append(AnchorPair(
            line.line_id, line.week, line.game_id, conditional_over(probability.over, probability.under),
            probability.push, line.receptions > line.line,
        ))
    return pairs, excluded


def _log_loss(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    return -sum(math.log(p if won else 1.0 - p) for p, won in zip(probabilities, outcomes)) / len(outcomes)


@dataclass(frozen=True)
class Diagnostics:
    pairs: int
    blend_log_loss: float
    raw_log_loss: float
    half_log_loss: float
    over_rate: float
    picks: int
    pick_hits: int


def diagnostics(pairs: Sequence[AnchorPair], fit: AnchorFit) -> Diagnostics:
    outcomes = [pair.went_over for pair in pairs]
    blended = [anchored_probability(pair.q_vol, pair.p_push, fit.a, fit.b) for pair in pairs]
    conditional = [over / (over + under) for over, under in blended]
    picks = hits = 0
    for (over, under), won_over in zip(blended, outcomes):
        chosen = pick_side("standard", over, under)
        if chosen is not None:
            picks += 1
            hits += (chosen[0] == "over") == won_over
    return Diagnostics(
        len(pairs), _log_loss(conditional, outcomes), _log_loss([clamp_q(pair.q_vol) for pair in pairs], outcomes),
        math.log(2.0), sum(outcomes) / len(outcomes), picks, hits,
    )


def calibration(pairs: Sequence[AnchorPair], fit: AnchorFit) -> list[tuple[int, float, float]]:
    """(pairs, mean blended P(over), observed over rate) in equal-count bins of the blended probability."""
    ranked = sorted(
        (anchored_probability(pair.q_vol, 0.0, fit.a, fit.b)[0], pair.went_over) for pair in pairs
    )
    rows = []
    for index in range(CALIBRATION_BINS):
        chunk = ranked[index * len(ranked) // CALIBRATION_BINS:(index + 1) * len(ranked) // CALIBRATION_BINS]
        if chunk:
            rows.append((len(chunk), sum(p for p, _ in chunk) / len(chunk), sum(won for _, won in chunk) / len(chunk)))
    return rows


def _pct(value: float) -> str:
    return f"{value * 100:5.1f}%"


def report(lines: Sequence[AnchorLine], pairs: Sequence[AnchorPair], excluded: Counter[str], fit: AnchorFit) -> str:
    unsettled_by_week: Counter[int] = Counter(line.week for line in lines if line.receptions is None)
    by_week: Counter[int] = Counter(pair.week for pair in pairs)
    stats = diagnostics(pairs, fit)
    break_even = BREAK_EVEN_BY_ODDS_TYPE["standard"]
    weeks = range(ANCHOR_FIT_FIRST_WEEK, ANCHOR_FIT_LAST_WEEK + 1)
    out = [
        f"NFL volume line anchor fit ({NFL_VOLUME_MODEL_VERSION} {ANCHOR_MARKET}, {ANCHOR_FIT_SEASON} weeks "
        f"{ANCHOR_FIT_FIRST_WEEK}-{ANCHOR_FIT_LAST_WEEK}, standard lines)",
        IN_SAMPLE,
        "",
        f"Lines loaded: {len(lines)}. Fit pairs: {len(pairs)} (minimum {ANCHOR_MIN_FIT_PAIRS}).",
        "Pairs by week: " + ", ".join(f"{week}={by_week.get(week, 0)}" for week in weeks),
        "Unsettled lines by week: " + ", ".join(f"{week}={unsettled_by_week.get(week, 0)}" for week in weeks),
        "",
        "Excluded lines",
        *(f"  {reason:<46}{n:>6}" for reason, n in sorted(excluded.items())),
        *([] if excluded else ["  -- none --"]),
        "",
        "Fitted: logit(q) = a + b * logit(q_vol)",
        f"  a = {fit.a:+.4f} (SE {fit.a_se:.4f})",
        f"  b = {fit.b:+.4f} (SE {fit.b_se:.4f})",
        "",
        f"Log loss, {stats.pairs} non-push pairs (lower is better; in-sample)",
        f"  blend {stats.blend_log_loss:.4f}   raw volume {stats.raw_log_loss:.4f}   constant 0.5 {stats.half_log_loss:.4f}",
        f"Observed over rate {_pct(stats.over_rate)}",
        f"Picks clearing break-even {_pct(break_even)} plus {_pct(MIN_PICK_MARGIN)}: {stats.picks}, "
        f"hits {stats.pick_hits}"
        + (f" ({_pct(stats.pick_hits / stats.picks)})" if stats.picks else ""),
        "",
        "Calibration of the blended P(over), equal-count bins",
        f"  {'pairs':>6}{'mean P':>9}{'over rate':>11}",
        *(f"  {n:>6}{_pct(mean_p):>9}{_pct(rate):>11}" for n, mean_p, rate in calibration(pairs, fit)),
    ]
    return "\n".join(out)


def load_cases(history: VolumeHistory) -> list[VolumeCase]:
    return build_cases(history)


async def run() -> str:
    from app.db.pool import SessionLocal
    from app.repositories.nfl_volume_anchor import get_anchor_history, get_anchor_lines

    started = time.monotonic()
    async with SessionLocal() as db:
        lines = await get_anchor_lines(db, ANCHOR_FIT_SEASON, ANCHOR_FIT_FIRST_WEEK, ANCHOR_FIT_LAST_WEEK)
        history = await get_anchor_history(db, ANCHOR_FIT_SEASON)
    pairs, excluded = build_pairs(lines, load_cases(history))
    print(f"Loaded {len(lines)} lines and {len(history.player_games)} player-games.", file=sys.stderr, flush=True)
    fit = fit_anchor([(pair.q_vol, pair.went_over) for pair in pairs])
    return "\n".join([f"Elapsed {time.monotonic() - started:.0f}s.", "", report(lines, pairs, excluded, fit)])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f"Fit the 49b line anchor on {ANCHOR_FIT_SEASON} weeks {ANCHOR_FIT_FIRST_WEEK}-{ANCHOR_FIT_LAST_WEEK} "
            f"standard {ANCHOR_MARKET} lines. Read-only; takes no options because the run is fixed by the "
            "pre-registered rule. Run once, after week 8 is settled and ingested."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(run()))


if __name__ == "__main__":
    main()
