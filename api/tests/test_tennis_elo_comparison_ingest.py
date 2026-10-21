import asyncio
from dataclasses import asdict, replace
from datetime import timedelta
import json
from types import SimpleNamespace

import pytest

from app.ingest import tennis_elo as ratings
from app.ingest import tennis_elo_comparison as ingest
from app.services.tennis.elo_comparison import ComparisonPlan
from app.repositories.tennis_elo_comparison import FreezeCycle
from tests.test_tennis_elo_comparison import NOW, Registry, candidates, config


def reviewed_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(ratings, "_now", lambda: NOW)
    values = list(candidates().values())
    data = b"synthetic source contract fixture"
    digest = ratings._sha(data)
    ratings._immutable_write(tmp_path / "files" / f"{digest}.csv", data)
    files = [ratings.DownloadedFile(s, digest, NOW - timedelta(hours=2)) for s in ratings.source_files(NOW.date())]
    manifest = {
        "source": ratings.SOURCE, "as_of_date": NOW.date().isoformat(),
        "computed_at": values[0].computed_at.isoformat(), "identity_sha256": "d" * 64,
        "mapping_sha256": ratings._sha(ratings._canonical_json(
            sorted(((s.provider_namespace, s.provider_player_id), s.player_id) for s in values))),
        "ratings_sha256": ratings._sha(ratings._canonical_json(
            [asdict(replace(s, manifest_sha256="0" * 64)) for s in values])),
        "files": ratings._file_records(files),
    }
    contents = ratings._canonical_json(manifest)
    sha = ratings._sha(contents)
    ratings._immutable_write(tmp_path / "manifests" / f"{sha}.json", contents)
    return [replace(s, manifest_sha256=sha) for s in values]


def test_complete_snapshot_reproduces_manifest_in_any_database_row_order(tmp_path, monkeypatch):
    values = reviewed_snapshot(tmp_path, monkeypatch)
    assert ingest.validated_candidates(list(reversed(values)), NOW, "d" * 64, tmp_path) == {s.player_id: s for s in values}


@pytest.mark.parametrize("change", ["missing", "added", "rating", "duplicate", "identity", "future", "corrupt_file"])
def test_partial_changed_or_unavailable_snapshot_is_rejected(tmp_path, monkeypatch, change):
    values = reviewed_snapshot(tmp_path, monkeypatch)
    identity = "d" * 64
    if change == "missing": values.pop()
    if change == "added": values.append(replace(values[0], player_id=99, provider_player_id="A99"))
    if change == "rating": values[0] = replace(values[0], rating=replace(values[0].rating, overall=1800.))
    if change == "duplicate": values.append(values[0])
    if change == "identity": identity = "f" * 64
    if change == "future": values[0] = replace(values[0], computed_at=NOW + timedelta(minutes=1))
    if change == "corrupt_file": next((tmp_path / "files").iterdir()).write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        ingest.validated_candidates(values, NOW, identity, tmp_path)


def setup_run(tmp_path, monkeypatch, active=True, existing=None):
    cfg = config(active=active)
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps({**cfg.pins(), "activated_at": cfg.activated_at.isoformat() if cfg.activated_at else None}))
    state = SimpleNamespace(writes=[], commits=0, db_calls=0)

    class Session:
        async def __aenter__(self):
            state.db_calls += 1
            return self

        async def __aexit__(self, *_args): pass

        async def commit(self): state.commits += 1

    async def continuity(*args): pass
    async def cycle(*args): return existing
    async def upcoming(*args): return []
    async def snapshots(*args, **kwargs): return []
    async def ids(*args): return set()
    async def write(db, ledger, pairs):
        state.writes.append((ledger, pairs))
        return len(pairs)

    monkeypatch.setattr(ingest, "ModelRegistry", lambda path: Registry())
    monkeypatch.setattr(ingest.ratings_cli, "load_identity_registry", lambda: SimpleNamespace(sha256="d" * 64))
    monkeypatch.setattr(ingest, "SessionLocal", Session)
    monkeypatch.setattr(ingest, "_now", lambda: NOW)
    monkeypatch.setattr(ingest, "check_experiment_continuity", continuity)
    monkeypatch.setattr(ingest, "get_cycle_attempt_count", cycle)
    monkeypatch.setattr(ingest.match_repo, "get_upcoming", upcoming)
    monkeypatch.setattr(ingest, "get_daily_snapshots", snapshots)
    monkeypatch.setattr(ingest, "get_frozen_match_ids", ids)
    monkeypatch.setattr(ingest, "get_resulted_match_ids", ids)
    monkeypatch.setattr(ingest, "freeze_cycle", write)
    return path, state


def test_default_preview_has_no_database_writes_or_commits(tmp_path, monkeypatch, capsys):
    path, state = setup_run(tmp_path, monkeypatch, active=False)
    result = asyncio.run(ingest.run(experiment_path=path, cache_dir=tmp_path))
    assert not result.active and result.inserted == 0 and result.plan_path.exists()
    assert state.writes == [] and state.commits == 0
    assert "DRY RUN" in capsys.readouterr().out


def test_explicit_write_can_record_empty_coverage_without_touching_production(tmp_path, monkeypatch):
    path, state = setup_run(tmp_path, monkeypatch)
    result = asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))
    assert result.inserted == 0 and len(state.writes) == 1 and state.commits == 1


def test_write_cannot_activate_experiment_or_bypass_first_full_day(tmp_path, monkeypatch):
    path, state = setup_run(tmp_path, monkeypatch, active=False)
    with pytest.raises(ValueError, match="activation"):
        asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))
    assert state.db_calls == 0 and state.writes == []
    record = json.loads(path.read_text())
    record["activated_at"] = NOW.isoformat()
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="first full UTC day"):
        asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))


def test_existing_cycle_reuses_frozen_ledger_before_loading_live_inputs(tmp_path, monkeypatch):
    path, state = setup_run(tmp_path, monkeypatch, existing=12)
    async def forbidden(*args): raise AssertionError("live inputs loaded on retry")
    monkeypatch.setattr(ingest.match_repo, "get_upcoming", forbidden)
    result = asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))
    assert result.reused and result.attempted == 12
    assert state.writes == [] and state.commits == 0


def test_incomplete_snapshot_cannot_create_partial_pairs(tmp_path, monkeypatch):
    from tests.test_tennis_elo_comparison import batch, match
    path, state = setup_run(tmp_path, monkeypatch)
    async def upcoming(*args): return [match()]
    async def load(*args): return batch()
    monkeypatch.setattr(ingest.match_repo, "get_upcoming", upcoming)
    monkeypatch.setattr(ingest, "load_prediction_batch", load)
    result = asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))
    ledger, pairs = state.writes[0]
    assert result.inserted == 0 and pairs == () and ledger.attempts[0].incumbent_eligible
    assert ledger.attempts[0].reason == "missing_or_invalid_daily_snapshot"


def test_utc_rollover_fails_before_coverage_or_pair_write(tmp_path, monkeypatch):
    path, state = setup_run(tmp_path, monkeypatch)
    times = iter((NOW, NOW + timedelta(days=1)))
    monkeypatch.setattr(ingest, "_now", lambda: next(times))
    with pytest.raises(ValueError, match="UTC day rolled over"):
        asyncio.run(ingest.run(dry_run=False, experiment_path=path, cache_dir=tmp_path))
    assert state.writes == [] and state.commits == 0


@pytest.mark.parametrize("activation_today", [False, True])
def test_scheduled_inactive_or_partial_first_day_skips_without_database(tmp_path, monkeypatch, capsys, activation_today):
    path, state = setup_run(tmp_path, monkeypatch, active=False)
    if activation_today:
        record = json.loads(path.read_text())
        record["activated_at"] = NOW.isoformat()
        path.write_text(json.dumps(record))
    result = asyncio.run(ingest.run(dry_run=False, scheduled=True, experiment_path=path, cache_dir=tmp_path))
    assert not result.active and result.inserted == 0 and result.plan_path is None
    assert state.db_calls == 0 and state.commits == 0 and state.writes == []
    assert "Freeze skipped" in capsys.readouterr().out


def test_active_scheduled_cache_miss_retains_eligible_denominator(tmp_path, monkeypatch, capsys):
    from tests.test_tennis_elo_comparison import batch, match
    path, state = setup_run(tmp_path, monkeypatch)
    async def upcoming(*args): return [match()]
    async def load(*args): return batch()
    monkeypatch.setattr(ingest.match_repo, "get_upcoming", upcoming)
    monkeypatch.setattr(ingest, "load_prediction_batch", load)
    result = asyncio.run(ingest.run(dry_run=False, scheduled=True, experiment_path=path, cache_dir=tmp_path))
    ledger, pairs = state.writes[0]
    assert result.active and result.inserted == 0 and pairs == ()
    assert state.commits == 1 and ledger.attempts[0].incumbent_eligible
    assert not ledger.attempts[0].candidate_available
    assert "missing_or_invalid_daily_snapshot" in capsys.readouterr().out


def test_shared_cache_validates_on_fresh_runner_without_recomputation(tmp_path, monkeypatch, capsys):
    import shutil
    producer, consumer = tmp_path / "producer", tmp_path / "consumer"
    values = reviewed_snapshot(producer, monkeypatch)
    _, state = setup_run(tmp_path, monkeypatch)
    for directory in ("files", "manifests"):
        shutil.copytree(producer / directory, consumer / directory)
    async def snapshots(*args, **kwargs): return values
    monkeypatch.setattr(ingest, "get_daily_snapshots", snapshots)
    asyncio.run(ingest.check_daily_snapshot(cache_dir=consumer))
    assert state.commits == 0 and state.writes == []
    assert "2 players" in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["missing_file", "missing_roster", "rollover"])
def test_cache_handoff_rejects_incomplete_or_wrong_day_inputs(tmp_path, monkeypatch, failure):
    values = reviewed_snapshot(tmp_path, monkeypatch)
    _, state = setup_run(tmp_path, monkeypatch)
    if failure == "missing_file":
        next((tmp_path / "files").iterdir()).unlink()
    if failure == "missing_roster":
        values.pop()
    if failure == "rollover":
        times = iter((NOW, NOW + timedelta(days=1)))
        monkeypatch.setattr(ingest, "_now", lambda: next(times))
    async def snapshots(*args, **kwargs): return values
    monkeypatch.setattr(ingest, "get_daily_snapshots", snapshots)
    with pytest.raises((ValueError, OSError)):
        asyncio.run(ingest.check_daily_snapshot(cache_dir=tmp_path))
    assert state.commits == 0 and state.writes == []
