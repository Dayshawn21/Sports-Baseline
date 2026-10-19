"""Inspect, fit and score the pre-registered WTA 125 comparison (40a).

Data: Valuebetennis open data (https://www.valuebetennis.com), CC BY 4.0.
Run from api/: python -m app.backtest.tennis_wta125_blend [--count | --fit]
Run --score --download-date YYYY-MM-DD once, only after explicit approval.
"""
from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Literal

from app.backtest.tennis_closing_lines import (
    BURN_IN_SEASONS, CHALLENGER_CATEGORIES, DATA_DIR, DEVELOPMENT_SEASONS, EXCLUSION_ORDER, LAVER_CUP,
    ROI_MIN_EDGE, ClosingLineCase, LoadSummary, build_cases, exclusion, flat_stake, load_valuebetennis,
)
from app.backtest.tennis_market_blend_fit import FitResult, development_cases, fit_group, served_prob
from app.core.tennis_grading import PairedDifference, calibration_bins, paired_loss_difference, score_component
from app.core.tennis_market_blend import BlendCoefficients
from app.core.tennis_market_blend_fit import FIT_COEFFICIENTS
from app.core.valuebetennis import MAIN_DRAW_FIRST_ROUND, VbtMatch

SEASONS = tuple(range(2021, 2027))
# Fixed before any candidate fit or 2026 scoring; see the 40a pre-registration.
MIN_FIT_CASES = 300
MIN_SCORED_CASES = 300
VERDICT_SEASON = 2026
G1_STANDARD_ERRORS = 2.5
G2_STANDARD_ERRORS = 2.0
POOLED_FIT_N = 5734
FIT_TOLERANCE = 0.001
Verdict = Literal["accruing", "keep pooled", "adopt A", "adopt B"]

# Frozen before the 2026 verdict run; refitting on that season would invalidate it.
WTA125_FIT_N = 336
WTA125_FIT = BlendCoefficients(market=1.442269367193, elo=-0.201619489152)

EVENT_FILE = Path(__file__).with_name("data") / "tennis_wta125_events.csv"
ITF_LABEL = re.compile(r"^W\d+(?:\+H)?\s")
COUNT_REASONS = ("not WTA 125", *EXCLUSION_ORDER[1:])
REQUIRED_COLUMNS = frozenset({
    "match_id", "date", "tournoi", "categorie", "genre", "surface", "tour",
    "joueur1_id", "joueur2_id", "vainqueur_id", "score",
    "cote1_ouverture", "cote2_ouverture", "cote1_cloture", "cote2_cloture",
})


def _event_names() -> frozenset[tuple[int, str]]:
    with EVENT_FILE.open(encoding="utf-8", newline="") as handle:
        return frozenset((int(row["season"]), row["tournament"]) for row in csv.DictReader(handle))


WTA125_EVENTS = _event_names()


def decide(
    n_scored: int, gates: Mapping[str, tuple[PairedDifference, PairedDifference]],
) -> Verdict:
    if n_scored < MIN_SCORED_CASES:
        return "accruing"
    for name in ("A", "B"):
        if name not in gates:
            continue
        g1, g2 = gates[name]
        for difference in (g1, g2):
            if (difference.n != n_scored or difference.standard_error is None
                    or not isfinite(difference.mean) or not isfinite(difference.standard_error)
                    or difference.standard_error < 0):
                raise ValueError("Gates need finite paired differences and SEs on the full scored sample")
        if (g1.mean + G1_STANDARD_ERRORS * g1.standard_error < 0
                and g2.mean - G2_STANDARD_ERRORS * g2.standard_error <= 0):
            return "adopt A" if name == "A" else "adopt B"
    return "keep pooled"


def pooled_integrity(cases: list[ClosingLineCase]) -> FitResult:
    result = fit_group(development_cases(cases, "CHALLENGER"))
    expected = FIT_COEFFICIENTS["CHALLENGER"]
    if (result.n != POOLED_FIT_N or abs(result.coefficients.market - expected.market) > FIT_TOLERANCE
            or abs(result.coefficients.elo - expected.elo) > FIT_TOLERANCE):
        raise ValueError(
            "2022 pooled Challenger integrity MISMATCH; stop before candidate fitting.\n"
            f"  Refitted: n={result.n}, a={result.coefficients.market:.6f}, b={result.coefficients.elo:+.6f}\n"
            f"  Expected: n={POOLED_FIT_N}, a={expected.market:.6f}, b={expected.elo:+.6f}\n"
            f"  Required: exact n and coefficient differences <= {FIT_TOLERANCE}. User review required."
        )
    return result


def fit_candidate_b(cases: list[ClosingLineCase]) -> tuple[int, FitResult | None]:
    reliable = [c for c in cases if c.season in DEVELOPMENT_SEASONS and in_wta125(c) and c.elo_reliable]
    n = len(reliable)
    return n, fit_group(reliable) if n >= MIN_FIT_CASES else None


def _in_sample_lines(cases: list[ClosingLineCase], candidate: FitResult | None) -> list[str]:
    eligible = [c for c in cases if c.season in DEVELOPMENT_SEASONS and in_wta125(c)]
    lines = ["IN-SAMPLE 2022 log loss (not a verdict; same eligible cases, gated ELO served as the close)",
             f"  {'blend':<12}{'n':>7}{'log loss':>13}"]
    if not eligible:
        return [*lines, "  No eligible development cases."]
    columns = [("incumbent", FIT_COEFFICIENTS["CHALLENGER"]), ("A", FIT_COEFFICIENTS["WTA"])]
    if candidate is not None:
        columns.append(("B", candidate.coefficients))
    outcomes = [c.p1_won for c in eligible]
    for name, coefficients in columns:
        probabilities = _probabilities(eligible, coefficients)
        score = score_component(probabilities, outcomes)
        lines.append(f"  {name:<12}{score.n:>7}{score.log_loss:>13.6f}")
    return lines


def fit_report(matches: list[VbtMatch]) -> str:
    history = [m for m in matches if m.season in BURN_IN_SEASONS | DEVELOPMENT_SEASONS]
    cases = build_cases(history)
    result = pooled_integrity(cases)
    n, candidate = fit_candidate_b(cases)
    lines = [
        "WTA 125 blend backtest (40a) - 2022 development fit, IN-SAMPLE ONLY",
        "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.",
        f"  Integrity MATCH: n={result.n}, a={result.coefficients.market:.6f}, b={result.coefficients.elo:+.6f}",
        f"  Frozen n and both coefficients match within {FIT_TOLERANCE}.",
        "  No holdout season built or scored. No adoption decision is made by --fit.", "",
    ]
    if candidate is None:
        lines.append(f"B DROPPED: n={n} reliable 2022 WTA 125 cases; need {MIN_FIT_CASES}.")
    else:
        lines += [f"Candidate B: n={candidate.n} reliable 2022 WTA 125 cases (SEs in parentheses)",
                  f"  a={candidate.coefficients.market:.12f} ({candidate.market_se:.12f})",
                  f"  b={candidate.coefficients.elo:+.12f} ({candidate.elo_se:.12f})"]
    return "\n".join([*lines, "", *_in_sample_lines(cases, candidate)])


def in_wta125(case: ClosingLineCase) -> bool:
    return (
        case.tour == "WTA" and (case.season, case.tournament) in WTA125_EVENTS
        and exclusion(case, CHALLENGER_CATEGORIES) is None
    )


def _first_dates(matches: list[VbtMatch]) -> dict[int, date]:
    first: dict[int, date] = {}
    for match in matches:
        for player in (match.p1_id, match.p2_id):
            first[player] = min(first.get(player, match.match_date), match.match_date)
    return first


def _count_exclusion(match: VbtMatch, first: dict[int, date]) -> str | None:
    if match.tour == "WTA" and (match.season, match.tournament) not in WTA125_EVENTS:
        return "not WTA 125"
    if match.round_code < MAIN_DRAW_FIRST_ROUND:
        return "qualifying"
    if LAVER_CUP in match.tournament:
        return "Laver Cup"
    if not match.completed:
        return "not completed"
    if match.p1_close is None or match.p2_close is None:
        return "no closing price"
    # EloIndex has an overall rating exactly when each player has a prior-day match.
    # Checking presence avoids replaying results or computing any probability here.
    if any(first[player] >= match.match_date for player in (match.p1_id, match.p2_id)):
        return "missing ELO"
    return None


def _audit_labels(matches: list[VbtMatch]) -> list[str]:
    lines = ["Women's Challenger tier audit (all parsed labels, before match exclusions)"]
    for season in SEASONS:
        names = Counter(m.tournament for m in matches if m.season == season)
        verified = {name for name in names if (season, name) in WTA125_EVENTS}
        other = set(names) - verified
        unresolved = sorted(name for name in other if not ITF_LABEL.match(name))
        if unresolved:
            raise ValueError(f"{season}: unlisted women's Challenger labels need tier review: {unresolved}")
        lines.append(
            f"  {season}: WTA 125 labels {len(verified)}, rows {sum(names[n] for n in verified)}; "
            f"ITF labels {len(other)}, rows {sum(names[n] for n in other)}; unresolved labels 0"
        )
    return lines


def _top_names(title: str, matches: list[VbtMatch]) -> list[str]:
    names = Counter(m.tournament for m in matches)
    ranked = sorted(names.items(), key=lambda item: (-item[1], item[0]))[:10]
    return [title, *(f"  {n:>6}  {name}" for name, n in ranked)]


def count_report(matches: list[VbtMatch], summaries: list[LoadSummary]) -> str:
    challenger = [m for m in matches if m.season in SEASONS and m.category in CHALLENGER_CATEGORIES]
    women = [m for m in challenger if m.tour == "WTA"]
    audit = _audit_labels(women)
    first = _first_dates(matches)
    lines = [
        "WTA 125 blend backtest (40a) - COUNTS ONLY, seasons 2021-2026",
        "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.",
        "  Event tiers: frozen official WTA 125 calendar crosswalk (2026-10-19).",
        "  No outcomes, probabilities or losses computed. Eligible counts are not a verdict.",
        "", "Files (raw / parsed / skipped)",
    ]
    for summary in summaries:
        lines.append(f"  {summary.file}: {summary.rows} / {summary.parsed} / {sum(summary.skipped.values())}")
        if summary.skipped:
            lines.append("    " + ", ".join(f"{reason}={n}" for reason, n in sorted(summary.skipped.items())))
    lines += ["", *audit, "", "Challenger exclusions (first applicable reason; women restricted to verified WTA 125)",
              "  season tour   total eligible  " + " | ".join(COUNT_REASONS)]
    for season in SEASONS:
        for tour in ("WTA", "ATP"):
            subset = [m for m in challenger if m.season == season and m.tour == tour]
            counts = Counter(_count_exclusion(m, first) or "eligible" for m in subset)
            lines.append(f"  {season}   {tour} {len(subset):>7} {counts['eligible']:>8}  "
                         + " | ".join(str(counts[reason]) for reason in COUNT_REASONS))
    lines += ["", *_top_names("Top 10 women's Challenger names (all tiers, before exclusions)", women)]
    verified = [m for m in women if (m.season, m.tournament) in WTA125_EVENTS]
    lines += ["", *_top_names("Top 10 verified WTA 125 names (before match exclusions)", verified)]
    return "\n".join(lines)


def _probabilities(cases: list[ClosingLineCase], coefficients: BlendCoefficients | None) -> list[float]:
    values: list[float] = []
    for case in cases:
        value = case.market_prob if coefficients is None else served_prob(case, coefficients)
        if value is None:
            raise ValueError("Every comparison case needs a closing probability")
        values.append(value)
    return values


def _comparison_values(cases: list[ClosingLineCase]) -> dict[str, list[float]]:
    coefficients = {"close": None, "incumbent": FIT_COEFFICIENTS["CHALLENGER"], "A": FIT_COEFFICIENTS["WTA"]}
    if WTA125_FIT_N >= MIN_FIT_CASES:
        coefficients["B"] = WTA125_FIT
    return {name: _probabilities(cases, fit) for name, fit in coefficients.items()}


def _gate_differences(
    cases: list[ClosingLineCase], values: Mapping[str, list[float]],
) -> dict[str, tuple[PairedDifference, PairedDifference]]:
    outcomes = [c.p1_won for c in cases]
    return {
        name: (paired_loss_difference(values[name], values["incumbent"], outcomes),
               paired_loss_difference(values[name], values["close"], outcomes))
        for name in ("A", "B") if name in values
    }


def _gate_lines(gates: Mapping[str, tuple[PairedDifference, PairedDifference]]) -> list[str]:
    lines = ["Paired log-loss gates (candidate minus baseline; +/- one SE)"]
    for name, (g1, g2) in gates.items():
        upper = g1.mean + G1_STANDARD_ERRORS * (g1.standard_error or 0.0)
        lower = g2.mean - G2_STANDARD_ERRORS * (g2.standard_error or 0.0)
        lines += [
            f"  {name} G1 vs incumbent: n={g1.n}, {g1.mean:+.8f} +/- {g1.standard_error or 0.0:.8f}; "
            f"mean + {G1_STANDARD_ERRORS:g} SE = {upper:+.8f} -> {'pass' if upper < 0 else 'fail'}",
            f"  {name} G2 vs close: n={g2.n}, {g2.mean:+.8f} +/- {g2.standard_error or 0.0:.8f}; "
            f"mean - {G2_STANDARD_ERRORS:g} SE = {lower:+.8f} -> {'pass' if lower <= 0 else 'fail'}",
        ]
    return lines


def _score_lines(title: str, cases: list[ClosingLineCase], values: Mapping[str, list[float]]) -> list[str]:
    lines = [title, f"  {'blend':<12}{'n':>7}{'log loss':>13}{'Brier':>13}"]
    if not cases:
        return [*lines, "  No eligible cases."]
    outcomes = [c.p1_won for c in cases]
    for name, probabilities in values.items():
        score = score_component(probabilities, outcomes)
        lines.append(f"  {name:<12}{score.n:>7}{score.log_loss:>13.6f}{score.brier:>13.6f}")
    return lines


def _calibration_lines(cases: list[ClosingLineCase], values: Mapping[str, list[float]]) -> list[str]:
    lines = ["Calibration context only (bin: mean predicted / actual p1 win rate)"]
    outcomes = [c.p1_won for c in cases]
    for name, probabilities in values.items():
        bins = calibration_bins(probabilities, outcomes)
        lines.append(f"  {name}: " + "; ".join(
            f"{b.low:.1f}-{b.high:.1f}: {b.mean_predicted:.3f}/{b.actual_rate:.3f} (n={b.n})" for b in bins
        ))
    return lines


def _roi_lines(cases: list[ClosingLineCase], values: Mapping[str, list[float]]) -> list[str]:
    lines = [f"Flat-stake ROI context only (at the close; absolute edge >= {ROI_MIN_EDGE:.0%}, either side)"]
    for name, probabilities in values.items():
        if name == "close":
            continue
        returns = [flat_stake(replace(c, blend_prob=p)) for c, p in zip(cases, probabilities, strict=True)]
        bets = [r for r in returns if r is not None]
        if not bets:
            lines.append(f"  {name}: picks 0")
        else:
            profit = sum(bets)
            lines.append(f"  {name}: picks {len(bets)}, won {sum(r > 0 for r in bets)}, "
                         f"units {profit:+.2f}, ROI {profit / len(bets):+.1%}")
    return lines


def score_report(matches: list[VbtMatch], download_date: date) -> str:
    history = [m for m in matches if m.season in SEASONS and m.match_date <= download_date]
    women = [m for m in history if m.season == VERDICT_SEASON and m.tour == "WTA"
             and m.category in CHALLENGER_CATEGORIES]
    _audit_labels(women)
    first = _first_dates(history)
    n = sum(_count_exclusion(m, first) is None for m in women)
    lines = [f"WTA 125 blend backtest (40a) - {VERDICT_SEASON} verdict (score at most once)",
             "  Data: Valuebetennis open data (valuebetennis.com), CC BY 4.0.",
             f"  Download cutoff: {download_date.isoformat()}; eligible WTA 125 cases: {n}; minimum: {MIN_SCORED_CASES}."]
    if n < MIN_SCORED_CASES:
        return "\n".join([*lines, "  No probabilities, outcomes or losses computed; scored reads added: 0.",
                          f"Verdict: {decide(n, {})}"])
    cases = [c for c in build_cases(history) if c.season == VERDICT_SEASON]
    eligible = [c for c in cases if in_wta125(c)]
    if len(eligible) != n:
        raise ValueError("Count and replay populations differ; stop before loss computation")
    values = _comparison_values(eligible)
    gates = _gate_differences(eligible, values)
    verdict = decide(n, gates)
    men = [c for c in cases if c.tour == "ATP" and exclusion(c, CHALLENGER_CATEGORIES) is None]
    male_values = {"close": _probabilities(men, None), "incumbent": _probabilities(men, FIT_COEFFICIENTS["CHALLENGER"])}
    b_status = (f"  Frozen B: fit n={WTA125_FIT_N}, a={WTA125_FIT.market:.12f}, b={WTA125_FIT.elo:+.12f}."
                if WTA125_FIT_N >= MIN_FIT_CASES else f"  B dropped: fit n={WTA125_FIT_N} < {MIN_FIT_CASES}.")
    lines += [b_status, "",
              *_gate_lines(gates), "",
              *_score_lines("WTA 125 score context (same cases; only paired gates decide)", eligible, values), "",
              *_calibration_lines(eligible, values), "", *_roi_lines(eligible, values), "",
              *_score_lines("Men's Challenger context only (never decisive)", men, male_values), "",
              f"Verdict: {verdict}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspect the WTA 125 blend population and fit integrity (40a)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--count", action="store_true", help="counts only (the default); no scoring")
    mode.add_argument("--fit", action="store_true", help="verify the pooled fit, then fit B and report 2022 in-sample loss")
    mode.add_argument("--score", action="store_true", help="score 2026 once, only after explicit approval")
    parser.add_argument("--download-date", type=date.fromisoformat, help="snapshot download date; required with --score")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)
    if args.score and args.download_date is None:
        parser.error("--score requires --download-date YYYY-MM-DD for the downloaded snapshot")
    missing = [year for year in SEASONS if not (args.data_dir / f"valuebetennis-matchs-{year}.csv").is_file()]
    if missing:
        parser.error(f"Missing season files in {args.data_dir}: {missing}")
    for year in SEASONS:
        path = args.data_dir / f"valuebetennis-matchs-{year}.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            fields = csv.DictReader(handle, delimiter=";").fieldnames or []
        if not REQUIRED_COLUMNS.issubset(fields):
            parser.error(f"{path.name}: CSV layout changed; stop for review rather than modifying the parser")
    matches, summaries = load_valuebetennis(args.data_dir)
    try:
        if args.score:
            report = score_report(matches, args.download_date)
            fingerprints = [f"  {s.file}: SHA-256 {sha256((args.data_dir / s.file).read_bytes()).hexdigest()}"
                            for s in summaries]
            print("\n".join([report, "", "Input files", *fingerprints]))
        else:
            print(fit_report(matches) if args.fit else count_report(matches, summaries))
    except ValueError as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
