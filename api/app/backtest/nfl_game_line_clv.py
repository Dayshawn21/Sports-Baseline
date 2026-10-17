"""Does the NFL closing line move toward the game model from the stored entry line? (item 28)

Read-only. Replays the pinned `nfl-elo-v1` spread and `NFL_SCORING_V1` total,
grades them against each game's earliest stored in-window line, and applies the
pre-registered rule in `app/core/nfl_game_line_clv.py`.

Run from api/: python -m app.backtest.nfl_game_line_clv [--season 2026]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence

from app.core.nfl_elo import NFL_ELO_MODEL_VERSION, NFL_ELO_V1, NflEloGame, replay as replay_elo
from app.core.nfl_game_line_clv import (
    PICK_THRESHOLD, VERDICT_PICKS, ClvMarketGrade, ClvPick, ClvSummary, GameModel, summarize, verdict,
)
from app.core.nfl_game_lines import game_model_line
from app.core.nfl_scoring_ratings import NFL_SCORING_V1, replay as replay_scoring

EARLY_WEEKS = 4


def game_models(games: Sequence[NflEloGame]) -> dict[str, GameModel]:
    """The pinned model line for every game, replayed from `get_elo_games` order."""
    home: dict[str, float] = {}
    away: dict[str, float] = {}
    for row in replay_elo(games, NFL_ELO_V1):
        (home if row.is_home else away)[row.game_key] = row.elo_pre
    totals = {row.game_key: row.expected_total for row in replay_scoring(games, NFL_SCORING_V1)}
    return {
        key: GameModel(game_model_line(home[key], away[key], totals[key], None, None).home_spread, totals[key])
        for key in home
    }


def _signed(value: float | None, places: int = 2) -> str:
    return "-" if value is None else f"{value:+.{places}f}"


def _row(label: str, summary: ClvSummary) -> str:
    se = "-" if summary.standard_error is None else f"{summary.standard_error:.2f}"
    record = summary.record
    return (
        f"  {label:<8}{summary.n:>6}{_signed(summary.mean_clv):>10}{se:>7}"
        f"   {summary.toward}/{summary.away}/{summary.flat:<10}"
        f"{record.hits}-{record.misses}-{record.pushes}"
    )


def _verdict_line(picks: Sequence[ClvPick]) -> str:
    result = verdict(picks)
    if not result.weeks:
        weeks = "no weeks"
    elif len(result.weeks) == 1:
        weeks = f"week {result.weeks[0]}"
    else:
        weeks = f"weeks {result.weeks[0]}-{result.weeks[-1]}"
    if result.verdict == "accruing":
        return f"  Verdict: accruing, {result.summary.n} of {VERDICT_PICKS} picks ({weeks})"
    summary = result.summary
    return (
        f"  Verdict: {result.verdict} ({weeks}, {summary.n} picks): "
        f"mean CLV {_signed(summary.mean_clv)}, SE {summary.standard_error:.2f}"
    )


def market_section(grade: ClvMarketGrade) -> list[str]:
    excluded = ", ".join(f"{reason} {n}" for reason, n in sorted(grade.excluded.items())) or "none"
    lead = (
        "-" if grade.median_lead_hours is None
        else f"median {grade.median_lead_hours:.1f}h, min {min(grade.lead_hours):.1f}h"
    )
    early = [pick for pick in grade.picks if pick.week <= EARLY_WEEKS]
    late = [pick for pick in grade.picks if pick.week > EARLY_WEEKS]
    return [
        grade.market.upper(),
        f"  games graded {grade.graded}, picks {len(grade.picks)} (|model - entry| >= {PICK_THRESHOLD})",
        f"  excluded: {excluded}",
        f"  entry line before kickoff: {lead}",
        "  set      picks  mean CLV     SE   toward/away/flat  W-L-P vs entry",
        _row("all", summarize(grade.picks)),
        _row(f"wk 1-{EARLY_WEEKS}", summarize(early)),
        _row(f"wk {EARLY_WEEKS + 1}+", summarize(late)),
        _verdict_line(grade.picks),
    ]


def report(season: int, grades: Sequence[ClvMarketGrade]) -> str:
    lines = [
        f"NFL game-line CLV, {season} ({NFL_ELO_MODEL_VERSION} spread, NFL_SCORING_V1 total; rule fixed 2026-09-26)",
        "CLV = points the close moved toward the model from the entry line. Pass needs mean CLV - 2 SE > 0.",
    ]
    for grade in grades:
        lines += ["", *market_section(grade)]
    return "\n".join(lines)


async def _main(season: int) -> None:
    from app.db.pool import SessionLocal
    from app.services.nfl.track_record import load_clv_grades

    async with SessionLocal() as db:
        grades = await load_clv_grades(db, season)
    print(report(season, grades))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Grade the NFL game model against entry-to-close line movement")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main(args.season))
