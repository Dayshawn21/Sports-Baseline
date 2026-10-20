from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION as V4
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION as TARGETS
from app.core.prop_ranking_check import FrozenLine
from app.services.nfl import targets_ranking, track_record
from app.services.nfl.prop_source import NflPropSource
from app.services.prop_ranking import RankingCalls
from app.services.sport_registry import prop_source
from app.services.tennis.live_odds_cache import TimedSingleFlight
from tests.test_nfl_track_record_service import GRADED_AT
from tests.test_prop_ranking_check import _frozen

DB = cast(AsyncSession, object())


def _targets(line_id: int = 21, **overrides: object) -> FrozenLine:
    return replace(FrozenLine(
        line_id, 3, line_id, 100 + line_id, "receiving_targets", "standard", "over", None, None, TARGETS, None,
    ), **overrides)


def _repositories(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    calls: list[tuple[str, int]] = []

    async def v4_rows(db: AsyncSession, season: int) -> list[FrozenLine]:
        calls.append(("v4", season))
        return [_frozen(11), _frozen(12, p_over=None, over_probability_version=None)]

    async def targets_rows(db: AsyncSession, season: int) -> list[FrozenLine]:
        calls.append(("targets", season))
        return [
            _targets(), _targets(22, outcome="under"), _targets(23, outcome="push"),
            _targets(24, outcome="void_dnp"), _targets(25, outcome="stat_unavailable"),
            _targets(26, period=4), _targets(27, model_version=V4),
            _targets(28, over_probability_version="nfl-targets-pover-v1"),
        ]

    async def finished(db: AsyncSession, season: int) -> set[int]:
        calls.append(("finished", season))
        return {2, 3}

    async def v4_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        calls.append(("v4_coverage", season))
        return {2: (7, 0), 3: (20, 12)}

    async def targets_coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        calls.append(("targets_coverage", season))
        return {3: (5, 2)}

    monkeypatch.setattr(track_record.nfl_repo, "get_frozen_gradeable_lines", v4_rows)
    monkeypatch.setattr(track_record.nfl_repo, "get_finished_weeks", finished)
    monkeypatch.setattr(track_record.nfl_repo, "get_frozen_coverage", v4_coverage)
    monkeypatch.setattr(targets_ranking.nfl_targets_ranking, "get_frozen_gradeable_lines", targets_rows)
    monkeypatch.setattr(targets_ranking.nfl_targets_ranking, "get_frozen_coverage", targets_coverage)
    return calls


def test_targets_source_is_read_only_and_the_registered_nfl_source_is_unchanged() -> None:
    source = track_record.ranking_source(TARGETS)
    assert isinstance(source, targets_ranking.NflTargetsRankingSource)
    assert (source.config.code, source.config.period_label) == ("nfl", "week")
    assert (source.model_version, source.over_probability_version) == (TARGETS, None)
    assert isinstance(prop_source("nfl"), NflPropSource)
    assert isinstance(track_record.ranking_source(), NflPropSource)


def test_models_use_separate_rows_coverage_and_the_same_finished_week_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _repositories(monkeypatch)
    v4 = asyncio.run(track_record.load_ranking_calls(DB, 2026))
    targets = asyncio.run(track_record.load_ranking_calls(DB, 2026, TARGETS))

    assert [call.line_id for call in v4.calls] == [11, 12]
    assert [call.line_id for call in targets.calls] == [21, 22]
    assert targets.exclusions == {
        "push": 1, "void_dnp": 1, "stat_unavailable": 1, "week_not_finished": 1, "wrong_version": 2,
    }
    assert (v4.coverage, targets.coverage) == ({2: (7, 0), 3: (20, 12)}, {3: (5, 2)})
    assert v4.finished_periods == targets.finished_periods == {2, 3}
    assert calls == [("v4", 2026), ("finished", 2026), ("v4_coverage", 2026),
                     ("targets", 2026), ("finished", 2026), ("targets_coverage", 2026)]

    record = track_record.build_ranking_record(targets, 2026, GRADED_AT, TARGETS)
    assert (record.model_version, record.over_probability_version, record.frozen_rows) == (TARGETS, None, 8)
    assert (record.funnel.calls, record.funnel.with_p_over, record.funnel.picks, record.funnel.bets) == (2, 0, 0, 0)
    assert len(record.slices) == 4
    assert all((s.verdict, s.n, s.weeks, s.signal) == ("insufficient", 0, 0, "neutral") for s in record.slices)
    assert all(s.hit_rate is None and s.standard_error is None for s in record.slices)


def test_a_large_probability_free_targets_sample_never_fixes_a_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _repositories(monkeypatch)

    async def rows(db: AsyncSession, season: int) -> list[FrozenLine]:
        return [_targets(i, period=1+i%4) for i in range(300)]

    async def finished(db: AsyncSession, season: int) -> set[int]:
        return {1, 2, 3, 4}

    monkeypatch.setattr(targets_ranking.nfl_targets_ranking, "get_frozen_gradeable_lines", rows)
    monkeypatch.setattr(track_record.nfl_repo, "get_finished_weeks", finished)
    inputs = asyncio.run(track_record.load_ranking_calls(DB, 2026, TARGETS))
    record = track_record.build_ranking_record(inputs, 2026, GRADED_AT, TARGETS)

    assert record.funnel.calls == 300
    assert record.funnel.picks == record.funnel.bets == 0
    assert all(s.verdict == "insufficient" and s.n == 0 for s in record.slices)


def test_no_targets_or_finished_weeks_is_a_valid_empty_record(monkeypatch: pytest.MonkeyPatch) -> None:
    async def rows(db: AsyncSession, season: int) -> list[FrozenLine]:
        return []

    async def finished(db: AsyncSession, season: int) -> set[int]:
        return set()

    async def coverage(db: AsyncSession, season: int) -> dict[int, tuple[int, int]]:
        return {}

    monkeypatch.setattr(targets_ranking.nfl_targets_ranking, "get_frozen_gradeable_lines", rows)
    monkeypatch.setattr(targets_ranking.nfl_targets_ranking, "get_frozen_coverage", coverage)
    monkeypatch.setattr(track_record.nfl_repo, "get_finished_weeks", finished)
    inputs = asyncio.run(track_record.load_ranking_calls(DB, 2026, TARGETS))
    record = track_record.build_ranking_record(inputs, 2026, GRADED_AT, TARGETS)

    assert record.frozen_rows == record.funnel.calls == 0
    assert record.coverage == record.finished_weeks == []
    assert record.excluded == {} and record.last_settled_week is None


def test_unknown_models_fail_before_reading_or_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _repositories(monkeypatch)
    with pytest.raises(ValueError, match="Unknown NFL ranking model"):
        asyncio.run(track_record.get_ranking_record(DB, 2026, "nfl-targets-v2"))
    assert calls == []


def _cached_loader(
    monkeypatch: pytest.MonkeyPatch, failures: set[tuple[int, str]],
) -> tuple[Counter[tuple[int, str]], list[float]]:
    calls: Counter[tuple[int, str]] = Counter()
    clock = [0.0]

    async def load(db: AsyncSession, season: int, model_version: str = V4) -> RankingCalls:
        key = season, model_version
        calls[key] += 1
        await asyncio.sleep(0)
        if key in failures:
            raise RuntimeError("synthetic lookup failure")
        return RankingCalls([], Counter(), 0, {}, set())

    monkeypatch.setattr(track_record, "load_ranking_calls", load)
    monkeypatch.setattr(track_record, "_RANKING", TimedSingleFlight(track_record.CACHE_TTL_SECONDS, clock=lambda: clock[0]))
    return calls, clock


def test_concurrent_records_share_only_the_same_season_and_model_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _cached_loader(monkeypatch, set())

    async def run() -> None:
        default, explicit, targets, duplicate, next_season = await asyncio.gather(
            track_record.get_ranking_record(DB, 2026), track_record.get_ranking_record(DB, 2026, V4),
            track_record.get_ranking_record(DB, 2026, TARGETS), track_record.get_ranking_record(DB, 2026, TARGETS),
            track_record.get_ranking_record(DB, 2027, TARGETS),
        )
        assert default is explicit and targets is duplicate
        assert default is not None and targets is not None and next_season is not None
        assert (default.model_version, targets.model_version, next_season.season) == (V4, TARGETS, 2027)
        assert default.over_probability_version == "nfl-pover-v1" and targets.over_probability_version is None

    asyncio.run(run())
    assert calls == {(2026, V4): 1, (2026, TARGETS): 1, (2027, TARGETS): 1}


def test_cached_failures_are_isolated_and_retry_only_after_the_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    failures = {(2026, TARGETS)}
    calls, clock = _cached_loader(monkeypatch, failures)

    async def run() -> None:
        targets, v4, next_season = await asyncio.gather(
            track_record.get_ranking_record(DB, 2026, TARGETS), track_record.get_ranking_record(DB, 2026),
            track_record.get_ranking_record(DB, 2027, TARGETS),
        )
        assert targets is None and v4 is not None and next_season is not None
        failures.clear()
        clock[0] = track_record.CACHE_TTL_SECONDS - 1
        assert await track_record.get_ranking_record(DB, 2026, TARGETS) is None
        assert await track_record.get_ranking_record(DB, 2026) is v4
        assert calls[(2026, TARGETS)] == 1
        clock[0] = track_record.CACHE_TTL_SECONDS
        recovered = await track_record.get_ranking_record(DB, 2026, TARGETS)
        assert recovered is not None and recovered.model_version == TARGETS

    asyncio.run(run())
    assert calls == {(2026, TARGETS): 2, (2026, V4): 1, (2027, TARGETS): 1}


def test_probability_identity_is_part_of_the_cache_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _cached_loader(monkeypatch, set())

    async def run() -> None:
        initial = await track_record.get_ranking_record(DB, 2026, TARGETS)
        # Only a synthetic source change: real future probability versions need separate approval.
        monkeypatch.setattr(targets_ranking.NflTargetsRankingSource, "over_probability_version", "synthetic-v2")
        changed = await track_record.get_ranking_record(DB, 2026, TARGETS)
        assert initial is not None and changed is not None
        assert initial.over_probability_version is None
        assert changed.over_probability_version == "synthetic-v2" and initial is not changed

    asyncio.run(run())
    assert calls[(2026, TARGETS)] == 2
