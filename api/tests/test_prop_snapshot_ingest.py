"""The job freezes after enrichment and reports start-boundary rejects honestly."""
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.ingest import prop_snapshots as ingest
from app.repositories.prop_snapshots import SnapshotInsertCounts
from app.repositories.props import Prop
from app.schemas.props import PropLine
from app.services.tennis.prop_snapshots import SNAPSHOT_ELIGIBILITY_POLICY

CAPTURE = datetime(2026, 10, 18, 12, tzinfo=UTC)
START = CAPTURE + timedelta(hours=2)


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
        recommendation="UNDER", confidence="LEAN", hit_probability=0.6,
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


def test_freeze_clock_and_counts_follow_the_real_job_path_with_mocked_io(monkeypatch):
    session = _Session()
    props = [
        _prop(1), _prop(2),
        replace(_prop(3), source_start_time=CAPTURE + timedelta(seconds=1)),
        replace(_prop(4), match_status="live"),
        replace(_prop(5), match_start_time=CAPTURE - timedelta(seconds=1)),
    ]
    lines = [_line(prop) for prop in props]
    stages = []

    async def load(db, source):
        assert db is session and source == "prizepicks"
        stages.append("load")
        return props

    async def enrich(db, loaded):
        assert db is session and loaded == props
        stages.append("enrich")
        return lines

    class Clock:
        @staticmethod
        def now(tz):
            assert tz is UTC and stages == ["load", "enrich"]
            stages.append("capture")
            return CAPTURE

    async def insert(db, snapshots):
        assert db is session and stages == ["load", "enrich", "capture"]
        assert [snap.prop_id for snap in snapshots] == [1, 2, 3]
        for snap in snapshots:
            assert snap.snapshot_at == CAPTURE
            assert snap.projection_inputs["snapshot_eligibility_policy"] == SNAPSHOT_ELIGIBILITY_POLICY
            line = lines[snap.prop_id - 1]
            for field in ("recommendation", "confidence", "hit_probability", "p_over", "p_under", "p_push", "stat_avg", "ev_pct"):
                assert getattr(snap, field) == getattr(line, field)
        return SnapshotInsertCounts(inserted=1, already_stored=1, rejected_started=1)

    monkeypatch.setattr(ingest, "SessionLocal", lambda: session)
    monkeypatch.setattr(ingest, "get_today_props", load)
    monkeypatch.setattr(ingest, "enrich_props", enrich)
    monkeypatch.setattr(ingest, "datetime", Clock)
    monkeypatch.setattr(ingest, "insert_prop_projection_snapshots", insert)

    counts = asyncio.run(ingest.snapshot_props())

    assert session.committed
    assert counts == {
        "loaded": 5, "eligible": 3, "inserted": 1, "already_stored": 1,
        "skipped_started_at_insert": 1, "skipped_live": 1, "skipped_started": 1,
    }
    assert all(line.projection_inputs == {"projection_source": "market_total"} for line in lines)
