import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest

from app.backtest import tennis_elo as cli
from app.repositories.tennis_elo_report import ReportInputs
from app.services.tennis.elo_comparison import ExperimentConfig
from tests.test_tennis_elo_report import FIRST, NOW, PINS, observation, result, series


def setup(tmp_path, monkeypatch, daily=None, active=True):
    config = ExperimentConfig(PINS.identity_sha256, PINS.coefficient_sha256, PINS.gate_sha256,
                              PINS.model_versions, datetime.combine(FIRST, datetime.min.time(), timezone.utc)
                              - timedelta(days=1) if active else None)
    config_path = tmp_path / "experiment.json"
    config_path.write_text(json.dumps({**config.pins(), "activated_at": config.activated_at.isoformat()
                                     if config.activated_at else None}))
    cases = [replace(c, experiment_sha256=config.sha256) for c in series(daily)]
    observations = [replace(observation(c), experiment_sha256=config.sha256) for c in cases]
    state = SimpleNamespace(inputs=0, results=0, losses=0, invalid=0, sql=[], cases=cases,
                            observations=observations, outcomes={c.match_id: result(c) for c in cases})

    class Session:
        async def __aenter__(self): return self
        async def __aexit__(self, *_args): pass
        async def execute(self, sql): state.sql.append(str(sql))

    async def load_inputs(db, *, include_probabilities=False):
        state.inputs += 1
        values = state.cases if include_probabilities else [replace(c, probabilities=None) for c in state.cases]
        return ReportInputs(tuple(values), tuple(state.observations), state.invalid)

    async def load_results(db, match_ids):
        state.results += 1
        return {mid: state.outcomes[mid] for mid in match_ids if mid in state.outcomes}

    original_score = cli.score_sample
    def score(selection, cov):
        state.losses += 1
        sample_path = tmp_path / "reports" / selection.group / "sample.json"
        assert sample_path.exists(), "Loss calculation preceded immutable sample lock"
        locked = json.loads(sample_path.read_bytes())
        assert locked["payload"]["case_ids"] == [c.match_id for c in selection.cases]
        assert locked["sha256"] == cli._sha(locked["payload"])
        return original_score(selection, cov)

    monkeypatch.setattr(cli, "SessionLocal", Session)
    monkeypatch.setattr(cli, "get_report_inputs", load_inputs)
    monkeypatch.setattr(cli, "get_report_results", load_results)
    monkeypatch.setattr(cli, "score_sample", score)
    monkeypatch.setattr(cli, "_now", lambda: NOW)
    args = {"experiment_path": config_path, "report_dir": tmp_path / "reports"}
    return args, state, config


def test_default_count_never_reads_winners_or_computes_losses_even_above_floor(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    def forbidden(*args): raise AssertionError("Scoring path reached by count mode")
    monkeypatch.setattr(cli, "get_report_results", forbidden)
    monkeypatch.setattr(cli, "score_sample", forbidden)
    output = asyncio.run(cli.run(**args))
    assert "ATP: accruing; frozen=300, mature=300" in output
    assert "Sample count/day floor met" in output and "log_loss" not in output
    assert not args["report_dir"].exists()
    assert state.results == state.losses == 0
    assert len(state.sql) == 1 and "READ ONLY" in state.sql[0]


def test_under_floor_score_request_reads_no_outcomes_and_locks_no_sample(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch, daily=[22] * 13 + [13])
    output = asyncio.run(cli.run(score=True, group="ATP", **args))
    assert "accruing" in output and state.results == state.losses == 0
    assert not (args["report_dir"] / "ATP" / "sample.json").exists()


def test_inactive_experiment_cannot_score_or_touch_database(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch, active=False)
    output = asyncio.run(cli.run(score=True, group="ATP", **args))
    assert "inactive" in output and state.inputs == state.results == state.losses == 0
    assert not args["report_dir"].exists()


def test_scoring_requires_one_explicit_known_group(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    for group in (None, "WTA_125"):
        with pytest.raises(ValueError):
            asyncio.run(cli.run(score=True, group=group, **args))
    assert state.inputs == 0


def test_first_sample_locks_full_prefix_before_losses_then_reuses_report_without_database(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch, daily=[22] * 13 + [15, 40])
    output = asyncio.run(cli.run(score=True, group="ATP", **args))
    payload = json.loads(output)
    assert payload["result"]["cases"] == 301 and payload["result"]["verdict"] == "pass"
    assert state.results == state.losses == 1
    assert (args["report_dir"] / "ATP" / "sample.json").exists()
    def forbidden(*args, **kwargs): raise AssertionError("Locked report recomputed or database loaded")
    monkeypatch.setattr(cli, "SessionLocal", forbidden)
    monkeypatch.setattr(cli, "score_sample", forbidden)
    monkeypatch.setattr(cli, "_now", lambda: NOW + timedelta(days=100))
    assert asyncio.run(cli.run(score=True, group="ATP", **args)) == output


def test_crash_after_lock_resumes_only_from_copied_inputs_not_changed_results(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    score = cli.score_sample
    def crash(*args): raise RuntimeError("simulated crash after lock")
    monkeypatch.setattr(cli, "score_sample", crash)
    with pytest.raises(RuntimeError, match="after lock"):
        asyncio.run(cli.run(score=True, group="ATP", **args))
    sample = args["report_dir"] / "ATP" / "sample.json"
    assert sample.exists() and not (sample.parent / "report.json").exists()
    original_bytes = sample.read_bytes()
    state.outcomes.clear()
    state.cases.clear()
    def forbidden(*args): raise AssertionError("Database queried after sample lock")
    monkeypatch.setattr(cli, "SessionLocal", forbidden)
    monkeypatch.setattr(cli, "score_sample", score)
    output = asyncio.run(cli.run(score=True, group="ATP", **args))
    assert json.loads(output)["result"]["cases"] == 300
    assert sample.read_bytes() == original_bytes and state.results == 1


def test_unresolved_cohort_blocks_without_loss_or_sample_lock(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch, daily=[22] * 15)
    del state.outcomes[23]
    output = asyncio.run(cli.run(score=True, group="ATP", **args))
    assert "blocked UTC day=2027-01-02" in output and state.losses == 0
    assert not (args["report_dir"] / "ATP" / "sample.json").exists()


def test_missing_coverage_ledger_blocks_before_lock_or_losses(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    state.observations.clear()
    with pytest.raises(ValueError, match="coverage ledger"):
        asyncio.run(cli.run(score=True, group="ATP", **args))
    assert state.losses == 0 and not (args["report_dir"] / "ATP" / "sample.json").exists()


def test_invalid_frozen_payloads_require_review_without_loading_outcomes(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    state.invalid = 1
    with pytest.raises(ValueError, match="Invalid frozen"):
        asyncio.run(cli.run(score=True, group="ATP", **args))
    assert state.results == state.losses == 0


def test_count_after_final_verdict_still_reads_no_outcomes_and_prints_no_losses(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    asyncio.run(cli.run(score=True, group="ATP", **args))
    def forbidden(*args, **kwargs): raise AssertionError("Count read outcomes or rescored")
    monkeypatch.setattr(cli, "get_report_results", forbidden)
    monkeypatch.setattr(cli, "score_sample", forbidden)
    output = asyncio.run(cli.run(**args))
    assert "ATP: locked (counts only)" in output and "log_loss" not in output and "pass" not in output
    assert state.results == state.losses == 1


def test_artifacts_reject_tampering_rule_drift_and_second_sample(tmp_path, monkeypatch):
    args, state, config = setup(tmp_path, monkeypatch)
    asyncio.run(cli.run(score=True, group="ATP", **args))
    sample = args["report_dir"] / "ATP" / "sample.json"
    record = json.loads(sample.read_bytes())
    with pytest.raises(ValueError, match="already locked"):
        cli._write_once(sample, {"changed": True})
    record["payload"]["case_ids"].append(99999)
    sample.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="hash mismatch"):
        asyncio.run(cli.run(score=True, group="ATP", **args))


def test_changed_rule_cannot_reinterpret_locked_sample(tmp_path, monkeypatch):
    args, state, _ = setup(tmp_path, monkeypatch)
    asyncio.run(cli.run(score=True, group="ATP", **args))
    monkeypatch.setattr(cli, "RULE_SHA256", "f" * 64)
    with pytest.raises(ValueError, match="no rescoring"):
        asyncio.run(cli.run(score=True, group="ATP", **args))
    assert state.losses == 1


def test_report_lock_excludes_another_scorer_and_releases_after_exception(tmp_path):
    with cli._score_lock(tmp_path):
        with pytest.raises(ValueError, match="Another process"):
            with cli._score_lock(tmp_path):
                raise AssertionError("Second scorer obtained lock")
    with pytest.raises(RuntimeError):
        with cli._score_lock(tmp_path):
            raise RuntimeError("release me")
    with cli._score_lock(tmp_path):
        pass
