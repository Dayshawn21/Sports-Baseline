"""Count forward ELO pairs by default; score one reviewed, immutable group sample."""
from __future__ import annotations

import argparse
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from app.core.tennis_elo_report import (
    EXPERIMENT, GROUPS, RULE_SHA256, Coverage, CoverageObservation, Probabilities, ReportCase, ReportPins,
    SampleSelection, ScoredCase,
    count_summary, coverage, mature_through, score_sample, select_sample, utc_day, valid_cases,
)
from app.db.pool import SessionLocal
from app.repositories.tennis_elo_report import begin_read_only_report, get_report_inputs, get_report_results
from app.services.tennis.elo_comparison import ExperimentConfig

EXPERIMENT_PATH = Path(__file__).resolve().parents[1] / "ingest" / "data" / "tennis_elo_experiment.json"
REPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "tennismylife-elo" / "reports" / EXPERIMENT


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical(value: object) -> bytes:
    def encode(item: object) -> str:
        if isinstance(item, datetime):
            return item.astimezone(timezone.utc).isoformat()
        if isinstance(item, date):
            return item.isoformat()
        raise TypeError(f"Unsupported report artifact type {type(item).__name__}")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=encode).encode()


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _write_once(path: Path, payload: dict[str, object]) -> str:
    digest = _sha(payload)
    contents = _canonical({"sha256": digest, "payload": payload})
    try:
        with path.open("xb") as handle:
            handle.write(contents)
    except FileExistsError:
        if path.read_bytes() != contents:
            raise ValueError("A different forward report artifact is already locked")
    return digest


def _read(path: Path, pins: ReportPins, group: str) -> tuple[dict[str, object], str]:
    record = json.loads(path.read_bytes())
    payload = record["payload"]
    if _sha(payload) != record["sha256"]:
        raise ValueError("Forward report artifact hash mismatch; manual review required")
    if (payload["experiment"], payload["experiment_sha256"], payload["rule_sha256"], payload["group"]) != (
        EXPERIMENT, pins.experiment_sha256, RULE_SHA256, group,
    ):
        raise ValueError("Locked forward experiment/rule changed; no rescoring permitted")
    return payload, record["sha256"]


@contextmanager
def _score_lock(directory: Path) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "score.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("Another process owns this group's score lock") from exc
        try:
            yield
        finally:
            handle.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _pins(config: ExperimentConfig) -> ReportPins:
    return ReportPins(config.sha256, config.eligible_from, config.coefficient_sha256,
                      config.gate_sha256, config.identity_sha256, config.model_versions)


def _counts(
    cases: Sequence[ReportCase], observations: Sequence[CoverageObservation], pins: ReportPins,
    groups: tuple[str, ...], now: datetime, locked_groups: frozenset[str] = frozenset(),
) -> str:
    lines = [f"Forward ELO source report: {EXPERIMENT}",
             f"First eligible UTC day: {pins.eligible_from or 'pending activation'}; "
             f"mature through: {mature_through(now)}", "Count only; outcomes and losses not inspected."]
    for group in groups:
        summary = count_summary(cases, observations, pins, group, now)
        state = "locked (counts only)" if group in locked_groups else "accruing"
        lines.append(f"{group}: {state}; frozen={summary.frozen_pairs}, mature={summary.mature_pairs}, "
                     f"mature days={summary.mature_kickoff_days}, "
                     f"candidate available={summary.candidate_available}/{summary.eligible_attempts} eligible attempts")
        if summary.potential_sample_floor:
            lines.append("  Sample count/day floor met; explicit score review still requires fully resolved cohorts.")
    return "\n".join(lines)


def _restore_selection(payload: dict[str, object]) -> tuple[SampleSelection, Coverage]:
    packet = payload["inputs"]
    if _sha(packet) != payload["input_sha256"]:
        raise ValueError("Locked report input hash mismatch")
    value = packet["selection"]
    cases = tuple(ScoredCase(
        match_id=c["match_id"], kickoff=datetime.fromisoformat(c["kickoff"]), p1_won=c["p1_won"],
        probabilities=Probabilities(**c["probabilities"]), surface=c["surface"],
        candidate_gated=c["candidate_gated"], incumbent_gated=c["incumbent_gated"],
    ) for c in value["cases"])
    if (any(type(c.p1_won) is not bool for c in cases)
            or len({c.match_id for c in cases}) != len(cases)
            or [c.match_id for c in cases] != payload["case_ids"] or value["group"] != payload["group"]):
        raise ValueError("Locked sample IDs, outcomes or group are inconsistent")
    selected = SampleSelection(value["group"], cases, date.fromisoformat(value["cutoff"]), None,
                               tuple(tuple(item) for item in value["excluded"]))
    cov = Coverage(tuple(packet["coverage"]["eligible_ids"]), tuple(packet["coverage"]["available_ids"]))
    if len(set(cov.eligible_ids)) != len(cov.eligible_ids) or len(set(cov.available_ids)) != len(cov.available_ids):
        raise ValueError("Locked coverage contains duplicate matches")
    return selected, cov


def _finish_locked(directory: Path, pins: ReportPins, group: str) -> str:
    sample, sample_hash = _read(directory / "sample.json", pins, group)
    path = directory / "report.json"
    if path.exists():
        report, _ = _read(path, pins, group)
        if report["sample_sha256"] != sample_hash:
            raise ValueError("Locked report does not match its frozen sample")
    else:
        selected, cov = _restore_selection(sample)
        # The sample and full copied inputs exist on disk before the first loss calculation.
        scored = score_sample(selected, cov)
        report = {"experiment": EXPERIMENT, "experiment_sha256": pins.experiment_sha256,
                  "rule_sha256": RULE_SHA256, "group": group, "sample_sha256": sample_hash,
                  "locked_at": sample["locked_at"], "result": asdict(scored)}
        _write_once(path, report)
        report, _ = _read(path, pins, group)
    return json.dumps(report, indent=2, sort_keys=True)


async def _prepare_score(group: str, pins: ReportPins, now: datetime, directory: Path) -> str | None:
    async with SessionLocal() as db:
        await begin_read_only_report(db)
        inputs = await get_report_inputs(db, include_probabilities=True)
        if inputs.invalid_payloads:
            raise ValueError("Invalid frozen payloads require review before any scoring")
        cases, excluded = valid_cases(inputs.cases, pins)
        counts = _counts(cases, inputs.coverage, pins, (group,), now)
        summary = count_summary(cases, inputs.coverage, pins, group, now)
        if not summary.potential_sample_floor:
            return counts
        mature = [c for c in cases if c.group == group and utc_day(c.kickoff) <= mature_through(now)]
        results = await get_report_results(db, [c.match_id for c in mature if c.current.kickoff is not None
                                               and utc_day(c.current.kickoff) <= mature_through(now)])
        selected = select_sample(mature, results, group, now)
        if selected.cutoff is None:
            return (f"{group}: accruing; resolved prefix={len(selected.cases)}; "
                    f"blocked UTC day={selected.blocked_day or 'none'}; excluded={dict(selected.excluded)}")
        cov = coverage(inputs.coverage, cases, pins, group, selected.cutoff)
        ids = [c.match_id for c in selected.cases]
        if not set(ids) <= set(cov.available_ids) <= set(cov.eligible_ids):
            raise ValueError("Cannot lock a sample without its complete coverage ledger")
        packet = {"selection": asdict(selected), "coverage": asdict(cov), "capture_exclusions": excluded,
                  "provenance": [asdict(c) for c in inputs.cases if c.group == group
                                 and utc_day(c.kickoff) <= selected.cutoff],
                  "results": [asdict(r) for mid, r in sorted(results.items())
                              if mid in {c.match_id for c in mature if utc_day(c.kickoff) <= selected.cutoff}],
                  "coverage_observations": [asdict(r) for r in inputs.coverage if r.group == group
                                            and r.kickoff is not None and utc_day(r.kickoff) <= selected.cutoff]}
        _write_once(directory / "sample.json", {
            "experiment": EXPERIMENT, "experiment_sha256": pins.experiment_sha256,
            "rule_sha256": RULE_SHA256, "group": group, "locked_at": now,
            "case_ids": ids, "input_sha256": _sha(packet), "inputs": packet,
        })
    return None


async def run(
    *, score: bool = False, group: str | None = None, experiment_path: Path = EXPERIMENT_PATH,
    report_dir: Path = REPORT_DIR,
) -> str:
    if group is not None and group not in GROUPS:
        raise ValueError("Unknown forward report group")
    if score and group is None:
        raise ValueError("Explicit --score requires exactly one --group")
    config = ExperimentConfig.from_record(json.loads(experiment_path.read_text(encoding="utf-8")))
    pins, now = _pins(config), _now()
    if score:
        if pins.eligible_from is None:
            return "Experiment inactive: accruing; no outcomes loaded or scored."
        directory = report_dir / group
        with _score_lock(directory):
            if not (directory / "sample.json").exists():
                if (directory / "report.json").exists():
                    raise ValueError("Locked report sample is missing; manual review required")
                pending = await _prepare_score(group, pins, now, directory)
                if pending is not None:
                    return pending
            return _finish_locked(directory, pins, group)
    async with SessionLocal() as db:
        await begin_read_only_report(db)
        inputs = await get_report_inputs(db)
    cases, excluded = valid_cases(inputs.cases, pins)
    locked = frozenset(g for g in GROUPS if (report_dir / g / "report.json").exists())
    return (_counts(cases, inputs.coverage, pins, (group,) if group else GROUPS, now, locked)
            + f"\nExcluded captures: {excluded}; invalid frozen payloads: {inputs.invalid_payloads}")


def main() -> None:
    import asyncio
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--count", action="store_true")
    mode.add_argument("--score", action="store_true")
    parser.add_argument("--group", choices=GROUPS)
    args = parser.parse_args()
    if args.score and args.group is None:
        parser.error("--score requires --group")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(asyncio.run(run(score=args.score, group=args.group)))


if __name__ == "__main__":
    main()
