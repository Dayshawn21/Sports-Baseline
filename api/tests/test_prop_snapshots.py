"""A snapshot is a pre-match prediction only if it was taken before the match began."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.repositories.props import Prop
from app.schemas.props import PropLine
from app.services.tennis.prop_snapshots import PROJECTION_VERSION, skip_reason, to_snapshot

NOW = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
START = NOW + timedelta(hours=5)


def _prop(**kw) -> Prop:
    fields = dict(
        id=7, player_id=11, player_name="A Player", match_id=21, source="prizepicks",
        stat_type="Total Games", line=Decimal("21.5"), odds_type="standard",
        fetched_at=NOW - timedelta(hours=1), start_time=START,
        raw_json={"attributes": {"is_live": False, "in_game": False}},
    )
    fields.update(kw)
    return Prop(**fields)


def _line(**kw) -> PropLine:
    fields = dict(
        id=7, player_id=11, player_name="A Player", match_id=21, source="prizepicks",
        stat_type="Total Games", line=Decimal("21.5"), odds_type="standard",
        fetched_at=NOW - timedelta(hours=1), start_time=START,
        p_over=0.44, p_under=0.56, p_push=0.0, confidence="LEAN", recommendation="UNDER",
        stat_avg=20.9, ev_pct=-3.0, hit_probability=0.56, break_even_pct=57.7,
        matches_count=18, market_total_games=21.5, projection_status="ok",
        projection_inputs={"projection_source": "market_total"}, data_quality_flags=["small_sample"],
    )
    fields.update(kw)
    return PropLine(**fields)


class TestSkipReason:
    def test_an_upcoming_linked_prizepicks_line_is_eligible(self):
        assert skip_reason(_prop(), _line(), NOW) is None

    @pytest.mark.parametrize(
        ("line_fields", "reason"),
        [
            ({"source": "draftkings"}, "not_prizepicks"),
            ({"player_id": None}, "missing_player"),
            ({"match_id": None}, "missing_match"),
            ({"start_time": None}, "no_start_time"),
            ({"line": None}, "no_line"),
            ({"start_time": NOW - timedelta(minutes=1)}, "started"),
        ],
    )
    def test_each_skip_reason(self, line_fields, reason):
        assert skip_reason(_prop(), _line(**line_fields), NOW) == reason

    def test_a_start_exactly_now_has_started(self):
        assert skip_reason(_prop(), _line(start_time=NOW), NOW) == "started"

    @pytest.mark.parametrize("flag", ["is_live", "in_game"])
    def test_a_live_flag_wins_even_when_the_stored_start_is_later(self, flag):
        prop = _prop(raw_json={"attributes": {flag: True}})
        assert skip_reason(prop, _line(), NOW) == "live"

    def test_a_prop_with_no_raw_payload_is_not_live(self):
        assert skip_reason(_prop(raw_json=None), _line(), NOW) is None


class TestToSnapshot:
    def test_carries_the_page_projection(self):
        snap = to_snapshot(_line())
        assert snap.projection_version == PROJECTION_VERSION
        assert (snap.prop_id, snap.player_id, snap.match_id) == (7, 11, 21)
        assert snap.line == 21.5 and isinstance(snap.line, float)
        assert (snap.recommendation, snap.confidence, snap.hit_probability) == ("UNDER", "LEAN", 0.56)
        assert snap.projection_inputs == {"projection_source": "market_total"}
        assert snap.data_quality_flags == ["small_sample"]

    def test_a_relinked_prop_keeps_the_match_the_page_projected_against(self):
        # get_today_props re-resolves stale links, so the PropLine's match wins.
        assert to_snapshot(_line(match_id=99)).match_id == 99

    def test_an_ineligible_line_is_refused(self):
        with pytest.raises(ValueError):
            to_snapshot(_line(match_id=None))

    def test_a_pass_row_with_no_recommendation_still_maps(self):
        snap = to_snapshot(_line(recommendation=None, confidence=None, hit_probability=None,
                                 projection_status="unsupported_stat"))
        assert snap.recommendation is None and snap.projection_status == "unsupported_stat"
