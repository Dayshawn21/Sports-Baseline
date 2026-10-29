"""The job freezes after enrichment and reports start-boundary rejects honestly."""
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.ingest import prop_snapshots as ingest
from app.repositories.prop_snapshots import SnapshotInsertCounts
from app.repositories.props import Prop
from app.schemas.props import PropLine
from app.services.tennis.prop_sim import SimInputs
from app.services.tennis.prop_snapshots import SNAPSHOT_ELIGIBILITY_POLICY

CAPTURE = datetime(2026, 10, 18, 12, tzinfo=UTC)
START = CAPTURE + timedelta(hours=2)
INPUTS = SimInputs({}, {}, {}, {}, {})


def _prop(prop_id: int) -> Prop:
    return Prop(
        id=prop_id, player_id=11, player_name="A Player", match_id=21, source="prizepicks",
        stat_type="Total Games", line=Decimal("21.5"), odds_type="standard",
        fetched_at=CAPTURE - timedelta(hours=1), start_time=START,
        source_start_time=START, match_start_time=START, match_status="scheduled",
    )


def _line(prop: Prop) -> PropLine:
    return PropLine(
        id=prop.id, player_id=prop.player_id, player_name=prop.player_name, match_id=prop.match_id,
        source=prop.source, stat_type=prop.stat_type, line=prop.line, odds_type=prop.odds_type,
        fetched_at=prop.fetched_at, start_time=prop.start_time,
        recommendation="UNDER", confidence=None, hit_probability=0.6,
        p_over=0.4, p_under=0.6, p_push=0.0, stat_avg=20.9, ev_pct=3.0,
        projection_inputs={"projection_source": "market_total"},
    )


class _Session:
    committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def commit(self):
        self.committed = True


def _wire(monkeypatch: pytest.MonkeyPatch, props: list[Prop], inserts: list[list]) -> tuple[_Session, list[str]]:
    session = _Session()
    stages: list[str] = []
    v3 = [_line(prop) for prop in props]
    v4 = [line.model_copy(update={"stat_avg": 21.7, "projection_inputs": {"sim_seed": 1.0}}) for line in v3]

    async def load(db, source):
        assert db is session and source == "prizepicks"
        stages.append("load")
        return props

    async def load_inputs(db, loaded):
        assert db is session and loaded == props
        stages.append("inputs")
        return INPUTS

    def enrich(loaded, *loaded_inputs):
        assert loaded == props and loaded_inputs == (
            INPUTS.opponent_ids, INPUTS.rolling_stats, INPUTS.prediction_probs, INPUTS.market_probs,
            INPUTS.market_totals,
        )
        stages.append("v3")
        return v3

    def simulate(loaded, lines, inputs):
        assert loaded == props and lines is v3 and inputs is INPUTS
        stages.append("v4")
        return v4

    class Clock:
        @staticmethod
        def now(tz):
            assert tz is UTC and stages == ["load", "inputs", "v3", "v4"]
            stages.append("capture")
            return CAPTURE

    async def insert(db, snapshots):
        assert db is session
        inserts.append(snapshots)
        return SnapshotInsertCounts(inserted=1, already_stored=1, rejected_started=1)

    monkeypatch.setattr(ingest, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingest, "get_today_props", load)
    monkeypatch.setattr(ingest, "load_sim_inputs", load_inputs)
    monkeypatch.setattr(ingest, "enrich_with", enrich)
    monkeypatch.setattr(ingest, "sim_prop_lines", simulate)
    monkeypatch.setattr(ingest, "datetime", Clock)
    monkeypatch.setattr(ingest, "insert_prop_projection_snapshots", insert)
    return session, stages


def _props() -> list[Prop]:
    return [
        _prop(1), _prop(2),
        replace(_prop(3), source_start_time=CAPTURE + timedelta(seconds=1)),
        replace(_prop(4), match_status="live"),
        replace(_prop(5), match_start_time=CAPTURE - timedelta(seconds=1)),
    ]


def test_each_eligible_line_is_stored_once_per_version(monkeypatch):
    inserts: list[list] = []
    session, _ = _wire(monkeypatch, _props(), inserts)

    counts = asyncio.run(ingest.snapshot_props())

    assert session.committed
    v3, v4 = inserts
    assert [snap.prop_id for snap in v3] == [snap.prop_id for snap in v4] == [1, 2, 3]
    assert {snap.projection_version for snap in v3} == {"props-v3"}
    assert {snap.projection_version for snap in v4} == {"props-v4"}
    for old, new in zip(v3, v4):
        assert old.snapshot_at == new.snapshot_at == CAPTURE
        assert (old.stat_avg, new.stat_avg) == (20.9, 21.7)
        assert new.projection_inputs["snapshot_eligibility_policy"] == SNAPSHOT_ELIGIBILITY_POLICY
        assert new.projection_inputs["sim_seed"] == 1.0
    assert counts == {
        "loaded": 5, "eligible": 3,
        "props-v3_eligible": 3, "props-v3_inserted": 1, "props-v3_already_stored": 1,
        "props-v3_skipped_started_at_insert": 1,
        "props-v4_eligible": 3, "props-v4_inserted": 1, "props-v4_already_stored": 1,
        "props-v4_skipped_started_at_insert": 1,
        "skipped_live": 1, "skipped_started": 1,
    }


def test_a_dry_run_inserts_nothing_and_commits_nothing(monkeypatch):
    inserts: list[list] = []
    session, stages = _wire(monkeypatch, _props(), inserts)

    counts = asyncio.run(ingest.snapshot_props(dry_run=True))

    assert inserts == [] and not session.committed
    assert stages == ["load", "inputs", "v3", "v4", "capture"]
    assert counts == {
        "loaded": 5, "eligible": 3, "props-v3_eligible": 3, "props-v4_eligible": 3,
        "skipped_live": 1, "skipped_started": 1,
    }
