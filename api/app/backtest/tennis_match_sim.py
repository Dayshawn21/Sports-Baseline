"""Checks for the 48c match simulation, each run once before any v4 snapshot.

Read-only. `--sets` compares the exact match chain's deciding-set rate with the
held-out `tennis_sets` fit. A constant-hold chain treats sets as independent,
which that fit found doubled the deciding-set error. Stop rule, fixed in the
48c spec before the run: the chain is used as is only if the gap is under 0.02
at every win probability.

The rule fired (largest gap 0.107), so `--fit-set-effect` fits the sd of
the match-level hold shift in `mixed_match_distribution` to minimize the
largest gap, coarse grid then fine grid.

`--dispersion` measures how much wider per-match aces and double faults are
than a binomial on that match's serve points, from the 2026 TennisMyLife ATP
and WTA files (`player_match_stats` has no serve points). Each player's rate
is their leave-one-out rate in the file. The fitted gamma shape therefore
also covers the error in an estimated rate, which the simulation faces too.

`--level` simulates completed 2026 ATP and WTA matches from their last
pre-start moneyline and Bet365 total, through the same `build_match_sim` the
v4 rows use, and reads the mean bias by stat and tour. Stop rule, fixed in the
spec before the run: a stat and tour at or beyond its threshold is listed in
`SIM_LEVEL_UNVERIFIED`, never tuned. Rolling stats are current and include
these matches, so only the mean bias is read.

Run from api/: python -m app.backtest.tennis_match_sim --sets [--effect-sd X]
               python -m app.backtest.tennis_match_sim --fit-set-effect
               python -m app.backtest.tennis_match_sim --dispersion
               python -m app.backtest.tennis_match_sim --level
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from io import StringIO

import httpx

from app.core.box_score_join import BoxScoreCandidate
from app.core.odds import american_to_prob, devig_two_way
from app.core.prop_settlement import actual_value, box_score_value, parse_sets
from app.core.tennis_grading import is_completed_score
from app.core.tennis_match_chain import mixed_match_distribution
from app.core.tennis_sets import three_set_probability
from app.repositories.matches import PreStartMarketMatch
from app.repositories.players import PlayerRollingStats
from app.repositories.props import Prop
from app.routers.props import MarketTotal
from app.services.tennis.prop_sim import MatchSim, SimInputs, build_match_sim, stat_values

SET_GAP_STOP = 0.02
DISPERSION_FILES = (("ATP", "2026.csv"), ("WTA", "2026_wta.csv"))
MIN_OTHER_MATCHES = 5
_UNFINISHED = ("RET", "DEF", "W/O", "WO", "WALKOVER")
LEVEL_SINCE = date(2026, 1, 1)
# Stored totals were Bet365's until The Odds API took over on this date (48b).
LEVEL_UNTIL = date(2026, 10, 26)
LEVEL_TOTAL_BOOK = "bet365"
# Pre-registered in the 48c spec: an absolute mean bias at or above these is unverified.
LEVEL_THRESHOLDS = {
    "total_games": 0.25, "total_games_won": 0.25, "1st_set_total_games": 0.25, "1st_set_total_games_won": 0.25,
    "aces": 0.5, "double_faults": 0.5, "break_points_won": 0.25,
    "total_sets": 0.05, "total_tie_breaks": 0.05, "fantasy_score": 1.5,
}
_MATCH_STATS = ("total_games", "total_sets", "total_tie_breaks", "1st_set_total_games")
_SCORE_PLAYER_STATS = ("total_games_won", "1st_set_total_games_won")
_BOX_STATS = ("aces", "double_faults", "break_points_won")
WIN_PROBS = tuple(round(0.50 + 0.05 * i, 2) for i in range(10))
HOLD_LEVELS = (0.75, 0.82)
_HOLD_EDGE = 0.01
_BISECTION_STEPS = 30
_COARSE_SD_STEP = 0.02
_COARSE_SD_MAX = 0.40
_FINE_SD_STEP = 0.005


@dataclass(frozen=True)
class SetGapRow:
    level: float
    win_prob: float
    hold_a: float
    hold_b: float
    chain_three_sets: float
    fit_three_sets: float

    @property
    def gap(self) -> float:
        return self.chain_three_sets - self.fit_three_sets


def holds_for_win_prob(win_prob: float, level: float, effect_sd: float = 0.0) -> tuple[float, float]:
    """Holds `level + d` and `level - d` whose best-of-3 chain gives `win_prob`."""
    low, high = 0.0, min(level - _HOLD_EDGE, 1.0 - _HOLD_EDGE - level)
    for _ in range(_BISECTION_STEPS):
        mid = (low + high) / 2.0
        if mixed_match_distribution(level + mid, level - mid, 3, effect_sd).win_prob < win_prob:
            low = mid
        else:
            high = mid
    d = (low + high) / 2.0
    return level + d, level - d


def set_gap_rows(
    effect_sd: float = 0.0,
    levels: tuple[float, ...] = HOLD_LEVELS,
    win_probs: tuple[float, ...] = WIN_PROBS,
) -> list[SetGapRow]:
    rows = []
    for level in levels:
        for win_prob in win_probs:
            hold_a, hold_b = holds_for_win_prob(win_prob, level, effect_sd)
            dist = mixed_match_distribution(hold_a, hold_b, 3, effect_sd)
            rows.append(SetGapRow(
                level, win_prob, hold_a, hold_b, dist.set_count.get(3, 0.0), three_set_probability(dist.win_prob),
            ))
    return rows


def largest_gap(rows: list[SetGapRow]) -> float:
    return max(abs(row.gap) for row in rows)


def fit_set_effect(levels: tuple[float, ...] = HOLD_LEVELS, win_probs: tuple[float, ...] = WIN_PROBS) -> float:
    """The effect sd with the smallest largest gap, to the fine grid step."""
    def worst(sd: float) -> float:
        return largest_gap(set_gap_rows(sd, levels, win_probs))

    coarse = [round(i * _COARSE_SD_STEP, 4) for i in range(int(round(_COARSE_SD_MAX / _COARSE_SD_STEP)) + 1)]
    best = min(coarse, key=worst)
    fine = [round(best + i * _FINE_SD_STEP, 4) for i in range(-3, 4) if best + i * _FINE_SD_STEP >= 0]
    return min(fine, key=worst)


def set_gap_report(rows: list[SetGapRow], effect_sd: float = 0.0) -> str:
    worst = largest_gap(rows)
    lines = [
        f"Best-of-3 P(3 sets): exact chain (effect sd {effect_sd:.3f}) vs tennis_sets fit",
        f"  {'level':>6}{'win':>7}{'hold_a':>8}{'hold_b':>8}{'chain':>8}{'fit':>8}{'gap':>8}",
    ]
    for row in rows:
        lines.append(
            f"  {row.level:6.2f}{row.win_prob:7.2f}{row.hold_a:8.3f}{row.hold_b:8.3f}"
            f"{row.chain_three_sets:8.3f}{row.fit_three_sets:8.3f}{row.gap:+8.3f}"
        )
    if effect_sd > 0.0:
        lines.append(f"  largest residual gap {worst:.3f} with the effect")
    else:
        verdict = "chain used as is" if worst < SET_GAP_STOP else "set effect required"
        lines.append(f"  largest gap {worst:.3f} against stop {SET_GAP_STOP:.2f}: {verdict}")
    return "\n".join(lines)


@dataclass(frozen=True)
class ServeSide:
    tour: str
    player: str
    serve_points: int
    aces: int
    double_faults: int


@dataclass(frozen=True)
class CountSample:
    """One player-match: the count, its serve points and the player's rate elsewhere."""
    tour: str
    serve_points: int
    rate: float
    count: int


@dataclass(frozen=True)
class DispersionFit:
    stat: str
    shape: float | None
    samples: dict[str, int]
    ratio_before: dict[str, float]
    ratio_after: dict[str, float]


def _count(value: str | None) -> int | None:
    try:
        number = float(value) if value else float("nan")
    except ValueError:
        return None
    return int(number) if number.is_integer() and number >= 0 else None


def serve_sides(contents: str, tour: str) -> list[ServeSide]:
    """Completed sides with aces, double faults and serve points above 0."""
    sides = []
    for row in csv.DictReader(StringIO(contents)):
        score = (row.get("score") or "").upper()
        if not score.strip() or any(mark in score for mark in _UNFINISHED):
            continue
        for side, name in (("w", "winner_name"), ("l", "loser_name")):
            points, aces, faults = (_count(row.get(f"{side}_{col}")) for col in ("svpt", "ace", "df"))
            player = (row.get(name) or "").strip()
            if player and points and aces is not None and faults is not None:
                sides.append(ServeSide(tour, player, points, aces, faults))
    return sides


def leave_one_out(sides: list[ServeSide], stat: str) -> list[CountSample]:
    """Each side scored at the player's rate in their other matches, with enough of them."""
    totals: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for side in sides:
        total = totals[(side.tour, side.player)]
        total[0] += 1
        total[1] += side.serve_points
        total[2] += getattr(side, stat)
    samples = []
    for side in sides:
        matches, points, count = totals[(side.tour, side.player)]
        if matches - 1 < MIN_OTHER_MATCHES:
            continue
        rate = (count - getattr(side, stat)) / (points - side.serve_points)
        samples.append(CountSample(side.tour, side.serve_points, rate, getattr(side, stat)))
    return samples


def _variances(sample: CountSample) -> tuple[float, float, float]:
    """Observed squared error, binomial variance, and the gamma term's coefficient."""
    n, r = sample.serve_points, sample.rate
    return (sample.count - n * r) ** 2, n * r * (1.0 - r), n * (n - 1) * r * r


def fit_dispersion(stat: str, samples: list[CountSample]) -> DispersionFit:
    """Method of moments: a rate multiplier Gamma(k, 1/k) adds n(n-1)r^2/k to the binomial variance.

    The shape is pooled across tours; None means no excess over the binomial.
    """
    terms = [_variances(sample) for sample in samples]
    excess = sum(sq - binom for sq, binom, _ in terms)
    coefficient = sum(c for _, _, c in terms)
    shape = coefficient / excess if excess > 0 and coefficient > 0 else None
    by_tour: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for sample, term in zip(samples, terms):
        by_tour[sample.tour].append(term)
        by_tour["all"].append(term)
    before, after = {}, {}
    for tour, rows in by_tour.items():
        observed = sum(sq for sq, _, _ in rows)
        binomial = sum(b for _, b, _ in rows)
        extra = sum(c for _, _, c in rows) / shape if shape else 0.0
        before[tour] = observed / binomial
        after[tour] = observed / (binomial + extra)
    return DispersionFit(stat, shape, {t: len(rows) for t, rows in by_tour.items()}, before, after)


def dispersion_report(fits: list[DispersionFit]) -> str:
    lines = ["Ace and DF dispersion: observed variance over model variance, leave-one-out rates"]
    lines.append(f"  {'stat':<14}{'tour':<6}{'n':>8}{'binomial':>10}{'gamma':>8}")
    for fit in fits:
        for tour in sorted(fit.samples, key=lambda t: (t == "all", t)):
            lines.append(
                f"  {fit.stat:<14}{tour:<6}{fit.samples[tour]:>8,}"
                f"{fit.ratio_before[tour]:10.3f}{fit.ratio_after[tour]:8.3f}"
            )
        shape = f"{fit.shape:.2f}" if fit.shape else "none (no excess)"
        lines.append(f"  {fit.stat} gamma shape {shape}")
    return "\n".join(lines)


def _download_sides() -> list[ServeSide]:
    from app.ingest.tennismylife import BASE_URL

    sides = []
    with httpx.Client(timeout=60.0) as client:
        for tour, path in DISPERSION_FILES:
            response = client.get(BASE_URL + path)
            response.raise_for_status()
            sides.extend(serve_sides(response.text, tour))
    return sides


def run_dispersion() -> str:
    sides = _download_sides()
    return dispersion_report([fit_dispersion(stat, leave_one_out(sides, stat)) for stat in ("aces", "double_faults")])


@dataclass(frozen=True)
class LevelCase:
    tour: str
    stat: str
    actual: float
    model: float


@dataclass(frozen=True)
class LevelRow:
    stat: str
    tour: str
    n: int
    actual: float
    model: float

    @property
    def bias(self) -> float:
        return self.model - self.actual

    @property
    def unverified(self) -> bool:
        return abs(self.bias) >= LEVEL_THRESHOLDS[self.stat]


def played_fantasy_score(sets: list[tuple[int, int]], player_is_p1: bool, box: BoxScoreCandidate) -> float | None:
    """PrizePicks scoring, as the simulation's fantasy score reads it."""
    if box.aces is None or box.double_faults is None:
        return None
    mine = [(a, b) if player_is_p1 else (b, a) for a, b in sets]
    games = sum(a - b for a, b in mine)
    set_diff = sum(1 if a > b else -1 for a, b in mine)
    return 10.0 + games + 3.0 * set_diff + 0.5 * box.aces - 0.5 * box.double_faults


def _sim_mean(sim: MatchSim, stat: str, player: int) -> float:
    values = stat_values(sim.draws, stat, player)
    if values is None:
        raise ValueError(f"The simulation has no {stat}")
    return float(values.mean())


def match_level_cases(
    tour: str, score: str, p1_id: int, sim: MatchSim, boxes: dict[int, BoxScoreCandidate | None],
) -> list[LevelCase]:
    """The played value beside the simulated mean for every stat the match can settle."""
    sets = parse_sets(score)
    cases = [
        LevelCase(tour, stat, float(actual_value(stat, sets, True)), _sim_mean(sim, stat, 0)) for stat in _MATCH_STATS
    ]
    for player, player_id in enumerate(sim.players):
        is_p1 = player_id == p1_id
        for stat in _SCORE_PLAYER_STATS:
            cases.append(LevelCase(tour, stat, float(actual_value(stat, sets, is_p1)), _sim_mean(sim, stat, player)))
        box = boxes.get(player_id)
        if box is None or player in sim.missing_ace_rate or player in sim.missing_df_rate:
            continue
        played = {stat: box_score_value(stat, box) for stat in _BOX_STATS}
        played["fantasy_score"] = played_fantasy_score(sets, is_p1, box)
        for stat, value in played.items():
            if value is not None:
                cases.append(LevelCase(tour, stat, float(value), _sim_mean(sim, stat, player)))
    return cases


def level_rows(cases: list[LevelCase]) -> list[LevelRow]:
    groups: dict[tuple[str, str], list[LevelCase]] = defaultdict(list)
    for case in cases:
        groups[(case.stat, case.tour)].append(case)
    order = list(LEVEL_THRESHOLDS)
    return [
        LevelRow(
            stat, tour, len(group),
            sum(c.actual for c in group) / len(group), sum(c.model for c in group) / len(group),
        )
        for (stat, tour), group in sorted(groups.items(), key=lambda item: (order.index(item[0][0]), item[0][1]))
    ]


def level_report(rows: list[LevelRow], simulated: int, skipped: dict[str, int]) -> str:
    skips = ", ".join(f"{count} {reason}" for reason, count in skipped.items() if count) or "none"
    lines = [
        f"Level check: {simulated} completed matches simulated from pre-start odds (skipped: {skips})",
        f"  {'stat':<26}{'tour':<6}{'n':>7}{'actual':>9}{'model':>9}{'bias':>8}{'stop':>7}  verdict",
    ]
    for row in rows:
        lines.append(
            f"  {row.stat:<26}{row.tour:<6}{row.n:>7,}{row.actual:>9.2f}{row.model:>9.2f}"
            f"{row.bias:>+8.2f}{LEVEL_THRESHOLDS[row.stat]:>7.2f}  {'unverified' if row.unverified else 'ok'}"
        )
    listed = ", ".join(f'("{row.stat}", "{row.tour}")' for row in rows if row.unverified)
    lines.append(f"  SIM_LEVEL_UNVERIFIED = frozenset({{{listed}}})")
    return "\n".join(lines)


def match_sim_for(
    match: PreStartMarketMatch, stats: dict[tuple[int, str | None], PlayerRollingStats],
) -> MatchSim | None:
    """The match simulated exactly as a v4 row on it would be."""
    p1_prob, p2_prob = devig_two_way(american_to_prob(match.p1_odds), american_to_prob(match.p2_odds))
    key = match.match_id
    inputs = SimInputs(
        opponent_ids={(match.p1_id, key): match.p2_id, (match.p2_id, key): match.p1_id},
        rolling_stats=stats,
        prediction_probs={},
        market_probs={(match.p1_id, key): p1_prob, (match.p2_id, key): p2_prob},
        market_totals={key: MarketTotal(match.total_line, match.over_odds, match.under_odds)},
    )
    prop = Prop(
        id=0, player_id=match.p1_id, player_name=None, match_id=key, source="level_check",
        stat_type="total_games", line=Decimal("0"), odds_type=None, fetched_at=match.start_utc,
        start_time=match.start_utc, surface=match.surface, best_of=match.best_of, player_tour=match.tour,
    )
    return build_match_sim(prop, inputs)


async def run_level() -> str:
    from app.db.pool import SessionLocal
    from app.repositories.matches import get_pre_start_market_matches
    from app.repositories.player_match_stats import get_box_score_candidates
    from app.repositories.players import get_rolling_stats_batch_all_surfaces

    async with SessionLocal() as db:
        matches = await get_pre_start_market_matches(db, LEVEL_SINCE, LEVEL_UNTIL, LEVEL_TOTAL_BOOK)
        player_ids = sorted({pid for match in matches for pid in (match.p1_id, match.p2_id)})
        stats = await get_rolling_stats_batch_all_surfaces(db, player_ids)
        pairs = sorted({(pid, match.match_id) for match in matches for pid in (match.p1_id, match.p2_id)})
        contexts = await get_box_score_candidates(db, pairs)
    joins = {pair: context.join().candidate for pair, context in contexts.items()}
    cases: list[LevelCase] = []
    skipped = {"unfinished": 0, "not simulated": 0}
    simulated = 0
    for match in matches:
        if not is_completed_score(match.score, match.best_of):
            skipped["unfinished"] += 1
            continue
        sim = match_sim_for(match, stats)
        if sim is None:
            skipped["not simulated"] += 1
            continue
        boxes = {pid: joins.get((pid, match.match_id)) for pid in (match.p1_id, match.p2_id)}
        cases.extend(match_level_cases(match.tour, match.score, match.p1_id, sim, boxes))
        simulated += 1
    return level_report(level_rows(cases), simulated, skipped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Checks for the 48c match simulation")
    parser.add_argument("--sets", action="store_true", help="compare the chain's deciding-set rate with the fit")
    parser.add_argument("--effect-sd", type=float, default=0.0, help="match-level hold shift sd for --sets")
    parser.add_argument("--fit-set-effect", action="store_true", help="fit the shift sd that minimizes the largest gap")
    parser.add_argument("--dispersion", action="store_true", help="fit the ace and DF gamma shapes from 2026 box scores")
    parser.add_argument("--level", action="store_true", help="mean bias of each stat on completed matches")
    args = parser.parse_args()
    if args.level:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print(asyncio.run(run_level()))
    elif args.dispersion:
        print(run_dispersion())
    elif args.fit_set_effect:
        sd = fit_set_effect()
        print(set_gap_report(set_gap_rows(sd), sd))
    elif args.sets:
        print(set_gap_report(set_gap_rows(args.effect_sd), args.effect_sd))
    else:
        parser.error("choose a check, e.g. --sets")
