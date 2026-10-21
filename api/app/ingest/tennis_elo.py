"""Preview or persist isolated TennisMyLife ELO; never change production ratings."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import cast

import httpx

from app.core.tennis_elo import (
    REQUIRED_COLUMNS, Family, IdentityRegistry, PlayerKey, TennisEloContractError, TennisEloMatch,
    TennisEloReplay, normalize_identities, parse_identity_registry, parse_row,
)
from app.core.tennismylife import PlayerNameIndex, resolve_name
from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.ingest.tennismylife import _retryable
from app.repositories.players import get_player_name_index, normalize_name
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot, get_daily_snapshots, insert_daily_snapshots
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

logger = logging.getLogger("tennis_elo")
BASE_URL = "https://stats.tennismylife.org/data/"
MANIFEST_URL = "https://stats.tennismylife.org/api/data-files"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "tennismylife-elo"
REGISTRY_DIR = Path(__file__).resolve().parent / "data"
START = date(2021, 1, 1)


@dataclass(frozen=True)
class SourceFile:
    family: Family
    path: str


@dataclass(frozen=True)
class DownloadedFile:
    source: SourceFile
    sha256: str
    downloaded_at: datetime


@dataclass
class Counts:
    files: int = 0
    rows: int = 0
    admitted: int = 0
    duplicates: int = 0
    malformed: int = 0
    excluded: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class LoadedRegistry:
    registry: IdentityRegistry
    sha256: str



@dataclass
class MappingResult:
    linked: dict[PlayerKey, int]
    unmapped: int
    ambiguous: int
    conflicts: list[str]


@dataclass(frozen=True)
class RunResult:
    manifest_path: Path | None
    candidates: int
    inserted: int = 0
    reused: bool = False
    blocked: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def source_files(day: date) -> list[SourceFile]:
    files = [source for year in range(START.year, day.year + 1) for source in (
        SourceFile("ATP", f"{year}.csv"), SourceFile("CHALLENGER", f"{year}_challenger.csv"),
        SourceFile("ATP_QUALI", f"atp_quali/{year}_atp_quali.csv"), SourceFile("WTA", f"{year}_wta.csv"),
    )]
    return [*files, SourceFile("ATP", "ongoing_tourneys.csv"),
            SourceFile("CHALLENGER", "challenger_ongoing_tourneys.csv"),
            SourceFile("WTA", "wta_ongoing_tourneys.csv")]


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str).encode()


def _sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _immutable_write(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(contents)
    except FileExistsError:
        if path.read_bytes() != contents:
            raise ValueError(f"Immutable ELO cache conflict: {path.name}")


@retry(retry=retry_if_exception(_retryable), stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def _fetch(client: httpx.AsyncClient, url: str) -> bytes:
    response = await client.get(url)
    response.raise_for_status()
    return response.content


async def download_files(day: date, cache_dir: Path) -> list[DownloadedFile]:
    sources = source_files(day)
    limit = asyncio.Semaphore(4)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        listing = json.loads(await _fetch(client, MANIFEST_URL))
        available = {f["name"]: f["url"] for f in listing["files"]}
        if any(available.get(s.path) != BASE_URL + s.path for s in sources):
            raise TennisEloContractError("Required ELO source file missing or moved in provider manifest")

        async def download(source: SourceFile) -> DownloadedFile:
            async with limit:
                contents = await _fetch(client, BASE_URL + source.path)
                downloaded_at = _now()
                digest = _sha(contents)
                _immutable_write(cache_dir / "files" / f"{digest}.csv", contents)
                logger.info("Downloaded %s", source.path)
                return DownloadedFile(source, digest, downloaded_at)

        files = list(await asyncio.gather(*(download(s) for s in sources)))
        provenance = _canonical_json({"source": SOURCE, "as_of_date": day.isoformat(), "files": _file_records(files)})
        path = cache_dir / "downloads" / f"{_sha(provenance)}.json"
        _immutable_write(path, provenance)
        logger.info("Complete download provenance: %s", path)
        return files


def _file_records(files: list[DownloadedFile]) -> list[dict[str, str]]:
    return [{"family": f.source.family, "path": f.source.path, "url": BASE_URL + f.source.path,
             "sha256": f.sha256, "downloaded_at": f.downloaded_at.isoformat()} for f in files]


def load_identity_registry(directory: Path = REGISTRY_DIR) -> LoadedRegistry:
    contents = [(directory / name).read_bytes()
                for name in ("tennis_elo_identities.csv", "tennis_elo_local_overrides.csv")]
    identities, overrides = (csv.DictReader(StringIO(c.decode("utf-8-sig"))) for c in contents)
    registry = parse_identity_registry(identities, overrides)
    digest = _sha(_canonical_json({"version": registry.version, "files": [_sha(c) for c in contents]}))
    return LoadedRegistry(registry, digest)


def collect_matches(
    files: list[DownloadedFile], cache_dir: Path, day: date, registry: IdentityRegistry = IdentityRegistry(),
) -> tuple[list[TennisEloMatch], dict[Family, Counts]]:
    """Identities are normalized before deduplication so renumbered copies compare equal."""
    counts = {family: Counts() for family in ("ATP", "CHALLENGER", "ATP_QUALI", "WTA")}
    unique: dict[str, TennisEloMatch] = {}
    for file in files:
        contents = (cache_dir / "files" / f"{file.sha256}.csv").read_bytes()
        if _sha(contents) != file.sha256:
            raise ValueError(f"ELO cached file hash mismatch: {file.source.path}")
        reader = csv.DictReader(StringIO(contents.decode("utf-8-sig")))
        if not REQUIRED_COLUMNS.issubset(reader.fieldnames or ()):
            raise TennisEloContractError(f"ELO CSV columns changed: {file.source.path}")
        count = counts[file.source.family]
        count.files += 1
        file_rows = 0
        for number, row in enumerate(reader, 2):
            count.rows += 1
            file_rows += 1
            try:
                provider_date = datetime.strptime(row.get("tourney_date") or "", "%Y%m%d").date()
                if not START <= provider_date < day:
                    count.excluded["outside cutoff"] += 1
                    continue
                if file.source.family == "ATP_QUALI" and row.get("round") in {
                    "R128", "R64", "R32", "R16", "QF", "SF", "F", "RR", "BR",
                }:
                    main_copy = parse_row(row, "ATP")
                    if isinstance(main_copy, TennisEloMatch):
                        main_copy = normalize_identities(main_copy, registry)
                    if isinstance(main_copy, TennisEloMatch) and unique.get(main_copy.source_key) == main_copy:
                        count.duplicates += 1
                        continue
                    raise TennisEloContractError("Unverified main-draw row in qualifying file")
                match = parse_row(row, file.source.family)
            except TennisEloContractError:
                raise
            except ValueError as exc:
                count.malformed += 1
                if count.malformed <= 5:
                    logger.warning("Malformed %s row %d: %s", file.source.path, number, exc)
                continue
            if not isinstance(match, TennisEloMatch):
                count.excluded[match.reason] += 1
                continue
            match = normalize_identities(match, registry)
            if match.source_key in unique:
                if unique[match.source_key] != match:
                    raise TennisEloContractError(f"Conflicting ELO match copies: {file.source.path} row {number}")
                count.duplicates += 1
            else:
                unique[match.source_key] = match
                count.admitted += 1
        if file_rows == 0 and "ongoing" not in file.source.path:
            raise TennisEloContractError(f"Empty required annual file: {file.source.path}")
    return list(unique.values()), counts


def map_players(
    matches: list[TennisEloMatch], index: PlayerNameIndex, overrides: Mapping[PlayerKey, int] | None = None,
) -> MappingResult:
    """Reviewed overrides replace name resolution; the one-to-one check still applies to them."""
    overrides = overrides or {}
    names: dict[PlayerKey, set[str]] = defaultdict(set)
    for match in matches:
        names[match.winner_key].add(match.winner_name)
        names[match.loser_key].add(match.loser_name)
    namespace_ids = {tour: {pid for (_name, ns), pid in index.canonical.items() if ns == tour}
                     for tour in ("ATP", "WTA")}
    linked, conflicts, unmapped = {}, [], 0
    ambiguous: set[PlayerKey] = set()
    reverse: dict[int, list[PlayerKey]] = defaultdict(list)
    for key, variants in sorted(names.items()):
        if key in overrides:
            if overrides[key] not in namespace_ids[key[0]]:
                ambiguous.add(key)
                conflicts.append(f"{key}: override target {overrides[key]} is not a local {key[0]} player")
            else:
                linked[key] = overrides[key]
                reverse[overrides[key]].append(key)
            continue
        resolved = {pid for name in variants
                    if (pid := resolve_name(index, normalize_name(name), key[0])) is not None
                    and pid in namespace_ids[key[0]]}
        if not resolved:
            unmapped += 1
        elif len(resolved) > 1:
            ambiguous.add(key)
            conflicts.append(f"{key}: names {sorted(variants)} resolve to local IDs {sorted(resolved)}")
        else:
            pid = resolved.pop()
            linked[key] = pid
            reverse[pid].append(key)
    for pid, keys in reverse.items():
        if len(keys) > 1:
            ambiguous.update(keys)
            conflicts.append(f"local {pid} has multiple provider IDs: {keys}")
            for key in keys:
                del linked[key]
    return MappingResult(linked, unmapped, len(ambiguous), conflicts)


def build_snapshots(
    replay: TennisEloReplay, mapping: MappingResult, day: date, computed_at: datetime,
    downloaded_at: datetime, manifest_hash: str,
) -> list[TennisEloSnapshot]:
    snapshots = []
    for key, player_id in sorted(mapping.linked.items()):
        rating = replay.rating(key, day)
        if rating is not None:
            snapshots.append(TennisEloSnapshot(
                player_id=player_id, source=SOURCE, as_of_date=day, rating=rating,
                provider_namespace=key[0], provider_player_id=key[1], computed_at=computed_at,
                source_downloaded_at=downloaded_at, replay_cutoff=day,
                method_version=SOURCE, manifest_sha256=manifest_hash,
            ))
    return snapshots


def load_manifest(path: Path, day: date) -> tuple[list[DownloadedFile], datetime, str, str, str]:
    contents = path.read_bytes()
    if path.stem != _sha(contents):
        raise ValueError("ELO manifest filename/hash mismatch")
    record = json.loads(contents)
    if record["source"] != SOURCE or record["as_of_date"] != day.isoformat():
        raise ValueError("ELO manifest must describe this source and current UTC day")
    computed = datetime.fromisoformat(record["computed_at"])
    if computed.utcoffset() is None or computed.date() != day or computed > _now():
        raise ValueError("Invalid ELO manifest computation time")
    files = []
    for item in record["files"]:
        source = SourceFile(cast(Family, item["family"]), item["path"])
        if not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]) or item["url"] != BASE_URL + source.path:
            raise ValueError("Invalid ELO manifest file provenance")
        downloaded = datetime.fromisoformat(item["downloaded_at"])
        if downloaded.utcoffset() is None or downloaded > computed:
            raise ValueError("ELO download occurred after computation")
        files.append(DownloadedFile(source, item["sha256"], downloaded))
    if [f.source for f in files] != source_files(day):
        raise ValueError("ELO manifest must contain every required source exactly once in order")
    return files, computed, record["mapping_sha256"], record["ratings_sha256"], record["identity_sha256"]


def _print_report(
    counts: dict[Family, Counts], replay: TennisEloReplay, mapping: MappingResult,
    snapshots: list[TennisEloSnapshot], manifest_path: Path, identities: LoadedRegistry,
) -> None:
    print(replay.audit_summary())
    registry = identities.registry
    print(f"Identity registry {registry.version} {identities.sha256}: {len(registry.canonical)} aliases, "
          f"{len(registry.local_overrides)} local overrides, {registry.proposed} proposed (not applied)")
    print("family       files     rows   unique duplicates malformed  excluded")
    for family, c in counts.items():
        print(f"{family:<12} {c.files:>5} {c.rows:>8} {c.admitted:>8} {c.duplicates:>10} "
              f"{c.malformed:>9} {sum(c.excluded.values()):>9} {dict(c.excluded)}")
    print(f"Tracked candidates: {len(snapshots)}; unmapped provider players: {mapping.unmapped}; "
          f"ambiguous provider players: {mapping.ambiguous}; identity conflicts: {len(mapping.conflicts)}")
    for conflict in mapping.conflicts:
        print(f"BLOCKED identity: {conflict}")
    for s in snapshots[:5]:
        print(f"rating local={s.player_id} provider={s.provider_namespace}:{s.provider_player_id} "
              f"overall={s.rating.overall:.6f} hard={s.rating.hard} clay={s.rating.clay} "
              f"grass={s.rating.grass} matches={s.rating.overall_matches}")
    print(f"Manifest SHA-256: {manifest_path.stem}\nManifest: {manifest_path}")


async def run(
    *, dry_run: bool = True, manifest_path: Path | None = None, cache_dir: Path = CACHE_DIR,
    registry_dir: Path = REGISTRY_DIR,
) -> RunResult:
    day = _now().date()
    identities = load_identity_registry(registry_dir)
    async with SessionLocal() as db:
        existing = await get_daily_snapshots(db, source=SOURCE, as_of_date=day)
        if existing:
            if manifest_path is not None and manifest_path.stem != existing[0].manifest_sha256:
                raise ValueError("A different ELO daily manifest is already frozen")
            print(f"Reused immutable {day} snapshot: {len(existing)} ratings, 0 inserted; "
                  f"manifest {existing[0].manifest_sha256}")
            return RunResult(None, len(existing), reused=True)
        index = await get_player_name_index(db)
    expected_mapping = expected_ratings = None
    if manifest_path is None:
        files = await download_files(day, cache_dir)
    else:
        files, computed, expected_mapping, expected_ratings, expected_identity = load_manifest(manifest_path, day)
        if expected_identity != identities.sha256:
            raise ValueError("ELO identity registry changed since the reviewed manifest")
    matches, counts = collect_matches(files, cache_dir, day, identities.registry)
    replay = TennisEloReplay(matches)
    mapping = map_players(matches, index, identities.registry.local_overrides)
    downloaded = max(f.downloaded_at for f in files)
    if manifest_path is None:
        computed = _now()
    if computed.date() != day or _now().date() != day:
        raise ValueError("UTC day rolled over; do not store a mixed-day snapshot")
    provisional = build_snapshots(replay, mapping, day, computed, downloaded, "0" * 64)
    mapping_hash = _sha(_canonical_json(sorted((key, pid) for key, pid in mapping.linked.items())))
    ratings_hash = _sha(_canonical_json([asdict(s) for s in provisional]))
    if manifest_path is not None:
        if (mapping_hash, ratings_hash) != (expected_mapping, expected_ratings):
            raise ValueError("Reviewed ELO manifest no longer reproduces its identity mappings and ratings")
    else:
        manifest = {
            "source": SOURCE, "as_of_date": day.isoformat(), "computed_at": computed.isoformat(),
            "mapping_sha256": mapping_hash, "ratings_sha256": ratings_hash,
            "identity_version": identities.registry.version, "identity_sha256": identities.sha256,
            "files": _file_records(files),
        }
        contents = _canonical_json(manifest)
        manifest_path = cache_dir / "manifests" / f"{_sha(contents)}.json"
        _immutable_write(manifest_path, contents)
    snapshots = build_snapshots(replay, mapping, day, computed, downloaded, manifest_path.stem)
    _print_report(counts, replay, mapping, snapshots, manifest_path, identities)
    blocked = bool(mapping.conflicts) or not snapshots
    if blocked or dry_run:
        print("BLOCKED, 0 inserted" if blocked else "DRY RUN, 0 inserted")
        return RunResult(manifest_path, len(snapshots), blocked=blocked)
    async with SessionLocal() as db:
        inserted = await insert_daily_snapshots(db, snapshots)
        await db.commit()
    print(f"Stored {inserted} candidate ratings; production ELO unchanged")
    return RunResult(manifest_path, len(snapshots), inserted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only (default)")
    mode.add_argument("--write", action="store_true", help="persist candidate ratings after review")
    parser.add_argument("--manifest", type=Path, help="reproduce an immutable reviewed dry-run manifest")
    args = parser.parse_args()
    configure_ingest_logging()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    result = asyncio.run(run(dry_run=not args.write, manifest_path=args.manifest))
    if result.blocked:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
