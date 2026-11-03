"""The volume reference rides on the v4 receptions line and freezes beside it, leaving v4 unchanged."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_projection import PlayerGame
from app.repositories.nfl_volume_serving import VolumeServingLine
from app.schemas.nfl import NflSlateResponse
from app.services.nfl import slate
from app.services.nfl.prop_predictions import freeze_rows
from app.services.nfl.prop_source import NflPropSource
from app.services.prop_predictions import freeze_current_period
from tests.test_nfl_projection_harness import _replay_row
from tests.test_nfl_targets_service import FETCHED, KICKOFF, NOW
from tests.test_nfl_targets_slate import _game, _inputs

DB = cast(AsyncSession, object())
V4_VERSION = "opponent-dvp-tg-blend-usage-snap-v4"
HISTORY = tuple(
    PlayerGame(2026, week, {"targets": 7.0, "receptions": 5.0}, team_pass_attempts=34.0, team_rush_attempts=26.0)
    for week in range(1, 7)
)


def _v4_receptions(**overrides: object) -> dict:
    return _replay_row(id=1, game_id=50, market="receptions", line=5.5, fetched_at=FETCHED) | overrides


def _volume(line_id: int = 1, **overrides: object) -> VolumeServingLine:
    fields: dict = {
        "line_id": line_id, "game_id": 50, "player_id": 3, "player_name": "Receiver", "position": "WR",
        "season": 2026, "week": 7, "player_team_id": 4, "opponent_team_id": 5, "is_home": True,
        "start_utc": KICKOFF, "market": "receptions", "segment": "full_game", "odds_type": "standard",
        "line": 5.5, "provider": "replay", "fetched_at": FETCHED, "home_spread_margin": -3.0, "total": 45.0,
        "history": HISTORY,
    } | overrides
    return VolumeServingLine(**fields)


def _serve(monkeypatch: pytest.MonkeyPatch, volume: list[VolumeServingLine], start: datetime | None = KICKOFF) -> None:
    _inputs(monkeypatch, [_game() | {"start_utc": start}], [_v4_receptions()], [])
    monkeypatch.setattr(slate.volume_repo, "get_volume_serving_lines", AsyncMock(return_value=volume))


def _build() -> NflSlateResponse:
    return asyncio.run(slate.build_slate(DB, 2026, 7, NOW))


def test_the_v4_slate_is_byte_identical_once_the_volume_field_is_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [])
    before = _build()
    _serve(monkeypatch, [_volume()])
    mixed = _build()

    (line,) = mixed.games[0].lines
    assert line.volume is not None and line.volume.model_version == "nfl-volume-v1"
    stripped = mixed.model_copy(deep=True)
    stripped.games[0].lines[0].volume = None
    assert stripped.model_dump_json() == before.model_dump_json()
    assert (mixed.line_count, mixed.unmatched_count) == (before.line_count, before.unmatched_count)


def test_a_slate_without_volume_rows_has_a_null_volume_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [])
    assert [line.volume for line in _build().games[0].lines] == [None]


def test_a_line_without_a_usable_reference_gets_no_companion(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [_volume(history=())])
    assert _build().games[0].lines[0].volume is None


def test_a_volume_row_for_a_line_v4_does_not_serve_attaches_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [_volume(line_id=999)])
    assert [line.volume for line in _build().games[0].lines] == [None]


def test_the_freezer_writes_a_v4_row_and_a_volume_row_under_their_own_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [_volume()])
    rows, counts = freeze_rows(_build(), NOW)

    assert counts == {"frozen": 2}
    by_model = {row.model_version: row for row in rows}
    assert set(by_model) == {V4_VERSION, "nfl-volume-v1"}
    assert {row.prop_line_id for row in rows} == {1}
    assert by_model["nfl-volume-v1"].over_probability_version == "nfl-volume-anchor-v1"
    assert by_model["nfl-volume-v1"].p_over is not None
    assert by_model[V4_VERSION].over_probability_version != "nfl-volume-anchor-v1"


def test_the_v4_frozen_rows_are_unchanged_by_the_companion(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [])
    plain, _ = freeze_rows(_build(), NOW)
    _serve(monkeypatch, [_volume()])
    mixed, _ = freeze_rows(_build(), NOW)

    assert [row for row in mixed if row.model_version != "nfl-volume-v1"] == plain


@pytest.mark.parametrize("start", [NOW, NOW - timedelta(seconds=1), None])
def test_started_and_unknown_start_games_freeze_neither_row(monkeypatch: pytest.MonkeyPatch, start: datetime | None) -> None:
    _serve(monkeypatch, [_volume(start_utc=start)], start=start)

    rows, counts = freeze_rows(_build(), NOW)

    assert rows == [] and counts == {"no_start_time" if start is None else "kicked_off": 2, "frozen": 0}


def test_the_source_dry_run_counts_both_rows_and_keeps_its_v4_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [_volume()])
    source = NflPropSource()

    run = asyncio.run(freeze_current_period(DB, source, NOW, dry_run=True))

    assert run is not None and run.inserted is None and run.counts == {"frozen": 2}
    assert source.model_version == V4_VERSION and source.over_probability_version == "nfl-pover-v1"


def test_a_stored_snapshot_without_the_field_still_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    _serve(monkeypatch, [])
    payload = _build().model_dump(by_alias=True)
    for line in payload["games"][0]["lines"]:
        del line["volume"]

    restored = NflSlateResponse.model_validate(payload)

    assert [line.volume for line in restored.games[0].lines] == [None]


def test_each_line_has_two_distinct_conflict_keys_and_a_rerun_repeats_them(monkeypatch: pytest.MonkeyPatch) -> None:
    def keys() -> list[tuple[int, str, str | None]]:
        rows, _ = freeze_rows(_build(), NOW)
        return [(row.prop_line_id, row.model_version, row.over_probability_version) for row in rows]

    _serve(monkeypatch, [_volume()])
    first = keys()

    assert len(set(first)) == 2
    assert keys() == first
