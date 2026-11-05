"""Select the NHL P(over) family per market on the development season, then confirm it once (item 56c2).

    python -m app.backtest.nhl_over_probability_fit
    python -m app.backtest.nhl_over_probability_fit --confirm --holdout --write

The default run reads 2023 (history for early windows) and 2024 (2024-25, the development season)
only, in a read-only transaction. Every family is cross-fitted by ISO-week parity and the family a
market is carried with is chosen by the rule pre-registered in `app/core/nhl_over_probability.py`.

`--confirm --holdout` is the one read of 2025-26: the families selected on development are fitted on
all of 2024-25 and scored on 2025-26. `--write` is required with it: it renders the generated module from
the 2024-25 fits that were scored, for the markets that pass, and that module is the record of the read.
The run refuses to start when the module already exists, so the holdout cannot be read twice by accident.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Mapping, Sequence
from math import isinf
from pathlib import Path

from app.core.count_over_probability import NegBinParams, ScaledNormalParams
from app.core.nhl_over_probability import (
    CANDIDATE_ORDER,
    CONFIRMATION_SEASON,
    FIT_SEASON,
    MAX_BIN_GAP,
    MAX_ECE,
    MIN_CASES,
    NHL_OVER_PROBABILITY_VERSION,
    NHL_PROJECTION_MODEL_VERSION,
    RULE_TEXT,
)
from app.core.nhl_over_probability_crossfit import (
    Confirmation,
    FamilyDiagnostics,
    MarketSelection,
    RatioParams,
    confirm_markets,
    select_markets,
)
from app.core.nhl_projection_backtest import (
    ARMS, PRIOR_SEASON, REFERENCE_ARM, NhlHistoryRow, NhlReplayCase, replay_cases,
)
from app.nhl.markets import NhlLineOnlyMarket

# The commit that fixed the candidates, selection rule, display rule and versions before any NHL family was fitted.
PREREGISTRATION_COMMIT = "512fe51eebd18dd3e7abd3bc15aa82e640831185"

DEVELOPMENT_SEASONS = (PRIOR_SEASON, FIT_SEASON)
# The confirmation also reads the holdout season; 2024 stays in for its prior-season windows.
CONFIRMATION_SEASONS = (PRIOR_SEASON, FIT_SEASON, CONFIRMATION_SEASON)

FIT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nhl_over_probability_fit.py"

INTEGER_LINE_NOTE = (
    "Integer lines: a whole-number line can push, which no family models, so it reads no probability. "
    "The synthetic lines scored here are x.5 by construction, so this report cannot show how many posted "
    "lines are whole numbers (Goalie Saves and Goals Allowed post some)."
)


def season_label(season: int) -> str:
    return f"{season}-{(season + 1) % 100:02d}"


def check_flags(confirm: bool, holdout: bool, write: bool) -> None:
    if confirm and not write:
        raise ValueError(
            "--confirm records its read by writing the generated module, which is what stops a second read, "
            "so it needs --write",
        )
    if confirm and not holdout:
        raise ValueError(f"--confirm reads the {season_label(CONFIRMATION_SEASON)} holdout and needs --holdout")
    if holdout and not confirm:
        raise ValueError("--holdout only applies to --confirm")
    if write and not confirm:
        raise ValueError("--write renders the fit that --confirm scored, so it needs --confirm")


def check_module_absent(path: Path) -> None:
    """The holdout is read once: a generated module on disk means that read already happened."""
    if path.exists():
        raise ValueError(
            f"{path.name} already exists, so the {season_label(CONFIRMATION_SEASON)} holdout was already read; "
            "a second read needs a new pre-registered version",
        )


def _header(case_count: int, holdout_read: bool) -> list[str]:
    return [
        f"NHL over-probability fit, {season_label(FIT_SEASON)} (development: select freely)",
        "",
        f"Pre-registered in commit {PREREGISTRATION_COMMIT}.",
        RULE_TEXT,
        f"Projection {NHL_PROJECTION_MODEL_VERSION}, over-probability {NHL_OVER_PROBABILITY_VERSION}; "
        f"candidates in tie-break order: {', '.join(CANDIDATE_ORDER)}.",
        f"Cases: {case_count} reference-arm replay cases from {season_label(FIT_SEASON)}, cross-fitted by ISO-week parity.",
        INTEGER_LINE_NOTE,
        f"Holdout ({season_label(CONFIRMATION_SEASON)}): "
        + ("read once in this run, reported below." if holdout_read else "not read."),
    ]


def failed_checks(cases: int, diagnostics: FamilyDiagnostics, brier: float) -> str:
    """Which of the registered checks a family missed, for the report; empty when none."""
    failed = []
    if cases < MIN_CASES:
        failed.append(f"cases<{MIN_CASES}")
    if diagnostics.ece is not None and diagnostics.ece > MAX_ECE:
        failed.append("ece")
    if diagnostics.worst_gap is not None and diagnostics.worst_gap > MAX_BIN_GAP:
        failed.append("bin")
    if diagnostics.normal_brier is not None and brier > diagnostics.normal_brier:
        failed.append("brier")
    return ",".join(failed)


def _num(value: float | None) -> str:
    return f"{value:8.4f}" if value is not None else f"{'--':>8}"


def _selection_table(selections: Mapping[NhlLineOnlyMarket, MarketSelection]) -> list[str]:
    header = f"  {'market / family':<34}{'cases':>7}{'pairs':>8}{'ECE':>8}{'gap':>8}{'Brier':>8}{'normal':>8}  verdict"
    lines = ["Cross-fit at synthetic x.5 lines", header]
    for market in NhlLineOnlyMarket:
        selection = selections.get(market)
        if selection is None:
            continue
        for result, diagnostics in zip(selection.results, selection.diagnostics, strict=True):
            failed = failed_checks(result.cases, diagnostics, result.brier)
            brier = _num(None if diagnostics.pairs == 0 else result.brier)
            lines.append(
                f"  {market.value + ' / ' + result.family:<34}{result.cases:>7}{diagnostics.pairs:>8}"
                f"{_num(diagnostics.ece)}{_num(diagnostics.worst_gap)}{brier}{_num(diagnostics.normal_brier)}"
                f"  {result.verdict}{' (' + failed + ')' if failed else ''}",
            )
    return lines


def _chosen(selections: Mapping[NhlLineOnlyMarket, MarketSelection]) -> list[str]:
    lines = ["Selected on development (each goes to the one holdout read; hidden markets never do)"]
    for market in NhlLineOnlyMarket:
        selection = selections.get(market)
        if selection is not None:
            lines.append(f"  {market.value:<20}{selection.selected or 'hidden (no eligible family)'}")
    return lines


def report(
    cases: Sequence[NhlReplayCase], selections: Mapping[NhlLineOnlyMarket, MarketSelection], *, holdout_read: bool = False,
) -> str:
    return "\n".join([*_header(len(cases), holdout_read), "", *_selection_table(selections), "", *_chosen(selections)])


def confirmation_report(confirmations: Mapping[NhlLineOnlyMarket, Confirmation]) -> str:
    lines = [
        f"HOLDOUT {season_label(CONFIRMATION_SEASON)}: holdout read 1 (the one read; nothing was fitted on it)",
        f"Each selected family, fitted on all of {season_label(FIT_SEASON)}, scored once under the same display rule.",
        "",
        f"  {'market / family':<34}{'cases':>7}{'pairs':>8}{'ECE':>8}{'gap':>8}{'Brier':>8}{'normal':>8}  verdict",
    ]
    for market in NhlLineOnlyMarket:
        confirmation = confirmations.get(market)
        if confirmation is None:
            continue
        diagnostics, result = confirmation.diagnostics, confirmation.result
        failed = failed_checks(result.cases, diagnostics, result.brier)
        brier = _num(None if diagnostics.pairs == 0 else result.brier)
        lines.append(
            f"  {market.value + ' / ' + confirmation.family:<34}{result.cases:>7}{diagnostics.pairs:>8}"
            f"{_num(diagnostics.ece)}{_num(diagnostics.worst_gap)}{brier}{_num(diagnostics.normal_brier)}"
            f"  {result.verdict}{' (' + failed + ')' if failed else ''}",
        )
    shown = [market.value for market in NhlLineOnlyMarket if _shown(confirmations.get(market))]
    return "\n".join([*lines, "", f"Shown: {', '.join(shown) if shown else 'none'}"])


def _shown(confirmation: Confirmation | None) -> bool:
    return confirmation is not None and confirmation.fit is not None and confirmation.result.verdict == "show"


def _float(value: float) -> str:
    return "float('inf')" if isinf(value) else repr(float(value))


def _entry(market: NhlLineOnlyMarket, confirmation: Confirmation) -> tuple[str, str]:
    """The family's table the market belongs in, and its rendered line."""
    params = confirmation.fit.params if confirmation.fit else None
    if isinstance(params, NegBinParams):
        return "NEGBIN_R", f"    {market.value!r}: {_float(params.r)},"
    if isinstance(params, ScaledNormalParams):
        return "SCALED_NORMAL", f"    {market.value!r}: ({_float(params.a)}, {_float(params.b)}),"
    if isinstance(params, RatioParams):
        body = ", ".join(_float(q) for q in params.quantiles)
        return "RATIO_QUANTILES", f"    {market.value!r}: ({body}),"
    raise ValueError(f"{market.value} has no fitted parameters to render")


def render_module(confirmations: Mapping[NhlLineOnlyMarket, Confirmation]) -> str:
    """The generated fit module: the 2024-25 fits of the markets that passed, and nothing for hidden ones."""
    shown = {market: c for market in NhlLineOnlyMarket if _shown(c := confirmations.get(market))}
    tables: dict[str, list[str]] = {"NEGBIN_R": [], "SCALED_NORMAL": [], "RATIO_QUANTILES": []}
    for market, confirmation in shown.items():
        table, line = _entry(market, confirmation)
        tables[table].append(line)

    def block(name: str, annotation: str) -> list[str]:
        return [f"{name}: {annotation} = {{", *tables[name], "}"]

    shown_names = ", ".join(repr(market.value) for market in shown)
    families = "".join(f"    {market.value!r}: {confirmation.family!r},\n" for market, confirmation in shown.items())
    return "\n".join([
        '"""Generated by `python -m app.backtest.nhl_over_probability_fit --confirm --holdout --write`. Do not edit.',
        "",
        f"Per-market P(over) parameters for the reference projection {NHL_PROJECTION_MODEL_VERSION}, fitted on",
        f"{season_label(FIT_SEASON)} and scored once on the {season_label(CONFIRMATION_SEASON)} holdout (item 56c2).",
        "Only markets that passed the pre-registered display rule are included.",
        '"""',
        "from __future__ import annotations",
        "",
        f"FIT_SEASON = {FIT_SEASON}",
        f"SCORED_SEASON = {CONFIRMATION_SEASON}",
        f"FIT_PROJECTION_MODEL_VERSION = {NHL_PROJECTION_MODEL_VERSION!r}",
        f"OVER_PROBABILITY_VERSION = {NHL_OVER_PROBABILITY_VERSION!r}",
        f"PRE_REGISTRATION_COMMIT = {PREREGISTRATION_COMMIT!r}",
        f"SHOWN_MARKETS: frozenset[str] = frozenset({{{shown_names}}})",
        "FAMILY_BY_MARKET: dict[str, str] = {",
        families.rstrip("\n"),
        "}",
        *block("NEGBIN_R", "dict[str, float]"),
        *block("SCALED_NORMAL", "dict[str, tuple[float, float]]"),
        *block("RATIO_QUANTILES", "dict[str, tuple[float, ...]]"),
        "",
    ])


async def _load_history(seasons: Sequence[int]) -> list[NhlHistoryRow]:
    from sqlalchemy import text

    from app.db.pool import SessionLocal
    from app.repositories.nhl import get_projection_history

    async with SessionLocal() as db:
        await db.execute(text("SET TRANSACTION READ ONLY"))
        return await get_projection_history(db, seasons)


async def _develop() -> None:
    cases = replay_cases(await _load_history(DEVELOPMENT_SEASONS), FIT_SEASON, ARMS[REFERENCE_ARM])
    print(report(cases, select_markets(cases)))


async def _confirm(write: bool) -> None:
    check_module_absent(FIT_MODULE_PATH)
    history = await _load_history(CONFIRMATION_SEASONS)
    fit_cases = replay_cases(history, FIT_SEASON, ARMS[REFERENCE_ARM])
    holdout_cases = replay_cases(history, CONFIRMATION_SEASON, ARMS[REFERENCE_ARM])
    selections = select_markets(fit_cases)
    selected = {market: selection.selected for market, selection in selections.items() if selection.selected}
    confirmations = confirm_markets(selected, fit_cases, holdout_cases)
    print(report(fit_cases, selections, holdout_read=True))
    print()
    print(confirmation_report(confirmations))
    if write:
        FIT_MODULE_PATH.write_text(render_module(confirmations), encoding="utf-8", newline="\n")
        print(f"\nWrote {FIT_MODULE_PATH.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Select and confirm NHL P(over) families")
    parser.add_argument("--confirm", action="store_true", help="the one holdout read (needs --holdout and --write)")
    parser.add_argument("--holdout", action="store_true", help="allow reading the 2025-26 holdout")
    parser.add_argument("--write", action="store_true", help="render the generated module (needs --confirm)")
    args = parser.parse_args()
    try:
        check_flags(args.confirm, args.holdout, args.write)
        if args.confirm:
            check_module_absent(FIT_MODULE_PATH)
    except ValueError as error:
        parser.error(str(error))
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_confirm(args.write) if args.confirm else _develop())
