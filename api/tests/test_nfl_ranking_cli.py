from __future__ import annotations

import asyncio
import sys
from collections import Counter
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest import nfl_ranking_check as cli
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION as V4
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION as TARGETS
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION as VOLUME
from app.core.prop_ranking_check import slice_results
from app.core.prop_ranking_rule import FrozenCall
from app.db import pool
from app.services.nfl import track_record, volume_ranking
from app.services.prop_ranking import RankingCalls
from tests.helpers.nfl_volume_ranking_service import _passing_sample


def _inputs(model: str) -> RankingCalls:
    calls = [FrozenCall(
        line_id=i, period=3, player_id=i, game_id=50, market="receiving_targets" if model == TARGETS else "receptions",
        odds_type="standard", outcome="over", p_over=None if model == TARGETS else 0.7,
        p_under=None if model == TARGETS else 0.3,
    ) for i in range(2 if model == TARGETS else 1)]
    return RankingCalls(calls, Counter(), 8 if model == TARGETS else 4, {3: (10, 2 if model == TARGETS else 1)}, {3})


def _volume_inputs() -> volume_ranking.VolumeInputs:
    lines = _passing_sample()
    calls = [
        FrozenCall(
            line_id=item.frozen.line_id, period=item.frozen.period, player_id=item.frozen.player_id,
            game_id=item.frozen.game_id, market="receptions", odds_type="standard",
            p_over=item.frozen.p_over, p_under=item.frozen.p_under, outcome="over" if item.frozen.outcome == "over" else "under",
        )
        for item in lines
    ]
    finished = {9, 10, 11, 12}
    return volume_ranking.VolumeInputs(
        RankingCalls(calls, Counter(), len(lines), {9: (115, 50)}, finished),
        volume_ranking.log_loss_rows(lines, finished),
        frozenset({"standard"}),
    )


def _stub_loaders(monkeypatch: pytest.MonkeyPatch, fail_model: str | None = None) -> list[str]:
    calls: list[str] = []

    class Session:
        async def __aenter__(self) -> AsyncSession:
            calls.append("session_enter")
            return cast(AsyncSession, self)

        async def __aexit__(self, *args: object) -> None:
            calls.append("session_exit")

    async def load(db: AsyncSession, season: int, model_version: str = V4) -> RankingCalls:
        assert season == 2026
        calls.append(model_version)
        if model_version == fail_model:
            raise RuntimeError("synthetic report failure")
        return _inputs(model_version)

    async def load_volume(db: AsyncSession, season: int) -> volume_ranking.VolumeInputs:
        assert season == 2026
        calls.append(VOLUME)
        if VOLUME == fail_model:
            raise RuntimeError("synthetic report failure")
        return _volume_inputs()

    monkeypatch.setattr(pool, "SessionLocal", Session)
    monkeypatch.setattr(track_record, "load_ranking_calls", load)
    monkeypatch.setattr(volume_ranking, "load_volume_inputs", load_volume)
    return calls


def test_default_arguments_preserve_the_v4_only_command() -> None:
    args = cli.parse_args([])
    assert (args.season, args.model_version) == (2026, V4)


@pytest.mark.parametrize("selector", [V4, TARGETS, VOLUME, "all"])
def test_the_cli_selectors_are_accepted(selector: str) -> None:
    assert cli.parse_args(["--model-version", selector]).model_version == selector


@pytest.mark.parametrize("selector", ["nfl-targets-v2", "nfl-volume-v2", "", "unknown"])
def test_invalid_selectors_exit_before_loading_a_database(
    monkeypatch: pytest.MonkeyPatch, selector: str,
) -> None:
    monkeypatch.setitem(sys.modules, "app.db.pool", None)
    with pytest.raises(SystemExit) as error:
        cli.main(["--model-version", selector])
    assert error.value.code == 2


def test_help_needs_no_database(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setitem(sys.modules, "app.db.pool", None)
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0
    assert "--model-version" in capsys.readouterr().out


def test_direct_run_also_rejects_unknown_models_before_database_import(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "app.db.pool", None)
    with pytest.raises(ValueError, match="Unknown NFL ranking model"):
        asyncio.run(cli.run(2026, "unknown"))


def test_targets_report_labels_coverage_and_the_absence_of_a_served_probability() -> None:
    inputs = _inputs(TARGETS)
    text = cli.report(2026, slice_results(inputs.calls), inputs.frozen_rows, {}, inputs.coverage, TARGETS, None)
    assert text.splitlines()[0] == f"NFL forward ranking check, 2026 (model {TARGETS}, P(over) not served)"
    assert "coverage, eligible standard Rec Targets props with a targets-version frozen row: wk 3 2/10" in text
    assert "funnel: calls 2, with P(over) 0, picks 0, one per bet 0" in text
    assert "validation did not pass" in text and "no probability-based picks accrue" in text
    assert "Goblin and demon lines are not projected" in text
    assert "None" not in text and "nfl-targets-pover-v1" not in text


def test_default_cli_prints_only_the_original_v4_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    calls = _stub_loaders(monkeypatch)
    cli.main([])
    inputs = _inputs(V4)
    expected = cli.report(2026, slice_results(inputs.calls), inputs.frozen_rows, {}, inputs.coverage)
    assert capsys.readouterr().out == expected + "\n"
    assert calls == ["session_enter", V4, "session_exit"]


def test_targets_selector_loads_only_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_loaders(monkeypatch)
    text = asyncio.run(cli.run(2026, TARGETS))
    assert TARGETS in text and V4 not in text
    assert calls == ["session_enter", TARGETS, "session_exit"]


def test_all_loads_v4_then_targets_then_volume_and_keeps_their_funnels_separate(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_loaders(monkeypatch)
    text = asyncio.run(cli.run(2026, "all"))
    assert text.count("NFL forward ranking check") == 3
    assert text.index(V4) < text.index(TARGETS) < text.index(VOLUME)
    assert "funnel: calls 1, with P(over) 1, picks 1, one per bet 1" in text
    assert "funnel: calls 2, with P(over) 0, picks 0, one per bet 0" in text
    assert "funnel: calls 200, with P(over) 200, picks 200, one per bet 200" in text
    assert "wk 3 1/10" in text and "wk 3 2/10" in text and "wk 9 50/115" in text
    assert calls == ["session_enter", V4, TARGETS, VOLUME, "session_exit"]


def test_volume_selector_loads_only_the_volume_record(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _stub_loaders(monkeypatch)
    text = asyncio.run(cli.run(2026, VOLUME))
    assert VOLUME in text and V4 not in text and TARGETS not in text
    assert calls == ["session_enter", VOLUME, "session_exit"]


def test_the_volume_report_shows_progress_the_log_loss_and_the_not_frozen_slices(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_loaders(monkeypatch)
    text = asyncio.run(cli.run(2026, VOLUME))

    assert text.splitlines()[0] == f"NFL forward ranking check, 2026 (model {VOLUME}, P(over) nfl-volume-anchor-v1)"
    assert "coverage, eligible standard, goblin and demon receptions props with a volume-version frozen row: wk 9 50/115" in text
    assert "standard over" in text and "standard under" in text
    assert "goblin over" not in text.split("slice            picks")[1].split("Volume model")[0]
    assert "adopt" in text and "accruing" in text
    assert "second clause" in text and "log-loss progress below is not a verdict" in text
    assert "standard lines so far: 200 lines" in text and "weeks won 4 of 4 (need 3)" in text
    assert "Not frozen yet: goblin over, demon over (no frozen row for that payout)." in text
    assert "None" not in text


def test_the_volume_report_lists_a_rung_payout_once_it_has_frozen_rows_and_only_names_the_unfrozen(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_loaders(monkeypatch)

    async def with_demon(db: AsyncSession, season: int) -> volume_ranking.VolumeInputs:
        base = _volume_inputs()
        return volume_ranking.VolumeInputs(base.calls, base.log_rows, frozenset({"standard", "demon"}))

    monkeypatch.setattr(volume_ranking, "load_volume_inputs", with_demon)
    text = asyncio.run(cli.run(2026, VOLUME))

    table = text.split("slice            picks")[1].split("Volume model")[0]
    assert "standard over" in table and "demon over" in table and "goblin over" not in table
    assert "Not frozen yet: goblin over (no frozen row for that payout)." in text
    assert "demon over, verdict sample" in text


def test_the_volume_report_for_an_empty_record_is_ordinary(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_loaders(monkeypatch)

    async def empty(db: AsyncSession, season: int) -> volume_ranking.VolumeInputs:
        return volume_ranking.VolumeInputs(RankingCalls([], Counter(), 0, {}, set()), {}, frozenset())

    monkeypatch.setattr(volume_ranking, "load_volume_inputs", empty)
    text = asyncio.run(cli.run(2026, VOLUME))

    assert "frozen rows on completed games 0; excluded: none" in text
    assert "standard lines so far: no settled lines yet" in text
    assert "Not frozen yet: standard over, standard under, goblin over, demon over" in text


@pytest.mark.parametrize("fail_model", [V4, TARGETS, VOLUME])
def test_either_failure_leaves_no_partial_success_output_and_closes_the_session(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fail_model: str,
) -> None:
    calls = _stub_loaders(monkeypatch, fail_model)
    with pytest.raises(RuntimeError, match="synthetic report failure"):
        cli.main(["--model-version", "all"])
    assert capsys.readouterr().out == ""
    assert calls[-1] == "session_exit"
