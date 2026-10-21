"""Preview paired tennis ELO forecasts; explicit --write requires reviewed activation."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import sys

from app.db.pool import SessionLocal
from app.ingest import tennis_elo as ratings_cli
from app.ingest.predictions import MODELS_DIR
from app.ml.registry import ModelRegistry
from app.repositories import matches as match_repo
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot, get_daily_snapshots
from app.repositories.tennis_elo_comparison import (
    FreezeCycle, check_experiment_continuity, freeze_cycle, get_cycle_attempt_count, get_frozen_match_ids,
    get_resulted_match_ids,
)
from app.services.tennis.elo_comparison import ComparisonPlan, ExperimentConfig, build_plan, source_result_targets
from app.services.tennis.predictor import load_prediction_batch

EXPERIMENT_PATH = Path(__file__).parent / "data" / "tennis_elo_experiment.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def validated_candidates(
    snapshots: list[TennisEloSnapshot], now: datetime, identity_sha256: str, cache_dir: Path,
) -> dict[int, TennisEloSnapshot]:
    """Verify the entire persisted roster against its immutable reviewed manifest."""
    if not snapshots:
        raise ValueError("missing_daily_snapshot")
    ordered = sorted(snapshots, key=lambda s: (s.provider_namespace, s.provider_player_id))
    first = ordered[0]
    manifest = cache_dir / "manifests" / f"{first.manifest_sha256}.json"
    files, computed, mapping_hash, ratings_hash, identity = ratings_cli.load_manifest(manifest, now.date())
    if identity != identity_sha256 or computed > now:
        raise ValueError("invalid_daily_snapshot")
    if any(ratings_cli._sha((cache_dir / "files" / f"{f.sha256}.csv").read_bytes()) != f.sha256 for f in files):
        raise ValueError("invalid_daily_snapshot")
    if any(s.computed_at != computed or s.source_downloaded_at != max(f.downloaded_at for f in files)
           or s.as_of_date != now.date() or s.manifest_sha256 != first.manifest_sha256 for s in ordered):
        raise ValueError("invalid_daily_snapshot")
    mapping = sorted(((s.provider_namespace, s.provider_player_id), s.player_id) for s in ordered)
    if (len({s.player_id for s in ordered}) != len(ordered) or len({key for key, _ in mapping}) != len(ordered)
            or ratings_cli._sha(ratings_cli._canonical_json(mapping)) != mapping_hash
            or ratings_cli._sha(ratings_cli._canonical_json(
                [asdict(replace(s, manifest_sha256="0" * 64)) for s in ordered])) != ratings_hash):
        raise ValueError("incomplete_or_changed_daily_snapshot")
    return {s.player_id: s for s in ordered}


@dataclass(frozen=True)
class ComparisonRunResult:
    attempted: int
    ready: int
    inserted: int
    reused: bool
    active: bool
    plan_path: Path | None


def _report(plan: ComparisonPlan, config: ExperimentConfig, path: Path, inserted: int, dry_run: bool) -> None:
    attempts = plan.cycle.attempts
    eligible = sum(a.incumbent_eligible for a in attempts)
    available = sum(a.incumbent_eligible and a.candidate_available for a in attempts)
    print(f"Experiment {config.sha256}; active for accrual: {plan.experiment_active}; "
          f"first eligible UTC day: {config.eligible_from or 'pending activation'}")
    print(f"Attempts: {len(attempts)}; incumbent eligible: {eligible}; candidate available: {available}; "
          f"ready pairs: {plan.preview_pairs}; storable pairs: {len(plan.pairs)}")
    print(f"Reasons: {dict(Counter(a.reason for a in attempts))}")
    print(f"Plan SHA-256: {path.stem}\nPlan: {path}")
    print(f"{'DRY RUN' if dry_run else 'WRITE'}: {inserted} inserted; production predictions unchanged")


def _candidate_inputs(
    snapshots: list[TennisEloSnapshot], now: datetime, identity: ratings_cli.LoadedRegistry,
    cache_dir: Path, matches: list[match_repo.Match], resulted: set[int],
) -> tuple[dict[int, TennisEloSnapshot], str | None]:
    try:
        candidates = validated_candidates(snapshots, now, identity.sha256, cache_dir)
        manifest = cache_dir / "manifests" / f"{snapshots[0].manifest_sha256}.json"
        files, *_ = ratings_cli.load_manifest(manifest, now.date())
        source_matches, _ = ratings_cli.collect_matches(files, cache_dir, now.date(), identity.registry)
        resulted.update(source_result_targets(matches, source_matches, candidates))
    except (ValueError, OSError, KeyError):
        return {}, "missing_or_invalid_daily_snapshot"
    return candidates, None


async def run(
    *, dry_run: bool = True, cycle_key: datetime | None = None,
    experiment_path: Path = EXPERIMENT_PATH, cache_dir: Path = ratings_cli.CACHE_DIR,
    scheduled: bool = False,
) -> ComparisonRunResult:
    config = ExperimentConfig.from_record(json.loads(experiment_path.read_text(encoding="utf-8")))
    started = _now()
    if scheduled and (config.eligible_from is None or started.date() < config.eligible_from):
        print("Freeze skipped: experiment inactive or first full UTC day has not begun")
        return ComparisonRunResult(0, 0, 0, False, False, None)
    registry = ModelRegistry(MODELS_DIR)
    identity = ratings_cli.load_identity_registry()
    config.check_runtime(registry, identity.sha256)
    cycle_key = cycle_key or started.replace(minute=0, second=0, microsecond=0)
    if cycle_key.utcoffset() is None or cycle_key > started:
        raise ValueError("Comparison cycle key must be timezone-aware and not in the future")
    if not dry_run and (config.eligible_from is None or started.date() < config.eligible_from):
        raise ValueError("Experiment activation and its first full UTC day require review before a real freeze")
    async with SessionLocal() as db:
        await check_experiment_continuity(db, config.sha256)
        existing = await get_cycle_attempt_count(db, cycle_key)
        if existing is not None:
            print(f"Reused immutable cycle {cycle_key.isoformat()}: {existing} attempts, 0 inserted")
            return ComparisonRunResult(existing, 0, 0, True, True, None)
        dates = [started.date(), started.date() + timedelta(days=1)]
        matches = await match_repo.get_upcoming(db, dates)
        batch = await load_prediction_batch(db, matches, dates[0]) if matches else None
        snapshots = await get_daily_snapshots(db, source=SOURCE, as_of_date=started.date())
        resulted = await get_resulted_match_ids(db, [m.id for m in matches])
        frozen = await get_frozen_match_ids(db)
        now = _now()
        if now.date() != started.date():
            raise ValueError("UTC day rolled over while loading comparison inputs")
        candidates, snapshot_error = _candidate_inputs(snapshots, now, identity, cache_dir, matches, resulted)
        if snapshot_error:
            print(f"Freeze skipped: {snapshot_error}; eligible attempts retained for coverage")
        if batch is None:
            plan = ComparisonPlan(FreezeCycle(cycle_key, now, ()), (), 0,
                                  config.eligible_from is not None and now.date() >= config.eligible_from)
        else:
            plan = await asyncio.to_thread(
                build_plan, matches, batch, registry, candidates, config, now=now, cycle_key=cycle_key,
                resulted=resulted, frozen=frozen, snapshot_error=snapshot_error,
            )
        contents = ratings_cli._canonical_json({"experiment_sha256": config.sha256,
                                               "cycle": asdict(plan.cycle), "pairs": [asdict(p) for p in plan.pairs],
                                               "preview_pairs": plan.preview_pairs})
        path = cache_dir / "comparisons" / f"{ratings_cli._sha(contents)}.json"
        ratings_cli._immutable_write(path, contents)
        inserted = 0
        if not dry_run:
            if _now().date() != started.date():
                raise ValueError("UTC day rolled over before comparison write")
            inserted = await freeze_cycle(db, plan.cycle, plan.pairs)
            await db.commit()
    _report(plan, config, path, inserted, dry_run)
    return ComparisonRunResult(len(plan.cycle.attempts), plan.preview_pairs, inserted, False,
                               plan.experiment_active, path)


async def check_daily_snapshot(*, cache_dir: Path = ratings_cli.CACHE_DIR) -> None:
    """Check the full stored roster and original files before sharing a runner cache."""
    now = _now()
    identity = ratings_cli.load_identity_registry()
    async with SessionLocal() as db:
        snapshots = await get_daily_snapshots(db, source=SOURCE, as_of_date=now.date())
    candidates = validated_candidates(snapshots, now, identity.sha256, cache_dir)
    if _now().date() != now.date():
        raise ValueError("UTC day rolled over while checking snapshot cache")
    print(f"Complete UTC {now.date()} candidate snapshot and original files: {len(candidates)} players")


def main() -> None:
    logging.getLogger("tennis_elo").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--scheduled", action="store_true", help="write only after reviewed activation and first full UTC day")
    mode.add_argument("--check-snapshot", action="store_true", help="validate today's full stored roster and original cached files only")
    parser.add_argument("--cycle", type=datetime.fromisoformat, help="aware UTC cycle key; first cycle wins")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.check_snapshot:
        if args.cycle is not None:
            parser.error("--cycle does not apply to --check-snapshot")
        asyncio.run(check_daily_snapshot())
    else:
        asyncio.run(run(dry_run=not (args.write or args.scheduled), cycle_key=args.cycle,
                        scheduled=args.scheduled))


if __name__ == "__main__":
    main()
