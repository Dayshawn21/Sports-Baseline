import asyncio
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.backtest import nfl_volume_projection as harness
from app.core.nfl_volume_backtest import (
    SCORED_SEASONS,
    MarketVerdict,
    OriginScore,
    ReferenceFit,
    ScoredPair,
    VolumeFit,
    VolumeHistory,
)
from app.core.nfl_volume_projection import TeamVolumeFit, VolumeParameters

API_ROOT = Path(__file__).resolve().parents[1]


def _params(k_share: float, k_rate: float) -> VolumeParameters:
    return VolumeParameters(
        pass_volume=TeamVolumeFit(30.0, 0.1, -0.2),
        rush_volume=TeamVolumeFit(25.0, 0.1, 0.3),
        previous_season_weight=0.6,
        k_share=k_share,
        k_rate={"receptions": k_rate, "rushing_yards": 2 * k_rate},
        position_share={},
        position_rate={},
        dispersion={},
        yards_sd={},
    )


def _pair(season: int, game_id: int, volume: float, reference: float, market: str = "receptions") -> ScoredPair:
    return ScoredPair(game_id, game_id, market, "WR", season, volume, reference, (), 0.5)


def _origin(season: int, volume: float, excluded: dict[tuple[str, str], int] | None = None) -> OriginScore:
    pairs = (_pair(season, 10 * season, volume, 1.0), _pair(season, 10 * season + 1, volume, 1.0))
    return OriginScore(
        season, pairs, excluded or {}, VolumeFit(_params(2.0, 25.0), {}, {}), ReferenceFit({}, {}),
    )


def _verdict(market: str, verdict: str, failed: tuple[str, ...] = ()) -> MarketVerdict:
    if verdict == "insufficient":
        counts = {season: 120 for season in SCORED_SEASONS}
        return MarketVerdict(market, counts, None, None, 0, None, None, None, ("cases",), "insufficient")
    counts = {season: 400 + season - SCORED_SEASONS[0] for season in SCORED_SEASONS}
    return MarketVerdict(market, counts, -0.0412, 0.0104, 4, 0.0123, None, 0.512, failed, verdict)


def _report() -> str:
    origins = [
        _origin(2021, 0.9, {("receptions", "no volume forecast"): 37, ("rushing_yards", "no reference forecast"): 3}),
        _origin(2022, 1.1),
    ]
    verdicts = [
        _verdict("receptions", "adopt"),
        _verdict("receiving_yards", "reject", ("crps", "median")),
        _verdict("passing_yards", "insufficient"),
    ]
    return harness.report(origins, verdicts)


def _line(text: str, start: str) -> list[str]:
    return next(line for line in text.splitlines() if line.startswith(start)).split()


def test_report_states_the_rule_hash_and_closing_line_caveat() -> None:
    text = _report()

    assert "commit 5b953125" in text
    for clause in ("1. cases: >= 300", "2. crps:", "by more than 2 SE", "3. seasons: volume's mean CRPS is lower in at least 4 of 5",
                   "4. calibration:", "ECE <= 0.02", "more than 0.05", "5. median:", "0.47-0.53"):
        assert clause in text
    assert "closing spread and total" in text


def test_report_shows_each_origins_chosen_k() -> None:
    text = _report()

    assert "k_share" in text and "k_rate" in text
    assert _line(text, "  2021    ") == ["2021", "2", "2", "receptions=25,", "rushing_yards=50"]


def test_report_lists_exclusions_with_rookies_as_no_volume_forecast() -> None:
    text = _report()

    assert "rookies show as no volume forecast" in text
    assert re.search(r"2021\s+receptions\s+no volume forecast\s+37", text)
    assert re.search(r"2021\s+rushing_yards\s+no reference forecast\s+3", text)


def test_report_shows_cases_by_season_and_pooled() -> None:
    cases = _report().split("Common-cohort cases by season")[1].split("Mean CRPS")[0]

    assert _line(cases, "  market") == ["market", *map(str, SCORED_SEASONS), "pooled"]
    assert _line(cases, "  receptions") == ["receptions", "400", "401", "402", "403", "404", "2010"]
    assert _line(cases, "  passing_yards") == ["passing_yards", "120", "120", "120", "120", "120", "600"]


def test_report_shows_crps_both_arms_paired_difference_se_and_season_wins() -> None:
    text = _report()
    crps = text.split("Mean CRPS")[1].split("Volume calibration")[0]

    assert "SE clustered by game" in crps
    assert _line(crps, "  market").count("volume") == 1
    # Volume beats reference in 2021 (0.9 < 1.0) and loses in 2022; later seasons have no pairs.
    assert _line(crps, "  receptions") == [
        "receptions", "4", "1.000", "1.000", "-0.041", "0.010", "4/5", "V", "R", "--", "--", "--",
    ]
    assert _line(crps, "  passing_yards") == [
        "passing_yards", "0", "--", "--", "--", "--", "--", "--", "--", "--", "--", "--",
    ]


def test_report_shows_ece_worst_bin_and_median_share() -> None:
    text = _report()
    calibration = text.split("Volume calibration")[1].split("Verdicts")[0]

    assert "ECE" in calibration and "worst bin" in calibration and "below median" in calibration
    assert _line(calibration, "  receptions") == ["receptions", "0.0123", "--", "0.512"]
    assert _line(calibration, "  passing_yards") == ["passing_yards", "--", "--", "--"]


def test_report_words_each_verdict_with_its_failed_clauses() -> None:
    verdicts = _report().split("Verdicts")[-1]

    assert re.search(r"receptions\s+ADOPT nfl-volume-v1", verdicts)
    assert re.search(r"receiving_yards\s+REJECT \(failed: crps, median\)", verdicts)
    assert re.search(r"passing_yards\s+INSUFFICIENT \(fewer than 300 cases in a season; failed: cases\)", verdicts)


def test_report_with_no_exclusions_says_none() -> None:
    assert "-- none --" in harness.report([_origin(2021, 0.9)], [_verdict("receptions", "adopt")])


def test_judge_gives_every_market_a_verdict() -> None:
    verdicts = harness.judge([_origin(2021, 0.9)])

    assert [row.market for row in verdicts] == list(harness.MARKETS)
    assert len(harness.MARKETS) == 7
    assert all(row.verdict == "insufficient" for row in verdicts)


def test_cli_takes_no_options() -> None:
    with pytest.raises(SystemExit) as exit:
        harness.parse_args(["--season", "2025"])

    assert exit.value.code == 2


def test_help_exits_before_any_database_import() -> None:
    probe = (
        "import runpy, sys\n"
        "sys.argv = ['nfl_volume_projection', '--help']\n"
        "try:\n"
        "    runpy.run_module('app.backtest.nfl_volume_projection', run_name='__main__')\n"
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


@pytest.mark.parametrize("path", ["app/backtest/nfl_volume_projection.py", "app/repositories/nfl_volume.py"])
def test_the_run_issues_no_writes(path: str) -> None:
    source = (API_ROOT / path).read_text(encoding="utf-8")

    assert not re.search(r"\b(INSERT|UPDATE|DELETE|UPSERT|TRUNCATE)\b", source, re.IGNORECASE)
    assert ".commit(" not in source
    assert not re.search(r"\b(db|session)\.(add|add_all|merge|flush|delete)\(", source)


def test_run_loads_history_once_and_scores_every_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[tuple[int, int]] = []
    scored: list[int] = []

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

    async def get_volume_history(db: FakeSession, first_season: int, last_season: int) -> VolumeHistory:
        loads.append((first_season, last_season))
        return VolumeHistory([], [])

    def score_origin(cases: list[object], season: int) -> OriginScore:
        scored.append(season)
        return _origin(season, 0.9)

    pool = ModuleType("app.db.pool")
    pool.SessionLocal = FakeSession  # type: ignore[attr-defined]
    repository = ModuleType("app.repositories.nfl_volume")
    repository.get_volume_history = get_volume_history  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.db.pool", pool)
    monkeypatch.setitem(sys.modules, "app.repositories.nfl_volume", repository)
    monkeypatch.setattr(harness, "score_origin", score_origin)

    text = asyncio.run(harness.run())

    assert loads == [(2018, 2025)]
    assert scored == list(SCORED_SEASONS)
    assert text.startswith("Loaded 2018-2025: 0 player-games, 0 team-games, 0 cases")
    assert "Elapsed" in text and "Verdicts" in text
