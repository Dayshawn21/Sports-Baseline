"""Choose each NBA market's P(over) v2 family on 2024-25 alone (item 44a).

    python -m app.backtest.nba_over_probability_v2_dev

Replays 20f's reference arm on 2024-25 (2023-24 only as early-window input),
cross-fits both candidate families by ISO-week parity, and applies the rule
pre-registered in `ebd4aea`. Reads no 2025-26 or 2026-27 row: 2025-26 was read
twice already, and 2026-27 is 44b's one confirmation sample.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable, Mapping, Sequence
from math import isinf
from pathlib import Path

from app.core.count_over_probability import NegBinParams
from app.core.nba_over_probability import MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES, ScoredLine
from app.core.nba_over_probability_v2 import (
    CANDIDATE_ORDER,
    CONFIRMATION_SEASON,
    CONFIRMATION_WEEKS,
    FIT_SEASON,
    NBA_OVER_PROBABILITY_V2_VERSION,
    TARGET_MARKETS,
    CandidateResult,
    Family,
    select_family,
)
from app.core.nba_over_probability_v2_crossfit import FamilyParams, cross_fit, evaluate, fit_family, push_context
from app.core.nba_projection_backtest import NBA_PROJECTION_MODEL_VERSION, NbaReplayCase
from app.core.nfl_over_probability_calibration import CalibrationPair, calibrate

LOADED_SEASONS: tuple[int, ...] = (FIT_SEASON - 1, FIT_SEASON)
PRE_REGISTRATION_COMMIT = "ebd4aea"

FIT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nba_over_probability_v2_fit.py"


def _failed(result: CandidateResult, ece: float, worst: float | None, normal_brier: float) -> str:
    if result.cases < MIN_CASES:
        return "cases"
    checks = [
        ("ECE", ece > MAX_ECE),
        ("worst gap", worst is not None and worst > MAX_BIN_GAP),
        ("Brier", result.brier > normal_brier),
    ]
    return ", ".join(name for name, failed in checks if failed)


def _row(family: Family, lines: Sequence[ScoredLine]) -> tuple[CandidateResult, str]:
    result = evaluate(family, lines)
    report = calibrate(CalibrationPair(line.p_over, line.over) for line in lines)
    worst_gaps = [b.gap for b in report.bins if b.n >= MIN_BIN_PAIRS]
    worst = max(worst_gaps) if worst_gaps else None
    normal = sum((line.normal_p_over - line.over) ** 2 for line in lines) / len(lines)
    worst_text = f"{worst:>8.3f}" if worst is not None else f"{'--':>8}"
    text = (
        f"  {family:<15}{result.cases:>7}{len(lines):>8}{report.ece:>8.3f}{worst_text}"
        f"{result.brier:>8.4f}{normal:>8.4f}  {result.verdict:<9} {_failed(result, report.ece, worst, normal)}"
    )
    return result, text


def report(cases: Sequence[NbaReplayCase]) -> str:
    return build(cases)[0]


def build(cases: Sequence[NbaReplayCase]) -> tuple[str, dict[str, Family | None]]:
    """The report text and each target market's selected family (None: not carried)."""
    scored = {family: cross_fit(family, cases) for family in CANDIDATE_ORDER}
    pushes = {family: push_context(family, cases) for family in CANDIDATE_ORDER}
    header = f"  {'family':<15}{'cases':>7}{'pairs':>8}{'ECE':>8}{'worst':>8}{'Brier':>8}{'normal':>8}  verdict   failed on"
    out = [
        f"NBA over probability {NBA_OVER_PROBABILITY_V2_VERSION}: family selection on "
        f"{FIT_SEASON}-{(FIT_SEASON + 1) % 100:02d}, cross-fitted by ISO-week parity",
        f"Projection {NBA_PROJECTION_MODEL_VERSION}; rule pre-registered in {PRE_REGISTRATION_COMMIT}; "
        f"seasons loaded {', '.join(str(s) for s in LOADED_SEASONS)}; 2025-26 reads 0, 2026-27 reads 0",
        f"Eligible: >= {MIN_CASES} cases, ECE <= {MAX_ECE}, no bin of {MIN_BIN_PAIRS}+ pairs off by more than "
        f"{MAX_BIN_GAP}, Brier no worse than a constant-sigma normal. Pick: lowest Brier, ties to {CANDIDATE_ORDER[0]}.",
    ]
    selection: dict[str, Family | None] = {}
    for market in TARGET_MARKETS:
        results = []
        out += ["", market, header]
        for family in CANDIDATE_ORDER:
            lines = [line for line in scored[family] if line.case.market == market]
            if not lines:
                out.append(f"  {family:<15}no cases")
                continue
            result, text = _row(family, lines)
            results.append(result)
            out.append(text)
        selection[market] = select_family(results)
    out += ["", "Selection (frozen by --write)"]
    out += [f"  {market:<26}{choice or 'not_carried'}" for market, choice in selection.items()]
    out += [
        "", "Whole-number lines, information only (not part of the verdict): P(push) predicted vs observed",
        f"  {'market':<26}{'family':<15}{'pairs':>8}{'predicted':>11}{'observed':>10}",
    ]
    for market in TARGET_MARKETS:
        for family in CANDIDATE_ORDER:
            context = pushes[family].get(market)
            if context:
                out.append(
                    f"  {market:<26}{family:<15}{context.pairs:>8}{context.predicted:>11.3f}{context.observed:>10.3f}"
                )
    return "\n".join(out), selection


def render_module(params_by_market: Mapping[str, FamilyParams], not_carried: Iterable[str]) -> str:
    # repr keeps every digit, so 44b reads exactly the parameters fitted here.
    def literal(params: FamilyParams) -> str:
        if isinstance(params, NegBinParams):
            return f"NegBinParams(r={'inf' if isinf(params.r) else repr(params.r)})"
        return f"ScaledNormalParams(a={params.a!r}, b={params.b!r})"

    uses_inf = any(isinstance(p, NegBinParams) and isinf(p.r) for p in params_by_market.values())
    lines = [
        '"""Generated by `python -m app.backtest.nba_over_probability_v2_dev --write`. Do not edit.',
        "",
        f"Each carried market's P(over) family, fitted on all of {FIT_SEASON}-{(FIT_SEASON + 1) % 100:02d} for",
        f"projection model {NBA_PROJECTION_MODEL_VERSION} and selected under the rule pre-registered in",
        f"{PRE_REGISTRATION_COMMIT} (item 44a). Item 44b scores these once on {CONFIRMATION_SEASON} weeks",
        f"{CONFIRMATION_WEEKS[0]}-{CONFIRMATION_WEEKS[-1]}; it never refits.",
        '"""',
        "from __future__ import annotations",
        "",
        *(["from math import inf", ""] if uses_inf else []),
        "from app.core.count_over_probability import NegBinParams, ScaledNormalParams",
        "",
        f"FIT_SEASON = {FIT_SEASON}",
        f"CONFIRMATION_SEASON = {CONFIRMATION_SEASON}",
        f"CONFIRMATION_WEEKS: tuple[int, ...] = {CONFIRMATION_WEEKS!r}",
        f'FIT_PROJECTION_MODEL_VERSION = "{NBA_PROJECTION_MODEL_VERSION}"',
        f'OVER_PROBABILITY_VERSION = "{NBA_OVER_PROBABILITY_V2_VERSION}"',
        f'PRE_REGISTRATION_COMMIT = "{PRE_REGISTRATION_COMMIT}"',
        "PARAMS_BY_MARKET: dict[str, NegBinParams | ScaledNormalParams] = {",
        # str() first: the target markets are StrEnum members, whose repr is not a plain literal.
        *(f"    {str(market)!r}: {literal(params)}," for market, params in params_by_market.items()),
        "}",
        f"NOT_CARRIED: frozenset[str] = frozenset({{{', '.join(repr(str(m)) for m in sorted(not_carried))}}})",
    ]
    return "\n".join(lines) + "\n"


async def _main(write: bool) -> None:
    from app.core.nba_projection_backtest import ARMS, REFERENCE_ARM, replay_cases
    from app.db.pool import SessionLocal
    from app.repositories.nba import get_projection_history

    async with SessionLocal() as db:
        history = await get_projection_history(db, LOADED_SEASONS)
    cases = replay_cases(history, FIT_SEASON, ARMS[REFERENCE_ARM])
    text, selection = build(cases)
    print(text)
    if write:
        params = {
            market: fit_family(family, [case for case in cases if case.market == market])
            for market, family in selection.items() if family is not None
        }
        not_carried = [market for market, family in selection.items() if family is None]
        FIT_MODULE_PATH.write_text(render_module(params, not_carried), encoding="utf-8")
        print(f"\nWrote {FIT_MODULE_PATH} with {len(params)} carried market(s).")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Choose NBA P(over) v2 families on 2024-25 only")
    parser.add_argument("--season", type=int, default=FIT_SEASON, help="must be 2024; any other season is refused")
    parser.add_argument("--write", action="store_true", help="freeze the selection into the generated fit module")
    args = parser.parse_args(argv)
    if args.season != FIT_SEASON:
        parser.error(f"only {FIT_SEASON} is allowed: 2025-26 is read out and 2026-27 is 44b's confirmation sample")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.write))


if __name__ == "__main__":
    main()
