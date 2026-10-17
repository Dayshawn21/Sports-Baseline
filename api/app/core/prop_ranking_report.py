"""The forward ranking check's printed report, shared by every sport's CLI (from 27j, 20g4).

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections.abc import Mapping

from app.core.prop_ranking_check import RankingCheck
from app.core.prop_ranking_rule import MIN_PERIODS, MIN_PICKS, SliceResult


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _verdict(result: SliceResult) -> str:
    if result.verdict != "insufficient":
        return result.verdict
    return f"accruing, {result.n} of {MIN_PICKS} picks, {result.periods} of {MIN_PERIODS} weeks"


def _slice_row(odds_type: str, side: str, result: SliceResult) -> str:
    label = f"{odds_type} {side}"
    return (
        f"  {label:<16}{result.n:>6}{result.periods:>7}{result.hits:>7}{_pct(result.hit_rate):>10}"
        f"{_pct(result.standard_error):>8}{_pct(result.break_even):>12}   {_verdict(result)}"
    )


def ranking_report(
    sport_label: str, season: int, check: RankingCheck, graded: int, exclusions: Mapping[str, int],
    coverage: Mapping[int, tuple[int, int]], model_version: str, over_probability_version: str, coverage_label: str,
) -> str:
    """Week wording throughout: every sport graded so far (NFL, NBA) uses the week as its period."""
    excluded = ", ".join(f"{reason} {n}" for reason, n in sorted(exclusions.items())) or "none"
    covered = ", ".join(f"wk {week} {frozen}/{lines}" for week, (lines, frozen) in sorted(coverage.items())) or "none"
    funnel = check.funnel
    return "\n".join([
        f"{sport_label} forward ranking check, {season} (model {model_version}, P(over) {over_probability_version})",
        f"Rule fixed 2026-09-26 (27i): a slice adopts only when hit rate - 2 SE beats its break-even,"
        f" on the first whole weeks holding {MIN_PICKS} picks over {MIN_PERIODS}+ weeks.",
        "",
        f"frozen rows on completed games {graded}; excluded: {excluded}",
        f"coverage, {coverage_label}: {covered}",
        f"funnel: calls {funnel.calls}, with P(over) {funnel.with_p_over}, picks {funnel.picks},"
        f" one per bet {funnel.bets}",
        "",
        "  slice            picks  weeks   hits  hit rate      SE  break-even   verdict",
        *(_slice_row(odds_type, side, result) for (odds_type, side), result in check.slices.items()),
    ])
