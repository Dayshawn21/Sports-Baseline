import asyncio
import math
import random
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest

from app.backtest import nfl_volume_anchor as harness
from app.core.nfl_volume_anchor import ANCHOR_MIN_FIT_PAIRS, AnchorFit, anchored_probability
from app.core.nfl_volume_backtest import VolumeCase, VolumeHistory
from app.core.nfl_volume_projection import GameContext, PlayerGame
from app.repositories.nfl_volume_anchor import AnchorLine

API_ROOT = Path(__file__).resolve().parents[1]
FETCHED = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
GAME = GameContext(season=2026, week=5, implied_team_total=24.0, implied_margin=2.0)


def _past(week: int) -> PlayerGame:
    return PlayerGame(
        2026, week, {"targets": 8.0, "receptions": 5.0, "receiving_yards": 60.0},
        team_pass_attempts=34.0, team_rush_attempts=26.0,
    )


def _case(player_id: int = 7, game_id: int = 50, position: str = "WR", history: tuple[PlayerGame, ...] | None = None) -> VolumeCase:
    past = history if history is not None else (_past(1), _past(2), _past(3), _past(4))
    return VolumeCase(player_id, game_id, 2026, position, GAME, past, {"receptions": 5.0}, _past(5))


def _line(line: float = 4.5, receptions: float | None = 6.0, player_id: int = 7, game_id: int = 50, week: int = 5) -> AnchorLine:
    return AnchorLine(
        line_id=player_id * 1000 + game_id, player_id=player_id, game_id=game_id, season=2026, week=week,
        team_id=11, is_home=True, position="WR", line=line, fetched_at=FETCHED, receptions=receptions,
    )


def test_a_settled_line_becomes_one_pair_with_its_outcome() -> None:
    pairs, excluded = harness.build_pairs([_line(4.5, 6.0), _line(4.5, 3.0, player_id=8)], [_case(), _case(player_id=8)])

    assert [pair.went_over for pair in pairs] == [True, False]
    assert all(0.0 < pair.q_vol < 1.0 and pair.p_push == 0.0 for pair in pairs)
    assert not excluded


def test_every_other_line_is_counted_by_reason_and_never_becomes_a_pair() -> None:
    lines = [
        _line(receptions=None, player_id=1),
        _line(player_id=2),
        _line(4.5, 6.0, player_id=3),
        _line(5.0, 5.0, player_id=4),
    ]
    cases = [_case(player_id=3), _case(player_id=4), _case(player_id=5, history=())]
    lines.append(_line(4.5, 6.0, player_id=5))
    pairs, excluded = harness.build_pairs(lines, cases)

    assert len(pairs) == 1 and pairs[0].line_id == lines[2].line_id
    assert dict(excluded) == {harness.UNSETTLED: 1, harness.NO_CASE: 1, harness.PUSH: 1, harness.NO_PROJECTION: 1}


def test_a_non_push_result_on_an_integer_line_keeps_the_push_mass() -> None:
    pairs, _ = harness.build_pairs([_line(5.0, 7.0)], [_case()])
    assert pairs[0].p_push > 0.0


def _fit(a: float = -0.1, b: float = 0.6) -> AnchorFit:
    return AnchorFit(a, b, 0.05, 0.08, 500)


def _pairs(n: int = 500, seed: int = 4) -> list[harness.AnchorPair]:
    rng = random.Random(seed)
    pairs = []
    for index in range(n):
        q_vol = rng.uniform(0.2, 0.8)
        pairs.append(harness.AnchorPair(index, 1 + index % 8, index, q_vol, 0.0, rng.random() < q_vol))
    return pairs


def test_diagnostics_match_hand_computed_losses() -> None:
    pairs = [harness.AnchorPair(1, 1, 1, 0.8, 0.0, True), harness.AnchorPair(2, 1, 2, 0.8, 0.0, False)]
    stats = harness.diagnostics(pairs, _fit(0.0, 1.0))

    assert stats.raw_log_loss == pytest.approx(-(math.log(0.8) + math.log(0.2)) / 2)
    assert stats.blend_log_loss == pytest.approx(stats.raw_log_loss)
    assert stats.half_log_loss == pytest.approx(math.log(2.0))
    assert stats.over_rate == 0.5 and (stats.picks, stats.pick_hits) == (2, 1)


def test_picks_use_27i_margin_over_the_standard_break_even() -> None:
    near_even = [harness.AnchorPair(1, 1, 1, 0.5, 0.0, True)]
    assert harness.diagnostics(near_even, _fit(0.0, 1.0)).picks == 0


def test_calibration_bins_are_equal_count_and_ordered() -> None:
    rows = harness.calibration(_pairs(500), _fit())

    assert [n for n, _, _ in rows] == [100] * harness.CALIBRATION_BINS
    assert [mean for _, mean, _ in rows] == sorted(mean for _, mean, _ in rows)


def test_report_shows_every_section_and_labels_the_fit_in_sample() -> None:
    lines = [_line(receptions=None, week=8), _line(week=2)]
    from collections import Counter
    text = harness.report(lines, _pairs(), Counter({harness.UNSETTLED: 1}), _fit())

    assert harness.IN_SAMPLE in text
    for needle in (
        "standard lines", f"minimum {ANCHOR_MIN_FIT_PAIRS}", "Pairs by week: 1=", "Unsettled lines by week:",
        "8=1", "Excluded lines", harness.UNSETTLED, "a = -0.1000 (SE 0.0500)", "b = +0.6000 (SE 0.0800)",
        "blend", "raw volume", "constant 0.5", "Observed over rate", "Picks clearing break-even", "Calibration",
    ):
        assert needle in text
    assert not re.search(r"\b(adopt|reject)\b", text, re.IGNORECASE)


def test_anchored_probability_is_what_the_diagnostics_score() -> None:
    pair = harness.AnchorPair(1, 1, 1, 0.7, 0.1, True)
    over, under = anchored_probability(0.7, 0.1, -0.1, 0.6)
    assert harness.diagnostics([pair, harness.AnchorPair(2, 1, 2, 0.7, 0.1, False)], _fit()).blend_log_loss == pytest.approx(
        -(math.log(over / (over + under)) + math.log(under / (over + under))) / 2
    )


def test_the_cli_takes_no_options() -> None:
    with pytest.raises(SystemExit) as exit:
        harness.parse_args(["--season", "2025"])
    assert exit.value.code == 2


def test_help_exits_before_any_database_import() -> None:
    probe = (
        "import runpy, sys\n"
        "sys.argv = ['nfl_volume_anchor', '--help']\n"
        "try:\n"
        "    runpy.run_module('app.backtest.nfl_volume_anchor', run_name='__main__')\n"
        "except SystemExit as exit:\n"
        "    assert exit.code == 0, exit.code\n"
        "loaded = [m for m in sys.modules if m.startswith(('app.db', 'app.repositories', 'app.config', 'sqlalchemy'))]\n"
        "print('LOADED', loaded)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=API_ROOT, capture_output=True, text=True, timeout=120, check=True,
    )

    assert "pre-registered rule" in result.stdout
    assert "LOADED []" in result.stdout


@pytest.mark.parametrize("path", ["app/backtest/nfl_volume_anchor.py", "app/repositories/nfl_volume_anchor.py"])
def test_the_run_issues_no_writes(path: str) -> None:
    source = (API_ROOT / path).read_text(encoding="utf-8")

    assert not re.search(r"\b(INSERT|UPDATE|DELETE|UPSERT|TRUNCATE)\b", source, re.IGNORECASE)
    assert ".commit(" not in source
    assert not re.search(r"\b(db|session)\.(add|add_all|merge|flush|delete)\(", source)


def test_run_loads_the_fixed_window_and_reports(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[tuple[int, ...]] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    async def get_anchor_lines(db: FakeSession, season: int, first_week: int, last_week: int) -> list[AnchorLine]:
        loads.append((season, first_week, last_week))
        return []

    async def get_anchor_history(db: FakeSession, season: int) -> VolumeHistory:
        loads.append((season,))
        return VolumeHistory([], [])

    pool = ModuleType("app.db.pool")
    pool.SessionLocal = FakeSession  # type: ignore[attr-defined]
    repository = ModuleType("app.repositories.nfl_volume_anchor")
    repository.get_anchor_lines = get_anchor_lines  # type: ignore[attr-defined]
    repository.get_anchor_history = get_anchor_history  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.db.pool", pool)
    monkeypatch.setitem(sys.modules, "app.repositories.nfl_volume_anchor", repository)

    with pytest.raises(ValueError, match="at least 400"):
        asyncio.run(harness.run())
    assert loads == [(2026, 1, 8), (2026,)]
