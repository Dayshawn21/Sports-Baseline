"""Score computed ELO and the hand-set ELO-plus-market blend against the closing line.

Data: Valuebetennis open data (https://www.valuebetennis.com), CC BY 4.0. Results
and Pinnacle opening and closing odds, one CSV per season, downloaded once into
api/data/valuebetennis/ (26c Step 1). Nothing here fetches the site, so a run
is reproducible from the downloads alone.

Run from api/: python -m app.backtest.tennis_closing_lines
"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd

from app.core.odds import devig_two_way
from app.core.tennis_grading import (
    PairedDifference, calibration_bins, clv_summary, paired_loss_difference, score_component,
)
from app.core.valuebetennis import MAIN_DRAW_FIRST_ROUND, VbtMatch, parse_row, row_problem
from app.ml.elo_history import EloIndex, expected_score
from app.services.tennis.ensemble import EnsembleInput, elo_is_unreliable, hand_set_blend

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "valuebetennis"
FILE_PATTERN = "valuebetennis-matchs-*.csv"
DOWNLOAD_URL = "https://www.valuebetennis.com/datasets/valuebetennis-matchs-<year>.csv"

# Pre-registered in the 26c spec (2026-09-30, amended 2026-10-01 before any score
# existed). Do not edit after the holdout run: a changed rule invalidates the verdict.
BURN_IN_SEASONS = frozenset({2021})
DEVELOPMENT_SEASONS = frozenset({2022})
HOLDOUT_SEASONS = frozenset({2023, 2024, 2025})
SCORED_CATEGORIES = frozenset({"Main tour", "Masters", "Grand Slam"})
CHALLENGER_CATEGORIES = frozenset({"Challenger"})
LAVER_CUP = "Laver Cup"
VERDICT_STANDARD_ERRORS = 2.0
ROI_MIN_EDGE = 0.03
CLV_MIN_GAP = 0.03

# The tour the live predictor passes to blend() for a Challenger match: matches.tour
# is stored as CHALLENGER, which takes the fallback weights.
CHALLENGER_TOUR_LABEL = "CHALLENGER"
# feature_builder flags a moneyline with more than 8% overround as high_overround.
HIGH_OVERROUND = 0.08


@dataclass
class LoadSummary:
    file: str
    rows: int = 0
    parsed: int = 0
    skipped: Counter[str] = field(default_factory=Counter)


def load_valuebetennis(folder: Path = DATA_DIR) -> tuple[list[VbtMatch], list[LoadSummary]]:
    files = sorted(folder.glob(FILE_PATTERN)) if folder.is_dir() else []
    if not files:
        raise FileNotFoundError(
            f"No {FILE_PATTERN} files in {folder}. Download the 2021-2026 season files "
            f"from {DOWNLOAD_URL} into that folder (26c Step 1)."
        )
    matches: list[VbtMatch] = []
    summaries: list[LoadSummary] = []
    for path in files:
        frame = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
        summary = LoadSummary(file=path.name, rows=len(frame))
        for row in frame.to_dict("records"):
            match = parse_row(row)
            if match is None:
                summary.skipped[row_problem(row) or "unparsed"] += 1
                continue
            matches.append(match)
            summary.parsed += 1
        summaries.append(summary)
    return matches, summaries


@dataclass(frozen=True)
class ClosingLineCase:
    tour: str
    category: str
    round_code: int
    tournament: str
    season: int
    match_date: date
    p1_id: int
    p2_id: int
    p1_won: bool
    completed: bool
    truncated: bool
    elo_prob: float | None
    market_prob: float | None
    open_prob: float | None
    blend_prob: float | None
    p1_close_decimal: float | None
    p2_close_decimal: float | None
    # Both ELO and the close exist and the live gate would not drop ELO (26d fits on these).
    elo_reliable: bool = False


def _devig_decimal(p1: float | None, p2: float | None) -> tuple[float, float] | None:
    """(p1 probability, overround), or None without both prices."""
    if p1 is None or p2 is None:
        return None
    raw1, raw2 = 1 / p1, 1 / p2
    return devig_two_way(raw1, raw2)[0], raw1 + raw2 - 1.0


def _elo_prob(elo: EloIndex, match: VbtMatch, p1_id: int, p2_id: int) -> float | None:
    s1 = elo.surface_rating(p1_id, match.surface, match.match_date)
    s2 = elo.surface_rating(p2_id, match.surface, match.match_date)
    if s1 is not None and s2 is not None:
        return expected_score(s1, s2)
    r1, r2 = elo.rating(p1_id, match.match_date), elo.rating(p2_id, match.match_date)
    if r1 is None or r2 is None:
        return None
    return expected_score(r1, r2)


def _played_dates(matches: Iterable[VbtMatch]) -> dict[int, list[date]]:
    dates: dict[int, list[date]] = defaultdict(list)
    for m in matches:
        dates[m.p1_id].append(m.match_date)
        dates[m.p2_id].append(m.match_date)
    for played in dates.values():
        played.sort()
    return dates


def build_cases(matches: list[VbtMatch]) -> list[ClosingLineCase]:
    """One case per match, p1 the lower player id, every rating strictly before the match date."""
    elo = EloIndex((m.match_date, m.p1_id, m.p2_id, m.winner_id, m.surface) for m in matches)
    played = _played_dates(matches)
    cases: list[ClosingLineCase] = []
    for m in matches:
        flipped = m.p1_id > m.p2_id
        p1_id, p2_id = (m.p2_id, m.p1_id) if flipped else (m.p1_id, m.p2_id)
        p1_close, p2_close = (m.p2_close, m.p1_close) if flipped else (m.p1_close, m.p2_close)
        p1_open, p2_open = (m.p2_open, m.p1_open) if flipped else (m.p1_open, m.p2_open)

        elo_prob = _elo_prob(elo, m, p1_id, p2_id)
        close = _devig_decimal(p1_close, p2_close)
        opening = _devig_decimal(p1_open, p2_open)
        market_prob = close[0] if close else None
        prior = min(bisect.bisect_left(played[p1_id], m.match_date), bisect.bisect_left(played[p2_id], m.match_date))
        unreliable = elo_is_unreliable(elo_prob, market_prob, prior)
        blended = hand_set_blend(EnsembleInput(
            tour=CHALLENGER_TOUR_LABEL if m.category == "Challenger" else m.tour,
            elo_prob=elo_prob,
            market_prob=market_prob,
            market_high_overround=close is not None and close[1] > HIGH_OVERROUND,
            elo_unreliable=unreliable,
        ))

        cases.append(ClosingLineCase(
            tour=m.tour, category=m.category, round_code=m.round_code, tournament=m.tournament,
            season=m.season, match_date=m.match_date, p1_id=p1_id, p2_id=p2_id,
            p1_won=m.winner_id == p1_id, completed=m.completed, truncated=m.truncated,
            elo_prob=elo_prob, market_prob=market_prob,
            open_prob=opening[0] if opening else None,
            blend_prob=blended.p1_win_prob if blended else None,
            p1_close_decimal=p1_close, p2_close_decimal=p2_close,
            elo_reliable=elo_prob is not None and market_prob is not None and not unreliable,
        ))
    return cases


Verdict = Literal["beats the close", "rejected against the close", "inconclusive"]
Probability = Callable[[ClosingLineCase], float | None]

GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("ATP", frozenset({"ATP"})),
    ("WTA", frozenset({"WTA"})),
    ("ATP+WTA", frozenset({"ATP", "WTA"})),
)
COMPONENTS: tuple[tuple[str, Probability], ...] = (
    ("elo (computed)", lambda c: c.elo_prob),
    ("blend", lambda c: c.blend_prob),
    ("market", lambda c: c.market_prob),
)
CANDIDATES = COMPONENTS[:2]
EXCLUSION_ORDER = ("category not scored", "qualifying", "Laver Cup", "not completed", "no closing price", "missing ELO")


def verdict(difference: PairedDifference) -> Verdict:
    margin = VERDICT_STANDARD_ERRORS * (difference.standard_error or 0.0)
    if difference.mean + margin < 0:
        return "beats the close"
    if difference.mean - margin > 0:
        return "rejected against the close"
    return "inconclusive"


def exclusion(case: ClosingLineCase, categories: frozenset[str] = SCORED_CATEGORIES) -> str | None:
    """Why a case is outside the scored set, in EXCLUSION_ORDER; None when it is scored."""
    if case.category not in categories:
        return "category not scored"
    if case.round_code < MAIN_DRAW_FIRST_ROUND:
        return "qualifying"
    if LAVER_CUP in case.tournament:
        return "Laver Cup"
    if not case.completed:
        return "not completed"
    if case.market_prob is None:
        return "no closing price"
    if case.elo_prob is None:
        return "missing ELO"
    return None


def _outcomes(cases: list[ClosingLineCase]) -> list[bool]:
    return [c.p1_won for c in cases]


def _values(cases: list[ClosingLineCase], get: Probability) -> list[float]:
    return [v for v in map(get, cases) if v is not None]


def _by_group(cases: list[ClosingLineCase]) -> list[tuple[str, list[ClosingLineCase]]]:
    return [(group, [c for c in cases if c.tour in tours]) for group, tours in GROUPS]


def _score_table(title: str, cases: list[ClosingLineCase]) -> list[str]:
    lines = [title, f"  {'group':<9}{'n':>7}  " + "  ".join(f"{name:>17}" for name, _ in COMPONENTS),
             f"  {'':<9}{'':>7}  " + "  ".join(f"{'logloss  brier':>17}" for _ in COMPONENTS)]
    for group, subset in _by_group(cases):
        if not subset:
            lines.append(f"  {group:<9}{0:>7}  (no eligible matches)")
            continue
        cells = []
        for _, get in COMPONENTS:
            score = score_component(_values(subset, get), _outcomes(subset))
            cells.append(f"{score.log_loss:>8.4f} {score.brier:>8.4f}")
        lines.append(f"  {group:<9}{len(subset):>7}  " + "  ".join(cells))
    return lines


def paired_differences(cases: list[ClosingLineCase]) -> dict[str, PairedDifference]:
    """Each candidate against the de-vigged close, on cases where every component exists."""
    market = _values(cases, lambda c: c.market_prob)
    return {name: paired_loss_difference(_values(cases, get), market, _outcomes(cases)) for name, get in CANDIDATES}


def _paired_section(cases: list[ClosingLineCase]) -> list[str]:
    lines = ["Paired log-loss difference vs the close (negative = beats the close; +/- one standard error)"]
    for group, subset in _by_group(cases):
        if len(subset) < 2:
            lines.append(f"  {group:<9}n={len(subset)} (too few)")
            continue
        cells = [f"{name} {d.mean:+.4f} +/- {d.standard_error or 0.0:.4f}" for name, d in paired_differences(subset).items()]
        lines.append(f"  {group:<9}n={len(subset):<6} " + "   ".join(cells))
    return lines


def _calibration_section(cases: list[ClosingLineCase]) -> list[str]:
    lines = ["Calibration, ATP+WTA (bin: mean predicted / actual p1 win rate)"]
    for name, get in (COMPONENTS[0], COMPONENTS[2]):
        bins = calibration_bins(_values(cases, get), _outcomes(cases))
        lines.append(f"  {name:<15}" + "  ".join(
            f"{b.low:.1f}-{b.high:.1f}: {b.mean_predicted:.2f}/{b.actual_rate:.2f} (n={b.n})" for b in bins))
    return lines


def flat_stake(case: ClosingLineCase) -> float | None:
    """Units won on one unit at the close on the side the blend favors by ROI_MIN_EDGE, else None."""
    if case.blend_prob is None or case.market_prob is None:
        return None
    edge = case.blend_prob - case.market_prob
    if abs(edge) < ROI_MIN_EDGE:
        return None
    on_p1 = edge > 0
    price = case.p1_close_decimal if on_p1 else case.p2_close_decimal
    if price is None:
        return None
    return price - 1.0 if case.p1_won == on_p1 else -1.0


def _roi_section(cases: list[ClosingLineCase]) -> list[str]:
    lines = [f"Flat-stake ROI at the close (blend - close >= {ROI_MIN_EDGE * 100:.0f} pts, either side; never decisive)"]
    for group, subset in _by_group(cases):
        results = [r for r in map(flat_stake, subset) if r is not None]
        if not results:
            lines.append(f"  {group:<9}picks 0")
            continue
        profit = sum(results)
        wins = sum(r > 0 for r in results)
        lines.append(f"  {group:<9}picks {len(results):>5}  won {wins:>5}  units {profit:+9.2f}  "
                     f"ROI {profit / len(results):+.1%}")
    return lines


def _clv_line(label: str, cases: list[ClosingLineCase], min_gap: float) -> str:
    summary = clv_summary([(c.elo_prob, c.open_prob, c.market_prob) for c in cases], min_gap)
    rate = f"{summary.toward_rate:.1%}" if summary.toward_rate is not None else "n/a"
    return (f"  {label:<22}eligible {summary.eligible:>6}  moved {summary.moved:>6}  "
            f"toward {summary.toward:>6} ({rate})  mean move toward {summary.mean_move_toward * 100:+.2f} pts")


def _clv_section(cases: list[ClosingLineCase]) -> list[str]:
    # The blend is built from the close, so grading it against the close would be circular.
    # A blend built from the open moves away from the open in ELO's direction.
    lines = ["Open-to-close CLV toward elo (computed) (stands in for the blend; never decisive)"]
    for group, subset in _by_group(cases):
        lines.append(_clv_line(group, subset, 0.0))
        lines.append(_clv_line(f"{group}, gap >= {CLV_MIN_GAP * 100:.0f} pts", subset, CLV_MIN_GAP))
    return lines


def _exclusion_section(in_scope: list[ClosingLineCase], out_of_scope: int, eligible: list[ClosingLineCase]) -> list[str]:
    reasons = Counter(r for r in map(exclusion, in_scope) if r is not None)
    return [
        "Exclusions",
        f"  {'burn-in or excluded season':<28}{out_of_scope:>8}",
        *(f"  {reason:<28}{reasons[reason]:>8}" for reason in EXCLUSION_ORDER),
        f"  {'scored':<28}{len(eligible):>8}  (completed by the truncation rule: {sum(c.truncated for c in eligible)})",
    ]


def _verdict_section(eligible: list[ClosingLineCase]) -> list[str]:
    lines = [f"Verdict (ATP+WTA holdout; pre-registered at {VERDICT_STANDARD_ERRORS:.0f} standard errors)"]
    for name, difference in paired_differences(eligible).items():
        lines.append(f"  {name:<15}{difference.mean:+.4f} +/- {difference.standard_error or 0.0:.4f}"
                     f"  ->  {verdict(difference)}")
    return lines


def _header(scope: frozenset[int], summaries: list[LoadSummary], holdout: bool) -> list[str]:
    lines = [
        f"Tennis closing-line backtest (26c) - {'HOLDOUT' if holdout else 'development'} seasons "
        + ", ".join(str(s) for s in sorted(scope)),
        "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0. Pinnacle opening and closing odds.",
        f"  Pre-registered: burn-in {sorted(BURN_IN_SEASONS)}, development {sorted(DEVELOPMENT_SEASONS)}, "
        f"holdout {sorted(HOLDOUT_SEASONS)} (scored once).",
        "  elo (computed) is replayed from these results; it is not the live TennisAbstract ELO.",
        f"  files {len(summaries)}, rows {sum(s.rows for s in summaries)}, parsed {sum(s.parsed for s in summaries)}",
    ]
    if not holdout:
        lines.append("  Holdout seasons are neither scored nor shown; run --holdout once, after review.")
    return lines


def report(cases: list[ClosingLineCase], summaries: list[LoadSummary], holdout: bool) -> str:
    scope = HOLDOUT_SEASONS if holdout else DEVELOPMENT_SEASONS
    visible = cases if holdout else [c for c in cases if c.season not in HOLDOUT_SEASONS]
    in_scope = [c for c in visible if c.season in scope]
    eligible = [c for c in in_scope if exclusion(c) is None]
    challenger = [c for c in in_scope if exclusion(c, CHALLENGER_CATEGORIES) is None]
    sections = [
        _header(scope, summaries, holdout),
        _exclusion_section(in_scope, len(visible) - len(in_scope), eligible),
        _score_table("Log loss and Brier (lower is better; same matches in every column)", eligible),
        _paired_section(eligible),
        _calibration_section(eligible),
        _roi_section(eligible),
        _clv_section(eligible),
        _score_table("Challenger (secondary, live Challenger blend weights; never decisive)", challenger),
        _paired_section(challenger),
    ]
    if holdout:
        sections.append(_verdict_section(eligible))
    return "\n\n".join("\n".join(section) for section in sections)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score computed ELO and the blend against the tennis closing line (26c)")
    parser.add_argument("--holdout", action="store_true", help="score the pre-registered holdout; run once")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    matches, summaries = load_valuebetennis(args.data_dir)
    print(report(build_cases(matches), summaries, holdout=args.holdout))


if __name__ == "__main__":
    main()
