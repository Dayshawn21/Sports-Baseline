"""Score `nba-minutes-v1` against `nba-reference-v1` on 2024-25 (item 65a).

    python -m app.backtest.nba_minutes --season 2024

k is fitted on 2023-24 only, then 2024-25 is scored once under the development gate
pre-registered in commit 3a886a6f. 2025-26 is the holdout and is refused.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.core.nba_line_only import line_only_value
from app.core.nba_minutes import (
    FitCase, Situation, fit_rotation_coefficient, k_in_range, project_minutes_line, situations,
)
from app.core.nba_minutes_rule import (
    AFFECTED_MINUTES, CANDIDATE_VERSION, COMPARISON_VERSION, DEVELOPMENT_SEASON, FIT_SEASON, development_verdict,
    is_affected,
)
from app.core.nba_projection_backtest import (
    BACKTEST_MARKETS, HOLDOUT_SEASON, MIN_PAIRED_CASES, MIN_RELATIVE_MAE_IMPROVEMENT, STANDARD_ERRORS_REQUIRED,
    NbaReplayCase,
)
from app.core.nfl_projection_backtest import market_metrics, paired

PRE_REGISTRATION_COMMIT = "3a886a6f56d8c2135a0c7c2a7ae0ae6eb00586a0"
Source = Literal["previous_game", "oracle"]

RULE_TEXT = (
    f"A market passes to 65b only with >= {MIN_PAIRED_CASES} affected paired cases (|minutes change| >= "
    f"{AFFECTED_MINUTES:g}), MAE at least {MIN_RELATIVE_MAE_IMPROVEMENT:.0%} lower than {COMPARISON_VERSION}, and a "
    f"paired mean |error| difference below zero by more than {STANDARD_ERRORS_REQUIRED:g} standard errors "
    f"(pre-registered in {PRE_REGISTRATION_COMMIT[:8]})."
)


@dataclass(frozen=True)
class ScoredPair:
    market: str
    minutes_change: float
    reference: NbaReplayCase
    candidate: NbaReplayCase


def fit_cases(found: Sequence[Situation], season: int) -> list[FitCase]:
    return [
        FitCase(
            actual_minutes=s.row.minutes, player_minutes=s.prior_minutes,
            team_delta=s.previous_game.team_delta, available_minutes=s.previous_game.available_minutes,
        )
        for s in found
        if s.row.season == season and s.row.minutes is not None and not s.previous_game.team_changed
    ]


def _case(s: Situation, market: str, projection: float, actual: float) -> NbaReplayCase:
    return NbaReplayCase(
        player_id=s.row.player_id, game_id=s.row.game_id, game_date=s.row.game_date, game_type=s.row.game_type,
        market=market, prior_minutes=s.prior_minutes, projection=projection, actual=actual,
    )


def score(found: Sequence[Situation], season: int, k: float, source: Source) -> list[ScoredPair]:
    pairs = []
    for s in found:
        if s.row.season != season:
            continue
        available = s.previous_game if source == "previous_game" else s.oracle
        for market in BACKTEST_MARKETS:
            actual = line_only_value(market, s.row.stats)
            result = project_minutes_line(s.prior, available, market, k)
            if actual is None or result.projection is None or result.reference is None:
                continue
            pairs.append(ScoredPair(
                market=market.value, minutes_change=result.minutes_change,
                reference=_case(s, market.value, result.reference, actual),
                candidate=_case(s, market.value, result.projection, actual),
            ))
    return pairs


def _paired_table(pairs: Sequence[ScoredPair], *, verdicts: bool) -> list[str]:
    lines = [
        f"  {'market':<26}{'all':>7}{'affected':>9}{'ref MAE':>9}{'new MAE':>9}{'change':>9}{'diff':>9}"
        f"{'SE':>7}{'ref bias':>9}{'new bias':>9}  {'verdict' if verdicts else ''}",
    ]
    for market in (m.value for m in BACKTEST_MARKETS):
        in_market = [p for p in pairs if p.market == market]
        affected = [p for p in in_market if is_affected(p.minutes_change)]
        if not affected:
            lines.append(f"  {market:<26}{len(in_market):>7}{0:>9}  no affected cases")
            continue
        diff = paired([p.reference for p in affected], [p.candidate for p in affected])
        ref = market_metrics([p.reference for p in affected])
        new = market_metrics([p.candidate for p in affected])
        lines.append(
            f"  {market:<26}{len(in_market):>7}{len(affected):>9}{diff.production_mae:>9.3f}{diff.variant_mae:>9.3f}"
            f"{diff.relative_mae_change * 100:>+8.2f}%{diff.mean_diff:>+9.3f}{diff.standard_error:>7.3f}"
            f"{ref.bias:>+9.2f}{new.bias:>+9.2f}  {development_verdict(diff) if verdicts else ''}".rstrip()
        )
    return lines


def _unaffected_check(pairs: Sequence[ScoredPair]) -> str:
    unaffected = [p for p in pairs if not is_affected(p.minutes_change)]
    unchanged = [p for p in unaffected if p.minutes_change == 0.0]
    same = all(p.candidate.projection == p.reference.projection for p in unchanged)
    return (
        f"Unaffected cases: {len(unaffected)} ({len(unchanged)} with no minutes change, "
        f"projection identical to {COMPARISON_VERSION}: {'yes' if same else 'NO'})"
    )


def report(k: float, fit_count: int, scored: Sequence[ScoredPair], oracle: Sequence[ScoredPair]) -> str:
    lines = [
        f"{CANDIDATE_VERSION} against {COMPARISON_VERSION}, development {DEVELOPMENT_SEASON}-"
        f"{(DEVELOPMENT_SEASON + 1) % 100:02d} (scored once; 2025-26 holdout unread)",
        "", RULE_TEXT, "",
        f"k = {k:.4f}, fitted on {fit_count} {FIT_SEASON}-{(FIT_SEASON + 1) % 100:02d} player-games with a "
        f"teammate change (previous-game availability)",
        "", "Previous-game availability (leakage-free): affected cases per market, the gate",
        *_paired_table(scored, verdicts=True),
        "", _unaffected_check(scored),
        "", "Oracle availability (diagnostic, leaks the game's own box score, no verdict)",
        *_paired_table(oracle, verdicts=False),
    ]
    passing = [
        market.value for market in BACKTEST_MARKETS
        if (affected := [p for p in scored if p.market == market.value and is_affected(p.minutes_change)])
        and development_verdict(paired([p.reference for p in affected], [p.candidate for p in affected])) == "adopt"
    ]
    lines += ["", f"Markets passing to 65b: {', '.join(passing) if passing else 'none: 65 closes at 65a'}"]
    return "\n".join(lines)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories.nba import get_projection_history, get_roster_history

    seasons = (FIT_SEASON, DEVELOPMENT_SEASON)
    async with SessionLocal() as db:
        history = await get_projection_history(db, seasons)
        roster = await get_roster_history(db, seasons)
    found = situations(history, roster, frozenset(seasons))
    fitted = fit_cases(found, FIT_SEASON)
    k = fit_rotation_coefficient(fitted)
    if not k_in_range(k):
        print(f"k = {k:.4f} is outside the pre-registered range: reject, 65 closes at 65a")
        return
    print(report(
        k, sum(1 for case in fitted if case.x != 0.0),
        score(found, DEVELOPMENT_SEASON, k, "previous_game"), score(found, DEVELOPMENT_SEASON, k, "oracle"),
    ))


def parse_season(parser: argparse.ArgumentParser, season: int) -> int:
    if season >= HOLDOUT_SEASON:
        parser.error(f"{season} is the holdout or later; {CANDIDATE_VERSION} is developed on {DEVELOPMENT_SEASON} only")
    if season != DEVELOPMENT_SEASON:
        parser.error(f"only --season {DEVELOPMENT_SEASON} is scored; k is fitted on {FIT_SEASON}")
    return season


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"Score {CANDIDATE_VERSION} on the development season")
    parser.add_argument("--season", type=int, required=True)
    parse_season(parser, parser.parse_args().season)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
