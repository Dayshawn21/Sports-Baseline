from __future__ import annotations

import asyncio
from collections import Counter
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION as V4
from app.core.nfl_volume_anchor import NFL_VOLUME_ANCHOR_VERSION as ANCHOR
from app.core.nfl_volume_projection import NFL_VOLUME_MODEL_VERSION as VOLUME
from app.repositories.nfl_volume_ranking import VolumeFrozenLine
from app.services.nfl import track_record, volume_ranking
from app.services.nfl.prop_source import NflPropSource
from app.services.sport_registry import prop_source
from app.services.tennis.live_odds_cache import TimedSingleFlight
from tests.helpers.nfl_volume_ranking_service import (  # noqa: F401 (_fresh_caches is autouse)
    DB, FINISHED, _fresh_caches, _line, _passing_sample, _repositories, _rungs, _volume,
)

GRADED_AT = datetime(2026, 11, 20, 15, tzinfo=UTC)


def test_the_volume_source_is_report_only_and_the_registered_nfl_source_is_unchanged() -> None:
    source = track_record.ranking_source(VOLUME)
    assert isinstance(source, volume_ranking.NflVolumeRankingSource)
    assert (source.config.code, source.config.period_label) == ("nfl", "week")
    assert (source.model_version, source.over_probability_version) == (VOLUME, ANCHOR)
    assert isinstance(prop_source("nfl"), NflPropSource)
    assert isinstance(track_record.ranking_source(), NflPropSource)
    assert prop_source("nfl").model_version == V4


def test_the_record_carries_the_volume_identity_and_a_nonnull_probability_version(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample())

    assert (record.record.model_version, record.record.over_probability_version) == (VOLUME, ANCHOR)
    assert record.record.season == 2026 and record.record.last_settled_week == 12
    assert record.record.funnel.calls == 200 and record.record.funnel.with_p_over == 200


def test_both_clauses_passing_adopts_standard_over_and_the_four_slices_stay_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample())

    slices = {(row.odds_type, row.side): row for row in record.record.slices}
    assert list(slices) == [("standard", "over"), ("standard", "under"), ("goblin", "over"), ("demon", "over")]
    over = slices[("standard", "over")]
    assert (over.verdict, over.n, over.weeks, over.hits, over.signal) == ("adopt", 200, 4, 160, "positive")
    state = next(item for item in record.states if (item.odds_type, item.side) == ("standard", "over"))
    assert state.state == "evaluated" and state.log_loss is not None and state.log_loss.passed


def test_the_log_loss_clause_failing_blocks_adopt_and_keeps_the_signal_gray(monkeypatch: pytest.MonkeyPatch) -> None:
    noise = [_line(900000 + i, 9 + i % 4, "over" if i % 2 else "under", p_over=0.6, p_under=0.4) for i in range(3000)]
    record = _volume(monkeypatch, _passing_sample() + noise)

    over = next(row for row in record.record.slices if (row.odds_type, row.side) == ("standard", "over"))
    assert over.hit_rate is not None and over.hit_rate >= 0.8
    assert over.verdict == "reject" and over.signal == "neutral"


def test_goblin_and_demon_read_not_frozen_never_insufficient_with_picks(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample())

    by_slice = {(item.odds_type, item.side): item for item in record.states}
    assert by_slice[("goblin", "over")].state == by_slice[("demon", "over")].state == "not_frozen"
    for key in (("goblin", "over"), ("demon", "over")):
        row = next(item for item in record.record.slices if (item.odds_type, item.side) == key)
        assert (row.verdict, row.n, row.weeks, row.hit_rate, row.signal) == ("insufficient", 0, 0, None, "neutral")
        assert by_slice[key].log_loss is None


def test_a_payout_reads_evaluated_once_any_row_of_it_is_frozen_even_if_unsettled(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = _passing_sample() + [_line(700001, 9, "void_dnp", odds_type="demon"), _line(700002, 9, "over", odds_type="goblin")]
    record = _volume(monkeypatch, lines)

    states = {(item.odds_type, item.side): item.state for item in record.states}
    assert states == {
        ("standard", "over"): "evaluated", ("standard", "under"): "evaluated",
        ("goblin", "over"): "evaluated", ("demon", "over"): "evaluated",
    }
    assert len(record.record.slices) == 4


def test_with_no_frozen_row_at_all_every_payout_reads_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, [], finished=set(), coverage={})
    assert [item.state for item in record.states] == ["not_frozen"] * 4


def test_each_rung_slice_is_judged_on_its_own_payouts_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    noise = [_line(900000 + i, 9 + i % 4, "over" if i % 2 else "under", p_over=0.6, p_under=0.4) for i in range(3000)]
    record = _volume(monkeypatch, _passing_sample() + noise + _rungs("demon", 2_000_000))

    slices = {(row.odds_type, row.side): row for row in record.record.slices}
    assert slices[("standard", "over")].verdict == "reject"
    assert slices[("demon", "over")].verdict == "adopt" and slices[("demon", "over")].n == 200
    states = {(item.odds_type, item.side): item for item in record.states}
    assert states[("demon", "over")].state == "evaluated" and states[("demon", "over")].log_loss is not None
    assert states[("demon", "over")].log_loss.passed
    assert states[("goblin", "over")].state == "not_frozen"


def test_the_standard_progress_block_ignores_rung_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample() + _rungs("demon", 2_000_000) + _rungs("goblin", 3_000_000))

    assert record.log_loss_progress.n == 200


def test_a_goblin_payout_with_rows_but_no_picks_reads_accruing_not_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample() + _rungs("goblin", 3_000_000, p_over=0.55))

    goblin = next(row for row in record.record.slices if row.odds_type == "goblin")
    assert (goblin.verdict, goblin.n, goblin.weeks, goblin.signal) == ("insufficient", 0, 0, "neutral")
    assert next(item for item in record.states if item.odds_type == "goblin").state == "evaluated"


def test_rungs_of_one_player_game_collapse_to_one_pick_per_bet(monkeypatch: pytest.MonkeyPatch) -> None:
    ladder = [
        _line(4_000_000 + i, 9, "over", odds_type="demon", player_id=7, game_id=88, p_over=0.7 + i / 100, p_under=0.3 - i / 100)
        for i in range(3)
    ]
    record = _volume(monkeypatch, ladder)

    assert (record.record.funnel.picks, record.record.funnel.bets) == (3, 1)
    demon = next(row for row in record.record.slices if row.odds_type == "demon")
    assert demon.n == 1


def test_rung_rows_are_not_mixed_into_a_payout_with_no_rows_of_its_own() -> None:
    lines = _rungs("demon", 2_000_000)
    rows = volume_ranking.log_loss_rows(lines, FINISHED)

    assert set(rows) == {"demon"} and len(rows["demon"]) == 200


def test_fewer_than_two_hundred_picks_is_insufficient_with_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, [_line(i, 9) for i in range(30)])

    over = record.record.slices[0]
    assert (over.verdict, over.n, over.weeks) == ("insufficient", 30, 1) and over.signal == "neutral"
    assert record.log_loss_progress.n == 30 and record.log_loss_progress.blend is not None


def test_an_unfinished_week_cannot_fix_the_sample_or_feed_the_log_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = _passing_sample() + [_line(800000 + i, 13) for i in range(50)]
    record = _volume(monkeypatch, lines, finished={9, 10, 11, 12})

    assert record.record.excluded == {"week_not_finished": 50}
    assert record.log_loss_progress.n == 200 and record.record.slices[0].n == 200


def test_pushes_and_unsettled_lines_never_become_calls_and_pushes_leave_the_log_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [
        _line(1, 9), _line(2, 9, "under", p_over=0.3, p_under=0.7), _line(3, 9, "push"),
        _line(4, 9, "void_dnp"), _line(5, 9, "stat_unavailable"), _line(6, 9, "q_vol_unavailable", q_vol=None),
        _line(7, 9, "probability_unavailable", p_over=None, p_under=None),
    ]
    record = _volume(monkeypatch, lines)

    assert record.record.funnel.calls == 2
    assert record.record.excluded == {
        "probability_unavailable": 1, "push": 1, "q_vol_unavailable": 1, "stat_unavailable": 1, "void_dnp": 1,
    }
    assert record.log_loss_progress.n == 2


def test_an_empty_record_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, [], finished=set(), coverage={})

    assert record.record.frozen_rows == 0 and record.record.finished_weeks == []
    assert all(row.verdict == "insufficient" and row.n == 0 for row in record.record.slices)
    assert record.log_loss_progress.n == 0 and not record.log_loss_progress.passed


def test_coverage_is_the_volume_identity_only(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _volume(monkeypatch, _passing_sample(), coverage={9: (115, 40), 10: (110, 50)})
    assert [(week.week, week.lines, week.frozen) for week in record.record.coverage] == [(9, 115, 40), (10, 110, 50)]


def test_a_row_of_another_identity_is_a_wrong_version_exclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = [_line(1, 9), _line(2, 9, model_version=V4), _line(3, 9, over_probability_version="nfl-pover-v1")]
    record = _volume(monkeypatch, lines)
    assert record.record.funnel.calls == 1 and record.record.excluded == {"wrong_version": 2}


def test_the_generic_ranking_path_returns_the_composite_record(monkeypatch: pytest.MonkeyPatch) -> None:
    lines = _passing_sample()
    _repositories(monkeypatch, lines)

    generic = asyncio.run(track_record.get_ranking_record(DB, 2026, VOLUME))
    volume = asyncio.run(volume_ranking.get_volume_record(DB, 2026))

    assert generic is not None and volume is not None and generic == volume.record
    assert generic.slices[0].verdict == "adopt"


def test_one_query_serves_the_calls_and_the_log_loss_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _repositories(monkeypatch, _passing_sample())
    asyncio.run(volume_ranking.get_volume_record(DB, 2026))
    assert calls.count("volume") == 1


def test_v4_is_unchanged_by_the_volume_record_and_a_volume_failure_stays_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    _repositories(monkeypatch, _passing_sample())
    before = asyncio.run(track_record.get_ranking_record(DB, 2026))
    asyncio.run(volume_ranking.get_volume_record(DB, 2026))

    async def boom(db: AsyncSession, season: int) -> list[VolumeFrozenLine]:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(track_record, "_RANKING", TimedSingleFlight(900))
    monkeypatch.setattr(volume_ranking, "_VOLUME", TimedSingleFlight(900))
    monkeypatch.setattr(volume_ranking.nfl_volume_ranking, "get_frozen_volume_lines", boom)

    assert asyncio.run(track_record.get_ranking_record(DB, 2026, VOLUME)) is None
    after = asyncio.run(track_record.get_ranking_record(DB, 2026))
    assert before is not None and after is not None
    assert before.model_version == V4 and (before.slices, before.funnel, before.excluded, before.coverage) == (
        after.slices, after.funnel, after.excluded, after.coverage,
    )
    assert after.over_probability_version == "nfl-pover-v1" and Counter(after.excluded) == Counter(before.excluded)


def test_seasons_are_cached_separately(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _repositories(monkeypatch, _passing_sample())
    asyncio.run(volume_ranking.get_volume_record(DB, 2026))
    asyncio.run(volume_ranking.get_volume_record(DB, 2026))
    asyncio.run(volume_ranking.get_volume_record(DB, 2025))
    assert calls.count("volume") == 2
