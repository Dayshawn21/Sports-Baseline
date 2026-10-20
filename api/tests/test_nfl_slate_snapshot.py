"""Stored NFL slates (37d, Step 9g): production serves the stored copy and never
builds, dev still can, and the stored text is the body the route used to send."""
import asyncio
import json
from datetime import timedelta

import pytest

from app.ingest.nfl_slate_snapshot import parse_weeks, summary
from app.repositories import report_snapshots
from app.services.nfl import slate_cache
from app.services.nfl.slate_cache import load_slate_json, slate_json, slate_report
from tests.test_nfl_prop_predictions import NOW, _game, _line, _slate


def _sample():
    return _slate(_game(1, NOW + timedelta(hours=2), [_line(10), _line(11, p_over=None)]))


def _as_jsonb_text(body: bytes) -> str:
    """Postgres prints jsonb with its own spacing and key order."""
    return json.dumps(json.loads(body), sort_keys=True)


@pytest.fixture
def builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    calls: list[tuple[int, int]] = []

    async def build(_db, season, week, _now):
        calls.append((season, week))
        return _sample()

    monkeypatch.setattr(slate_cache, "build_slate", build)
    return calls


def _stored(monkeypatch: pytest.MonkeyPatch, text: str | None) -> list[tuple[str, int]]:
    reads: list[tuple[str, int]] = []

    async def get(_db, report, season):
        reads.append((report, season))
        return text

    monkeypatch.setattr(report_snapshots, "get_snapshot_text", get)
    return reads


def test_the_week_is_in_the_report_name():
    assert slate_report(6) == "nfl_slate_week_6"
    assert slate_report(18) != slate_report(1)


def test_a_stored_slate_is_served_without_a_build(monkeypatch, builds):
    text = _as_jsonb_text(slate_json(_sample()))
    reads = _stored(monkeypatch, text)

    served = asyncio.run(load_slate_json(None, 2026, 6, production=True))

    assert served == text.encode()
    assert reads == [("nfl_slate_week_6", 2026)]
    assert builds == []


def test_production_without_a_stored_slate_is_unavailable(monkeypatch, builds):
    _stored(monkeypatch, None)

    assert asyncio.run(load_slate_json(None, 2026, 6, production=True)) is None
    assert builds == []


def test_dev_without_a_stored_slate_builds_live(monkeypatch, builds):
    _stored(monkeypatch, None)

    served = asyncio.run(load_slate_json(None, 2026, 6, production=False))

    assert served == slate_json(_sample())
    assert builds == [(2026, 6)]


def test_stored_text_decodes_to_the_body_the_route_sent():
    body = slate_json(_sample())

    assert json.loads(_as_jsonb_text(body).encode()) == json.loads(body)
    assert "lineCount" in json.loads(body)


class TestParseWeeks:
    def test_current_refreshes_previous_current_and_next_week(self):
        assert parse_weeks("current", 6) == [5, 6, 7]

    def test_week_one_has_no_week_before(self):
        assert parse_weeks("current", 1) == [1, 2]

    def test_last_week_has_no_week_after(self):
        assert parse_weeks("current", 18) == [17, 18]

    def test_current_needs_a_loaded_week(self):
        with pytest.raises(ValueError):
            parse_weeks("current", None)

    def test_all_is_the_regular_season(self):
        assert parse_weeks("all", None) == list(range(1, 19))

    def test_a_list_is_sorted_and_deduplicated(self):
        assert parse_weeks("6,5, 6", None) == [5, 6]

    @pytest.mark.parametrize("value", ["0", "19", "", "5,x"])
    def test_out_of_range_or_unreadable_weeks_fail(self, value):
        with pytest.raises(ValueError):
            parse_weeks(value, None)


def test_the_summary_names_games_lines_and_size():
    slate = _sample()

    assert summary(slate, 2_500_000) == (
        f"NFL slate {slate.season} week {slate.week}: {slate.game_count} games, "
        f"{slate.line_count} lines, 2.5 MB"
    )
