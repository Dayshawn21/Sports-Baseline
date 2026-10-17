"""17c's claim, end to end: a new sport supplies a config, its data reads and a projection, nothing else.

The toy sport below runs league selection, freezing and the 27i verdict through
the shared modules only. A subprocess repeats the run in a fresh interpreter and
proves no NFL module was loaded to do it.
"""
import asyncio
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.prop_predictions import FreezableGame, PropPredictionRow
from app.core.prop_ranking_check import FrozenLine, slice_results
from app.core.prop_ranking_report import ranking_report
from app.core.prop_ranking_rule import MIN_PICKS
from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig, board_leagues
from app.services import prop_predictions
from app.services.prop_ranking import build_ranking_record, load_ranking_calls

NOW = datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
TOY = SportPropConfig(
    code="toy", league_prefix="TOY", segment_suffixes={"1H": "first_half"},
    board_segments=frozenset({FULL_GAME_SEGMENT}), market_aliases={"points": "points"}, period_label="round",
)
NFL_MODULE_PREFIXES = ("app.nfl", "app.core.nfl_", "app.repositories.nfl", "app.services.nfl")


def _row(line_id: int) -> PropPredictionRow:
    return PropPredictionRow(line_id, "toy-v1", "toy-pover-v1", 22.0, 0.7, 0.3, 0.5, [], {"odds_type": "standard"}, NOW)


class ToySource:
    """Everything sport-specific, in memory: two games to freeze and four settled rounds to grade."""

    config = TOY
    model_version = "toy-v1"
    over_probability_version = "toy-pover-v1"

    async def current_period(self, db, now):
        return (2026, 5)

    async def freezable_games(self, db, season, period, now):
        return [
            FreezableGame(now + timedelta(hours=1), [_row(1), _row(2)]),
            FreezableGame(now - timedelta(minutes=5), [_row(3)]),
        ]

    async def frozen_lines(self, db, season):
        # MIN_PICKS standard overs at p_over 0.7 over rounds 1-4, nine in ten hitting.
        return [
            FrozenLine(i, 1 + i % 4, i, 1000 + i, "points", "standard", "over" if i % 10 else "under",
                       0.7, 0.3, "toy-v1", "toy-pover-v1")
            for i in range(MIN_PICKS)
        ] + [FrozenLine(MIN_PICKS, 5, 1, 1, "points", "standard", "over", 0.7, 0.3, "toy-v1", "toy-pover-v1")]

    async def finished_periods(self, db, season):
        return {1, 2, 3, 4}

    async def frozen_coverage(self, db, season):
        return {}


class _Db:
    async def commit(self) -> None:
        return None


def run_pipeline() -> dict[str, object]:
    leagues = [{"id": 1, "attributes": {"name": "TOY"}}, {"id": 2, "attributes": {"name": "TOY1H"}},
               {"id": 3, "attributes": {"name": "NFL"}}]
    stored: list[int] = []

    async def insert(db, sport, rows):
        assert sport == "toy"
        stored.extend(row.prop_line_id for row in rows)
        return len(rows)

    real_insert = prop_predictions.sport_props.insert_prop_predictions
    prop_predictions.sport_props.insert_prop_predictions = insert
    try:
        frozen = asyncio.run(prop_predictions.freeze_current_period(_Db(), ToySource(), NOW, dry_run=False))
    finally:
        prop_predictions.sport_props.insert_prop_predictions = real_insert
    loaded = asyncio.run(load_ranking_calls(_Db(), ToySource(), 2026))
    check = slice_results(loaded.calls)
    verdict = check.slices[("standard", "over")]
    record = build_ranking_record(loaded, 2026, NOW, ToySource.model_version, ToySource.over_probability_version)
    report = ranking_report(
        "TOY", 2026, check, loaded.frozen_rows, loaded.exclusions, loaded.coverage,
        ToySource.model_version, ToySource.over_probability_version, coverage_label="toy lines",
    )
    return {
        "board": board_leagues(leagues, TOY),
        "stored": stored,
        "skipped": dict(frozen.counts) if frozen else None,
        "exclusions": dict(loaded.exclusions),
        "verdict": (verdict.verdict, verdict.n, verdict.periods, verdict.hits),
        "record": (record.slices[0].verdict, record.slices[0].signal, record.last_settled_week, record.model_version),
        "report_head": report.splitlines()[0],
    }


def test_a_toy_sport_runs_the_whole_pipeline() -> None:
    result = run_pipeline()

    assert result["board"] == [(1, "TOY", "full_game")]
    assert result["stored"] == [1, 2]
    assert result["skipped"] == {"kicked_off": 1, "frozen": 2}
    assert result["exclusions"] == {"round_not_finished": 1}
    assert result["verdict"] == ("adopt", MIN_PICKS, 4, 180)
    assert result["record"] == ("adopt", "positive", 4, "toy-v1")
    assert result["report_head"] == "TOY forward ranking check, 2026 (model toy-v1, P(over) toy-pover-v1)"


def test_the_toy_sport_loads_no_nfl_module() -> None:
    script = (
        "import sys\n"
        "from tests.test_sport_props_pipeline import NFL_MODULE_PREFIXES, run_pipeline\n"
        "assert run_pipeline()['verdict'][0] == 'adopt'\n"
        "print(sorted(m for m in sys.modules if m.startswith(NFL_MODULE_PREFIXES)))\n"
    )
    api_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-c", script], cwd=api_root, capture_output=True, text=True, timeout=120, check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "[]"
