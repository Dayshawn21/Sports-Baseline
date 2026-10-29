"""A snapshot is a pre-match prediction only if it was taken before the match began."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.repositories.props import Prop
from app.routers.props import _enrich
from app.schemas.props import PropLine
from app.services.tennis.prop_snapshots import (
    PROJECTION_VERSION, SIM_PROJECTION_VERSION, SNAPSHOT_ELIGIBILITY_POLICY, skip_reason, to_snapshot,
)
from tests.test_props_audit_projection import _stats

NOW = datetime(2026, 9, 25, 13, 30, tzinfo=timezone.utc)
START = NOW + timedelta(hours=5)


def _prop(**kw) -> Prop:
    fields = dict(
        id=7, player_id=11, player_name="A Player", match_id=21, source="prizepicks",
        stat_type="Total Games", line=Decimal("21.5"), odds_type="standard",
        fetched_at=NOW - timedelta(hours=1), start_time=START,
        source_start_time=START, match_start_time=START, match_status="scheduled",
        raw_json={"attributes": {"is_live": False, "in_game": False}},
    )
    fields.update(kw)
    return Prop(**fields)


def _line(**kw) -> PropLine:
    fields = dict(
        id=7, player_id=11, player_name="A Player", match_id=21, source="prizepicks",
        stat_type="Total Games", line=Decimal("21.5"), odds_type="standard",
        fetched_at=NOW - timedelta(hours=1), start_time=START,
        p_over=0.44, p_under=0.56, p_push=0.0, confidence=None, recommendation="UNDER",
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

    @pytest.mark.parametrize(
        ("status", "reason"),
        [("live", "live"), ("completed", "match_finished"), ("cancelled", "match_finished")],
    )
    def test_known_match_status_overrides_future_starts_and_old_non_live_payload(self, status, reason):
        assert skip_reason(_prop(match_status=status), _line(), NOW) == reason

    def test_an_invalid_match_link_cannot_be_frozen(self):
        assert skip_reason(_prop(match_link_invalid=True), _line(), NOW) == "match_link_invalid"

    @pytest.mark.parametrize("field", ["source_start_time", "match_start_time"])
    @pytest.mark.parametrize("offset", [timedelta(minutes=-1), timedelta(0)])
    def test_either_start_at_or_before_capture_overrides_the_future_display_time(self, field, offset):
        assert skip_reason(_prop(**{field: NOW + offset}), _line(), NOW) == "started"

    @pytest.mark.parametrize("field", ["source_start_time", "match_start_time"])
    def test_one_missing_start_can_use_the_other(self, field):
        assert skip_reason(_prop(**{field: None}), _line(), NOW) is None

    def test_a_future_display_time_cannot_replace_both_missing_source_times(self):
        prop = _prop(source_start_time=None, match_start_time=None)
        assert skip_reason(prop, _line(), NOW) == "no_start_time"

    def test_a_delay_does_not_override_a_past_provider_start(self):
        prop = _prop(source_start_time=NOW - timedelta(hours=1), match_start_time=START)
        assert skip_reason(prop, _line(start_time=START), NOW) == "started"

    def test_different_future_starts_are_eligible(self):
        prop = _prop(source_start_time=START, match_start_time=START + timedelta(hours=2))
        assert skip_reason(prop, _line(), NOW) is None


class TestToSnapshot:
    def test_an_enriched_line_is_frozen_with_its_probabilities_and_no_tier(self):
        prop = _prop(best_of=3, player_tour="ATP")
        line = _enrich(prop, _stats(11), _stats(12), 0.6, market_total_games=21.5)
        snap = to_snapshot(prop, line, NOW)
        assert snap.confidence is None
        assert snap.p_over is not None and (snap.p_over, snap.p_under) == (line.p_over, line.p_under)
        assert snap.recommendation is not None and snap.recommendation == line.recommendation

    def test_the_page_keeps_v3_and_the_simulation_writes_v4(self):
        assert (PROJECTION_VERSION, SIM_PROJECTION_VERSION) == ("props-v3", "props-v4")
        snap = to_snapshot(_prop(), _line(stat_avg=21.7), NOW, SIM_PROJECTION_VERSION)
        assert (snap.projection_version, snap.stat_avg) == ("props-v4", 21.7)

    def test_carries_the_page_projection(self):
        line = _line()
        snap = to_snapshot(_prop(), line, NOW)
        assert snap.projection_version == PROJECTION_VERSION
        assert (snap.prop_id, snap.player_id, snap.match_id) == (7, 11, 21)
        assert snap.line == 21.5 and isinstance(snap.line, float)
        assert (snap.recommendation, snap.confidence, snap.hit_probability) == ("UNDER", None, 0.56)
        assert (snap.p_over, snap.p_under) == (0.44, 0.56)
        assert snap.snapshot_at == NOW
        assert snap.projection_inputs == {
            "projection_source": "market_total",
            "snapshot_eligibility_policy": SNAPSHOT_ELIGIBILITY_POLICY,
            "source_start_time": START.isoformat(),
            "match_start_time": START.isoformat(),
            "match_status_at_capture": "scheduled",
        }
        assert line.projection_inputs == {"projection_source": "market_total"}
        assert snap.data_quality_flags == ["small_sample"]

    def test_a_relinked_prop_keeps_the_match_the_page_projected_against(self):
        # get_today_props re-resolves stale links, so the PropLine's match wins.
        assert to_snapshot(_prop(match_id=99), _line(match_id=99), NOW).match_id == 99

    def test_an_ineligible_line_is_refused(self):
        with pytest.raises(ValueError):
            to_snapshot(_prop(), _line(match_id=None), NOW)

    def test_a_pass_row_with_no_recommendation_still_maps(self):
        snap = to_snapshot(_prop(), _line(recommendation=None, confidence=None, hit_probability=None,
                                         projection_status="unsupported_stat"), NOW)
        assert snap.recommendation is None and snap.projection_status == "unsupported_stat"

    @pytest.mark.parametrize("field", ["source_start_time", "match_start_time"])
    def test_missing_timing_provenance_is_absent_instead_of_fabricated(self, field):
        snap = to_snapshot(_prop(**{field: None}), _line(), NOW)
        assert field not in snap.projection_inputs

    def test_a_missing_match_status_is_preserved_as_unknown(self):
        snap = to_snapshot(_prop(match_status=None), _line(), NOW)
        assert "match_status_at_capture" not in snap.projection_inputs

    @pytest.mark.parametrize("fields", [{"id": 88}, {"player_id": 44}, {"match_id": 99}])
    def test_source_context_from_another_resolved_line_is_refused(self, fields):
        with pytest.raises(ValueError, match="same resolved line"):
            to_snapshot(_prop(**fields), _line(), NOW)

    def test_serializing_cannot_bypass_the_live_guard(self):
        with pytest.raises(ValueError, match="live"):
            to_snapshot(_prop(match_status="live"), _line(), NOW)

    def test_capture_clock_must_be_timezone_aware(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            to_snapshot(_prop(), _line(), NOW.replace(tzinfo=None))

    @pytest.mark.parametrize("field", ["source_start_time", "match_start_time"])
    def test_earlier_correction_that_crosses_capture_cannot_be_frozen(self, field):
        with pytest.raises(ValueError, match="started"):
            to_snapshot(_prop(**{field: NOW}), _line(), NOW)

    def test_a_delay_keeps_both_observed_times_not_just_the_later_one(self):
        delayed = START + timedelta(hours=3)
        snap = to_snapshot(_prop(match_start_time=delayed), _line(), NOW)
        assert snap.projection_inputs["source_start_time"] == START.isoformat()
        assert snap.projection_inputs["match_start_time"] == delayed.isoformat()
