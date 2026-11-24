"""Shared fixtures and builders, first written for `test_nfl_volume_ranking_service.py`."""
from __future__ import annotations

import asyncio
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_volume_anchor import NFL_VOLUME_ANCHOR_VERSION as ANCHOR
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION as VOLUME
from app.core.prop_ranking_check import FrozenLine
from app.repositories.nfl_volume_ranking import VolumeFrozenLine
from app.services.nfl import track_record, volume_ranking
from app.services.tennis.live_odds_cache import TimedSingleFlight
from tests.helpers.prop_ranking_check import _frozen


DB = cast(AsyncSession, object())
FINISHED = {9, 10, 11, 12}


def _line(
    line_id: int, week: int, outcome: str = "over", p_over: float | None = 0.7, p_under: float | None = 0.3,
    q_vol: float | None = 0.5, **overrides: object,
) -> VolumeFrozenLine:
    fields: dict = {
        "line_id": line_id, "period": week, "player_id": line_id, "game_id": 1000 + line_id,
        "market": "receptions", "odds_type": "standard", "outcome": outcome, "p_over": p_over, "p_under": p_under,
        "model_version": VOLUME, "over_probability_version": ANCHOR,
    } | overrides
    return VolumeFrozenLine(FrozenLine(**fields), q_vol)


def _passing_sample() -> list[VolumeFrozenLine]:
    """200 over-picks over four weeks, 80% of which hit, on lines the blend prices well."""
    return [
        _line(week * 1000 + i, week, "over" if i < 40 else "under")
        for week in (9, 10, 11, 12) for i in range(50)
    ]


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(track_record, "_RANKING", TimedSingleFlight(900))
    monkeypatch.setattr(volume_ranking, "_VOLUME", TimedSingleFlight(900))


def _repositories(
    monkeypatch: pytest.MonkeyPatch, volume: list[VolumeFrozenLine], finished: set[int] = FINISHED,
    coverage: dict[int, tuple[int, int]] | None = None,
) -> list[str]:
    calls: list[str] = []

    async def volume_rows(db: AsyncSession, season: int) -> list[VolumeFrozenLine]:
        calls.append("volume")
        return volume

    async def volume_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        calls.append("volume_coverage")
        return coverage if coverage is not None else {9: (115, 40)}

    async def finished_weeks(db: AsyncSession, season: int) -> set[int]:
        calls.append("finished")
        return finished

    async def v4_rows(db: AsyncSession, season: int) -> list[FrozenLine]:
        calls.append("v4")
        return [_frozen(11), _frozen(12, p_over=None, over_probability_version=None)]

    async def v4_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        calls.append("v4_coverage")
        return {9: (20, 12)}

    monkeypatch.setattr(volume_ranking.nfl_volume_ranking, "get_frozen_volume_lines", volume_rows)
    monkeypatch.setattr(volume_ranking.nfl_volume_ranking, "get_frozen_coverage", volume_coverage)
    monkeypatch.setattr(volume_ranking.nfl, "get_finished_weeks", finished_weeks)
    monkeypatch.setattr(track_record.nfl_repo, "get_frozen_gradeable_lines", v4_rows)
    monkeypatch.setattr(track_record.nfl_repo, "get_finished_weeks", finished_weeks)
    monkeypatch.setattr(track_record.nfl_repo, "get_frozen_coverage", v4_coverage)
    return calls


def _volume(monkeypatch: pytest.MonkeyPatch, lines: list[VolumeFrozenLine], **kwargs: object) -> volume_ranking.VolumeRankingRecord:
    _repositories(monkeypatch, lines, **kwargs)  # type: ignore[arg-type]
    record = asyncio.run(volume_ranking.get_volume_record(DB, 2026))
    assert record is not None
    return record


def _rungs(odds_type: str, base: int, p_over: float = 0.7, hit_share: float = 0.8, per_week: int = 50) -> list[VolumeFrozenLine]:
    return [
        _line(base + week * 1000 + i, week, "over" if i < hit_share * per_week else "under", p_over=p_over, p_under=1 - p_over, odds_type=odds_type)
        for week in (9, 10, 11, 12) for i in range(per_week)
    ]
