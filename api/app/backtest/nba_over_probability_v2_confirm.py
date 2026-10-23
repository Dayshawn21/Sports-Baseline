"""Confirm NBA P(over) v2 once on 2026-27 weeks 1-4 (item 44b).

    python -m app.backtest.nba_over_probability_v2_confirm [--score]

Without `--score` it reads only `sport_games` and prints whether the sample's
weeks are finished. `--score` stops as accruing, before any box score is read,
until every week is finished, and refuses once a confirmation is recorded. It
scores 44a's frozen families, never a refit, and writes the generated result
module 44c serves from. 2023-26 box scores are projection inputs only; no
2025-26 case is scored, so that holdout's read count stays at 2.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.core.nba_over_probability import MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES
from app.core.nba_over_probability_v2 import NBA_OVER_PROBABILITY_V2_VERSION
from app.core.nba_over_probability_v2_confirmation_score import (
    ConfirmationResult,
    Drift,
    evaluate_markets,
    gate,
    normal_sigmas,
    parameter_drift,
    push_context,
    refit,
    sample_cases,
    score_sample,
)
from app.core.nba_over_probability_v2_crossfit import FamilyParams
from app.core.nba_over_probability_v2_fit import (
    CONFIRMATION_SEASON,
    CONFIRMATION_WEEKS,
    FIT_PROJECTION_MODEL_VERSION,
    FIT_SEASON,
    NOT_CARRIED,
    PARAMS_BY_MARKET,
    PRE_REGISTRATION_COMMIT,
)
from app.core.nba_projection_backtest import NbaReplayCase

# Every stored season, so prior-game depth matches serving's `get_prior_games`.
LOADED_SEASONS: tuple[int, ...] = (FIT_SEASON - 1, FIT_SEASON, FIT_SEASON + 1, CONFIRMATION_SEASON)

RESULT_MODULE_PATH = Path(__file__).resolve().parents[1] / "core" / "nba_over_probability_v2_confirmation.py"


def gate_report(progress: Mapping[int, tuple[int, int]], finished: set[int]) -> str:
    out = [f"NBA P(over) {NBA_OVER_PROBABILITY_V2_VERSION} confirmation sample: {CONFIRMATION_SEASON} weeks "
           f"{CONFIRMATION_WEEKS[0]}-{CONFIRMATION_WEEKS[-1]} (REG)"]
    for week in CONFIRMATION_WEEKS:
        games, completed = progress.get(week, (0, 0))
        out.append(f"  week {week}: {games} games, {completed} completed, {'finished' if week in finished else 'open'}")
    out.append(f"State: {gate(finished)}")
    return "\n".join(out)


def _failed(result: ConfirmationResult) -> str:
    if result.cases < MIN_CASES:
        return "cases"
    checks = [
        ("ECE", result.ece > MAX_ECE),
        ("worst gap", result.worst_gap is not None and result.worst_gap > MAX_BIN_GAP),
        ("Brier", result.brier > result.normal_brier),
    ]
    return ", ".join(name for name, failed in checks if failed)


def report(
    results: Mapping[str, ConfirmationResult], sample: Sequence[NbaReplayCase], week_by_game: Mapping[int, int],
    frozen: Mapping[str, FamilyParams],
) -> str:
    out = [
        f"NBA over probability {NBA_OVER_PROBABILITY_V2_VERSION}: one confirmation on {CONFIRMATION_SEASON} weeks "
        f"{CONFIRMATION_WEEKS[0]}-{CONFIRMATION_WEEKS[-1]}",
        f"Projection {FIT_PROJECTION_MODEL_VERSION}; families frozen on {FIT_SEASON}, rule pre-registered in "
        f"{PRE_REGISTRATION_COMMIT}; seasons loaded {', '.join(str(s) for s in LOADED_SEASONS)}; 2025-26 cases scored: 0",
        f"Show: >= {MIN_CASES} cases, ECE <= {MAX_ECE}, no bin of {MIN_BIN_PAIRS}+ pairs off by more than "
        f"{MAX_BIN_GAP}, Brier no worse than a constant-sigma normal (sigma from {FIT_SEASON}).",
        "",
        f"  {'market':<26}{'family':<15}{'cases':>7}{'pairs':>8}{'ECE':>8}{'worst':>8}{'Brier':>8}{'normal':>8}"
        "  verdict       failed on",
    ]
    for market in frozen:
        result = results.get(market)
        if result is None:
            out.append(f"  {market:<26}no cases")
            continue
        worst = f"{result.worst_gap:>8.3f}" if result.worst_gap is not None else f"{'--':>8}"
        out.append(
            f"  {market:<26}{result.family:<15}{result.cases:>7}{result.pairs:>8}{result.ece:>8.3f}{worst}"
            f"{result.brier:>8.4f}{result.normal_brier:>8.4f}  {result.verdict:<13} {_failed(result)}"
        )
    out += [f"  {market:<26}not_carried (44a)" for market in sorted(NOT_CARRIED)]
    games = {week: {g for g, w in week_by_game.items() if w == week} for week in CONFIRMATION_WEEKS}
    cases_by_week = Counter(week_by_game[case.game_id] for case in sample)
    out += ["", "Coverage (sample cases count every carried market)"]
    out += [
        f"  week {week}: {len(games[week])} games, {cases_by_week.get(week, 0)} cases"
        for week in CONFIRMATION_WEEKS
    ]
    out += [
        "", "Whole-number lines, information only (not part of the verdict): P(push) predicted vs observed",
        f"  {'market':<26}{'pairs':>8}{'predicted':>11}{'observed':>10}",
    ]
    pushes = push_context(frozen, sample)
    out += [
        f"  {market:<26}{c.pairs:>8}{c.predicted:>11.3f}{c.observed:>10.3f}"
        for market in frozen if (c := pushes.get(market))
    ]
    return "\n".join(out)


def drift_report(drift: Sequence[Drift]) -> str:
    out = [f"Stopped: the {FIT_SEASON} refit no longer reproduces the frozen parameters. Nothing was scored or written."]
    out += [f"  {d.market}: frozen {d.frozen}, refit {d.refit}" for d in drift]
    return "\n".join(out)


def render_module(results: Mapping[str, ConfirmationResult], scored_at: dt.datetime) -> str:
    shown = sorted(market for market, result in results.items() if result.verdict == "show")
    hidden = sorted(set(PARAMS_BY_MARKET) - set(shown))

    def literal(result: ConfirmationResult) -> str:
        return (
            f"ConfirmationResult(family={result.family!r}, cases={result.cases}, pairs={result.pairs}, "
            f"ece={result.ece!r}, worst_gap={result.worst_gap!r}, brier={result.brier!r}, "
            f"normal_brier={result.normal_brier!r}, verdict={result.verdict!r})"
        )

    def frozenset_literal(markets: Sequence[str]) -> str:
        return f"frozenset({{{', '.join(repr(str(m)) for m in markets)}}})" if markets else "frozenset()"

    lines = [
        '"""Generated by `python -m app.backtest.nba_over_probability_v2_confirm --score`. Do not edit.',
        "",
        f"The one confirmation of {NBA_OVER_PROBABILITY_V2_VERSION} on {CONFIRMATION_SEASON} weeks "
        f"{CONFIRMATION_WEEKS[0]}-{CONFIRMATION_WEEKS[-1]} (item 44b).",
        "Item 44c serves only `SHOWN_MARKETS`; a hidden market stays hidden for this version.",
        '"""',
        "from __future__ import annotations",
        "",
        "from app.core.nba_over_probability_v2_confirmation_score import ConfirmationResult",
        "",
        f"CONFIRMATION_SEASON = {CONFIRMATION_SEASON}",
        f"CONFIRMATION_WEEKS: tuple[int, ...] = {CONFIRMATION_WEEKS!r}",
        f'OVER_PROBABILITY_VERSION = "{NBA_OVER_PROBABILITY_V2_VERSION}"',
        f'FIT_PROJECTION_MODEL_VERSION = "{FIT_PROJECTION_MODEL_VERSION}"',
        f'SCORED_AT = "{scored_at.astimezone(dt.UTC).isoformat()}"',
        f"SHOWN_MARKETS: frozenset[str] = {frozenset_literal(shown)}",
        f"HIDDEN_MARKETS: frozenset[str] = {frozenset_literal(hidden)}",
        f"NOT_CARRIED: frozenset[str] = {frozenset_literal(sorted(NOT_CARRIED))}",
        "RESULTS: dict[str, ConfirmationResult] = {",
        *(f"    {str(market)!r}: {literal(result)}," for market, result in results.items()),
        "}",
    ]
    return "\n".join(lines) + "\n"


async def _main(score: bool, result_path: Path) -> None:
    from app.core.nba_projection_backtest import ARMS, REFERENCE_ARM, replay_cases
    from app.db.pool import SessionLocal
    from app.repositories import nba

    async with SessionLocal() as db:
        progress = await nba.get_week_progress(db, CONFIRMATION_SEASON, CONFIRMATION_WEEKS)
        finished = await nba.get_finished_weeks(db, CONFIRMATION_SEASON)
        print(gate_report(progress, finished))
        if not score:
            return
        if gate(finished) == "accruing":
            print("\nAccruing: nothing scored, no box score read.")
            return
        week_by_game = await nba.get_week_game_ids(db, CONFIRMATION_SEASON, CONFIRMATION_WEEKS)
        history = await nba.get_projection_history(db, LOADED_SEASONS)

    fit_cases = replay_cases(history, FIT_SEASON, ARMS[REFERENCE_ARM])
    drift = parameter_drift(PARAMS_BY_MARKET, refit(PARAMS_BY_MARKET, fit_cases))
    if drift:
        raise SystemExit(drift_report(drift))
    season_cases = replay_cases(history, CONFIRMATION_SEASON, ARMS[REFERENCE_ARM])
    sample = sample_cases(season_cases, week_by_game, PARAMS_BY_MARKET)
    lines = score_sample(PARAMS_BY_MARKET, normal_sigmas(fit_cases, PARAMS_BY_MARKET), sample)
    results = evaluate_markets(PARAMS_BY_MARKET, lines)
    print("\n" + report(results, sample, week_by_game, PARAMS_BY_MARKET))
    result_path.write_text(render_module(results, dt.datetime.now(dt.UTC)), encoding="utf-8")
    print(f"\nWrote {result_path}.")


def main(argv: Sequence[str] | None = None, result_path: Path = RESULT_MODULE_PATH) -> None:
    parser = argparse.ArgumentParser(description="Confirm NBA P(over) v2 once on 2026-27 weeks 1-4")
    parser.add_argument("--score", action="store_true", help="score the sample once, only when every week is finished")
    args = parser.parse_args(argv)
    if args.score and result_path.exists():
        parser.error(f"a confirmation is already recorded in {result_path.name}; it is never rescored")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.score, result_path))


if __name__ == "__main__":
    main()
