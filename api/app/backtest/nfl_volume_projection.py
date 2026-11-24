"""Score the 49a volume x efficiency projection against the reference arm, origin by origin.

Loads 2018-2025 once, then for each scored season fits both arms on the floor
season to the season before and scores that season's common cohort on CRPS
(`score_origin`). Each market gets the verdict of the rule pre-registered in
commit 5b953125. There is deliberately no arm, grid or season option: the run
is the one the rule names, and a different run would be a different rule.

It reads and prints. Nothing is stored, and nothing feeds a projection.

Run from api/: python -m app.backtest.nfl_volume_projection
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence

from app.core.nfl_volume_backtest import (
    CALIBRATION_MAX_BIN_GAP,
    CALIBRATION_MAX_ECE,
    MIN_SEASON_CASES,
    MIN_SEASONS_WON,
    SCORED_SEASONS,
    SE_MULTIPLE,
    SHARE_BELOW_RANGE,
    MarketVerdict,
    OriginScore,
    ScoredPair,
    VolumeHistory,
    build_cases,
    score_origin,
    verdict,
)
from app.core.nfl_volume_projection import MARKET_SPECS, VOLUME_FIRST_HISTORY_SEASON

LAST_HISTORY_SEASON = SCORED_SEASONS[-1]
PRE_REGISTRATION_COMMIT = "5b9531259278d93de1ba70b010cfe266c46cb875"
MARKETS = tuple(sorted(MARKET_SPECS))

RULE_TEXT = "\n".join([
    f"Pre-registered rule (commit {PRE_REGISTRATION_COMMIT[:8]}, 2026-10-30). A market adopts only if:",
    f"  1. cases: >= {MIN_SEASON_CASES} common-cohort cases in each of {SCORED_SEASONS[0]}-{SCORED_SEASONS[-1]};",
    f"  2. crps: the pooled paired CRPS difference (volume minus reference) is below zero by more than "
    f"{SE_MULTIPLE:g} SE, clustered by game;",
    f"  3. seasons: volume's mean CRPS is lower in at least {MIN_SEASONS_WON} of {len(SCORED_SEASONS)} seasons;",
    f"  4. calibration: volume's P(over) at the common lines has ECE <= {CALIBRATION_MAX_ECE:g} "
    f"and no bin of 200+ pairs off by more than {CALIBRATION_MAX_BIN_GAP:g};",
    f"  5. median: the share of actuals below volume's median (ties count half) lies within "
    f"{SHARE_BELOW_RANGE[0]:.2f}-{SHARE_BELOW_RANGE[1]:.2f}.",
    "Otherwise reject, or insufficient when clause 1 fails. Verdicts are final for nfl-volume-v1.",
])

CLOSING_LINES_NOTE = (
    "Team volume uses each game's closing spread and total; production will use pre-kickoff lines, "
    "so this backtest flatters the team-volume term slightly."
)


def _num(value: float | None, width: int, digits: int, sign: bool = False) -> str:
    if value is None:
        return f"{'--':>{width}}"
    return f"{value:>+{width}.{digits}f}" if sign else f"{value:>{width}.{digits}f}"


def _origin_table(origins: Sequence[OriginScore]) -> list[str]:
    lines = [
        f"Origins: each fitted on {VOLUME_FIRST_HISTORY_SEASON} to the season before, then scored",
        f"  {'season':<8}{'pairs':>7}{'k_share':>9}  k_rate",
    ]
    for origin in origins:
        params = origin.volume_fit.params
        rates = ", ".join(f"{market}={k:g}" for market, k in sorted(params.k_rate.items()))
        lines.append(f"  {origin.season:<8}{len(origin.pairs):>7}{params.k_share:>9g}  {rates}")
    return lines


def _exclusion_table(origins: Sequence[OriginScore]) -> list[str]:
    lines = [
        "Excluded from the common cohort (case-market forecasts; rookies show as no volume forecast)",
        f"  {'season':<8}{'market':<22}{'reason':<24}{'n':>7}",
    ]
    rows = [
        (origin.season, market, reason, n)
        for origin in origins for (market, reason), n in sorted(origin.excluded.items())
    ]
    if not rows:
        return [*lines, "  -- none --"]
    return [*lines, *(f"  {season:<8}{market:<22}{reason:<24}{n:>7}" for season, market, reason, n in rows)]


def _cases_table(verdicts: Sequence[MarketVerdict]) -> list[str]:
    seasons = "".join(f"{season:>8}" for season in SCORED_SEASONS)
    lines = ["Common-cohort cases by season", f"  {'market':<22}{seasons}{'pooled':>9}"]
    for row in verdicts:
        counts = "".join(f"{row.cases_by_season.get(season, 0):>8}" for season in SCORED_SEASONS)
        lines.append(f"  {row.market:<22}{counts}{sum(row.cases_by_season.values()):>9}")
    return lines


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _season_winner(pairs: Sequence[ScoredPair]) -> str:
    """V when volume's mean CRPS is lower that season, R when it is not, -- with no pairs."""
    if not pairs:
        return "--"
    return "V" if sum(p.volume_crps for p in pairs) < sum(p.reference_crps for p in pairs) else "R"


def _crps_table(verdicts: Sequence[MarketVerdict], pairs: Sequence[ScoredPair]) -> list[str]:
    seasons = "".join(f"{season:>6}" for season in SCORED_SEASONS)
    lines = [
        "Mean CRPS, paired on player, game and market (diff = volume minus reference; SE clustered by game)",
        f"  {'market':<22}{'n':>7}{'volume':>9}{'ref':>9}{'diff':>9}{'SE':>8}{'won':>5}{seasons}",
    ]
    for row in verdicts:
        own = [pair for pair in pairs if pair.market == row.market]
        winners = "".join(
            f"{_season_winner([p for p in own if p.season == season]):>6}" for season in SCORED_SEASONS
        )
        won = f"{row.seasons_won}/{len(SCORED_SEASONS)}" if row.mean_difference is not None else "--"
        lines.append(
            f"  {row.market:<22}{len(own):>7}{_num(_mean([p.volume_crps for p in own]), 9, 3)}"
            f"{_num(_mean([p.reference_crps for p in own]), 9, 3)}{_num(row.mean_difference, 9, 3, sign=True)}"
            f"{_num(row.standard_error, 8, 3)}{won:>5}{winners}"
        )
    return lines


def _calibration_table(verdicts: Sequence[MarketVerdict]) -> list[str]:
    lines = [
        "Volume calibration: P(over) at the reference arm's synthetic lines, and the median",
        f"  {'market':<22}{'ECE':>8}{'worst bin':>11}{'below median':>14}",
    ]
    for row in verdicts:
        lines.append(
            f"  {row.market:<22}{_num(row.ece, 8, 4)}{_num(row.worst_gap, 11, 4)}{_num(row.share_below, 14, 3)}"
        )
    return lines


def verdict_wording(row: MarketVerdict) -> str:
    if row.verdict == "adopt":
        return "ADOPT nfl-volume-v1"
    if row.verdict == "insufficient":
        return f"INSUFFICIENT (fewer than {MIN_SEASON_CASES} cases in a season; failed: cases)"
    return f"REJECT (failed: {', '.join(row.failed)})"


def report(origins: Sequence[OriginScore], verdicts: Sequence[MarketVerdict]) -> str:
    pairs = [pair for origin in origins for pair in origin.pairs]
    lines = [
        f"NFL volume x efficiency backtest, rolling origin {SCORED_SEASONS[0]}-{SCORED_SEASONS[-1]} "
        f"(candidate nfl-volume-v1 against the v4 core reference)",
        "",
        RULE_TEXT,
        "",
        CLOSING_LINES_NOTE,
        "",
        *_origin_table(origins),
        "",
        *_exclusion_table(origins),
        "",
        *_cases_table(verdicts),
        "",
        *_crps_table(verdicts, pairs),
        "",
        *_calibration_table(verdicts),
        "",
        "Verdicts",
        *(f"  {row.market:<22}{verdict_wording(row)}" for row in verdicts),
    ]
    return "\n".join(lines)


def coverage_line(history: VolumeHistory, case_count: int) -> str:
    return (
        f"Loaded {VOLUME_FIRST_HISTORY_SEASON}-{LAST_HISTORY_SEASON}: {len(history.player_games)} player-games, "
        f"{len(history.team_games)} team-games, {case_count} cases with closing lines and team attempts."
    )


def judge(origins: Sequence[OriginScore]) -> list[MarketVerdict]:
    pairs = [pair for origin in origins for pair in origin.pairs]
    return [verdict(market, pairs) for market in MARKETS]


async def run() -> str:
    from app.db.pool import SessionLocal
    from app.repositories.nfl_volume import get_volume_history

    started = time.monotonic()
    async with SessionLocal() as db:
        history = await get_volume_history(db, VOLUME_FIRST_HISTORY_SEASON, LAST_HISTORY_SEASON)
    cases = build_cases(history)
    print(coverage_line(history, len(cases)), file=sys.stderr, flush=True)
    origins = []
    for season in SCORED_SEASONS:
        origins.append(score_origin(cases, season))
        print(f"Scored {season} after {time.monotonic() - started:.0f}s", file=sys.stderr, flush=True)
    elapsed = f"Elapsed {time.monotonic() - started:.0f}s."
    return "\n".join([coverage_line(history, len(cases)), elapsed, "", report(origins, judge(origins))])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score the 49a NFL volume projection against the reference arm over the "
            f"{SCORED_SEASONS[0]}-{SCORED_SEASONS[-1]} origins, under the pre-registered rule. "
            "Read-only; takes no options because the run is fixed by the rule."
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
