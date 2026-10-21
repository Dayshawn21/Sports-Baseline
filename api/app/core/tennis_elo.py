"""Pure results contracts for the TennisMyLife ELO experiment."""
from __future__ import annotations

import hashlib
import json
import re
from bisect import bisect_left
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Literal

from app.core.tennis_grading import is_completed_score
from app.ml.elo_history import EloIndex, expected_score

Family = Literal["ATP", "CHALLENGER", "ATP_QUALI", "WTA"]
Namespace = Literal["ATP", "WTA"]
PlayerKey = tuple[Namespace, str]
Exclusion = Literal["doubles", "exhibition", "outside scope", "walkover", "retirement", "unfinished"]
PROVIDER_DATE_NOTE = (
    "Provider dates may be tournament-week dates, not played dates; "
    "historical lookups do not prove pre-match availability."
)

_LEVELS: dict[Family, frozenset[str]] = {
    "ATP": frozenset({"A", "250", "500", "M", "G", "D", "O", "F"}),
    "CHALLENGER": frozenset({"C"}),
    "ATP_QUALI": frozenset({"A", "250", "500", "M", "G"}),
    "WTA": frozenset({"A", "250", "500", "1000", "G", "D", "O", "F", "W"}),
}
_ROUNDS = {r: i for i, r in enumerate(("Q1", "Q2", "Q3", "RR", "R128", "R64", "R32", "R16", "QF", "SF", "BR", "F"))}
REQUIRED_COLUMNS = frozenset({
    "tourney_id", "tourney_name", "tourney_date", "tourney_level", "match_num",
    "round", "surface", "winner_id", "winner_name", "loser_id", "loser_name",
    "score", "best_of",
})
_SET = re.compile(r"(\d{1,2})-(\d{1,2})(?:\(\d+\))?")
_SET_TOKEN = re.compile(r"(?:\d{1,2}-\d{1,2}(?:\(\d+\))?|\[\d{1,2}-\d{1,2}\])")


class TennisEloContractError(ValueError):
    """An unverified source shape must stop ingestion rather than drop valid history."""


@dataclass(frozen=True)
class ExcludedMatch:
    reason: Exclusion


@dataclass(frozen=True)
class TennisEloMatch:
    namespace: Namespace
    family: Family
    event_id: str
    match_number: int
    provider_date: date
    round: str
    level: str
    surface: str | None
    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    tournament: str
    score: str
    best_of: int

    @property
    def source_key(self) -> str:
        identity = (self.namespace, self.family, self.event_id, self.round, self.match_number)
        return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()

    @property
    def winner_key(self) -> tuple[Namespace, str]:
        return self.namespace, self.winner_id

    @property
    def loser_key(self) -> tuple[Namespace, str]:
        return self.namespace, self.loser_id

    @property
    def sort_key(self) -> tuple[date, Namespace, Family, str, int, int]:
        return (self.provider_date, self.namespace, self.family, self.event_id,
                _ROUNDS[self.round], self.match_number)


def _text(row: Mapping[str, str | None], column: str) -> str:
    value = (row[column] or "").strip()
    if not value:
        raise ValueError(f"Empty TennisMyLife ELO field: {column}")
    return value


def _identity(row: Mapping[str, str | None]) -> tuple[str, str, int, date]:
    winner_id, loser_id = _text(row, "winner_id"), _text(row, "loser_id")
    if not all(re.fullmatch(r"[A-Za-z0-9]+", pid) for pid in (winner_id, loser_id)):
        raise ValueError("Invalid TennisMyLife player ID")
    if winner_id == loser_id:
        raise ValueError("TennisMyLife result has identical participant IDs")
    number, date_text = _text(row, "match_num"), _text(row, "tourney_date")
    if not re.fullmatch(r"\d+", number) or int(number) < 1:
        raise ValueError("Invalid TennisMyLife match_num")
    if not re.fullmatch(r"\d{8}", date_text):
        raise ValueError("Invalid TennisMyLife tourney_date")
    return winner_id, loser_id, int(number), datetime.strptime(date_text, "%Y%m%d").date()


def _score_exclusion(score: str, best_of: int) -> ExcludedMatch | None:
    tokens = score.upper().split()
    if any(t in {"W/O", "WO", "WALKOVER"} for t in tokens):
        return ExcludedMatch("walkover")
    if any(t in {"RET", "RET.", "RETIRED"} for t in tokens):
        return ExcludedMatch("retirement")
    if not tokens or any(t in {"DEF", "DEF.", "ABD", "ABN", "ABANDONED", "CANCELLED"} for t in tokens):
        return ExcludedMatch("unfinished")
    if not all(_SET_TOKEN.fullmatch(t) for t in tokens):
        raise ValueError(f"Malformed TennisMyLife score: {score}")
    if not is_completed_score(score, best_of):
        return ExcludedMatch("unfinished")
    winner_sets = sum(int(m[1]) > int(m[2]) for m in _SET.finditer(score))
    if winner_sets != best_of // 2 + 1:
        raise ValueError("TennisMyLife score disagrees with winner-first orientation")
    return None


def parse_row(row: Mapping[str, str | None], family: Family) -> TennisEloMatch | ExcludedMatch:
    """Malformed contracts raise; intentionally excluded results carry a reason."""
    if family not in _LEVELS:
        raise TennisEloContractError(f"Unknown TennisMyLife family: {family}")
    missing = REQUIRED_COLUMNS.difference(row)
    if missing:
        raise TennisEloContractError(f"Missing TennisMyLife ELO columns: {', '.join(sorted(missing))}")
    if any("/" in (row[k] or "") or "&" in (row[k] or "")
           for k in ("winner_id", "winner_name", "loser_id", "loser_name")):
        return ExcludedMatch("doubles")
    level = _text(row, "tourney_level").upper()
    if level == "E":
        return ExcludedMatch("exhibition")
    if level in {"125", "ITF", "S", "15", "25", "60", "80", "100"}:
        return ExcludedMatch("outside scope")
    if level not in _LEVELS[family]:
        raise TennisEloContractError(f"Unverified TennisMyLife level {level!r} in {family}")
    # The audited W label is Charleston's second 2021 WTA 250, not WTA 125.
    if level == "W" and _text(row, "tourney_id") != "2021-2033":
        raise TennisEloContractError("Unverified TennisMyLife W-level event")
    if family == "WTA" and level == "A" and _text(row, "tourney_id") not in {"2025-1082", "2025-2084"}:
        raise TennisEloContractError("Unverified TennisMyLife WTA A-level event")
    winner_id, loser_id, match_number, provider_date = _identity(row)
    round_name = _text(row, "round").upper()
    qualifying = round_name in {"Q1", "Q2", "Q3"}
    if round_name not in _ROUNDS or qualifying != (family == "ATP_QUALI"):
        raise TennisEloContractError(f"Unverified TennisMyLife round {round_name!r} in {family}")
    best_of_text = _text(row, "best_of")
    if best_of_text not in {"3", "5"}:
        raise ValueError("TennisMyLife best_of must be 3 or 5")
    best_of = int(best_of_text)
    score = " ".join((row["score"] or "").split())
    excluded = _score_exclusion(score, best_of)
    if excluded is not None:
        return excluded
    return TennisEloMatch(
        namespace="WTA" if family == "WTA" else "ATP", family=family,
        event_id=_text(row, "tourney_id"), match_number=match_number,
        provider_date=provider_date, round=round_name, level=level,
        surface={"hard": "hard", "clay": "clay", "grass": "grass"}.get((row["surface"] or "").strip().lower()),
        winner_id=winner_id, winner_name=_text(row, "winner_name"),
        loser_id=loser_id, loser_name=_text(row, "loser_name"),
        tournament=_text(row, "tourney_name"), score=score, best_of=best_of,
    )


IDENTITY_VERSION = "tennis-elo-identities-v1"
IDENTITY_COLUMNS = ("namespace", "raw_provider_id", "canonical_provider_id", "status", "evidence")
OVERRIDE_COLUMNS = ("namespace", "canonical_provider_id", "local_player_id", "status", "evidence")
_PROVIDER_ID = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class IdentityRegistry:
    """Reviewed provider-identity crosswalk; only verified rows take effect."""
    canonical: Mapping[PlayerKey, str] = field(default_factory=dict)
    local_overrides: Mapping[PlayerKey, int] = field(default_factory=dict)
    proposed: int = 0
    version: str = IDENTITY_VERSION


def _registry_row(row: Mapping[str, str | None], columns: tuple[str, ...]) -> dict[str, str]:
    if tuple(row) != columns:
        raise TennisEloContractError(f"ELO identity registry columns must be {', '.join(columns)}")
    values = {k: (row[k] or "").strip() for k in columns}
    if values["namespace"] not in {"ATP", "WTA"} or values["status"] not in {"verified", "proposed"}:
        raise TennisEloContractError(f"Invalid ELO identity registry row: {values}")
    if not values["evidence"] or not _PROVIDER_ID.fullmatch(values["canonical_provider_id"]):
        raise TennisEloContractError(f"ELO identity registry row lacks evidence or a valid ID: {values}")
    return values


def parse_identity_registry(
    identities: Iterable[Mapping[str, str | None]], overrides: Iterable[Mapping[str, str | None]],
) -> IdentityRegistry:
    """Reject chains, duplicates and cross-namespace keys rather than guess a resolution."""
    canonical: dict[PlayerKey, str] = {}
    seen: set[PlayerKey] = set()
    proposed = 0
    for row in identities:
        values = _registry_row(row, IDENTITY_COLUMNS)
        ns = "ATP" if values["namespace"] == "ATP" else "WTA"
        raw = values["raw_provider_id"]
        if not _PROVIDER_ID.fullmatch(raw) or raw == values["canonical_provider_id"] or (ns, raw) in seen:
            raise TennisEloContractError(f"Invalid or duplicate ELO identity alias: {ns}:{raw}")
        seen.add((ns, raw))
        if values["status"] == "proposed":
            proposed += 1
        else:
            canonical[(ns, raw)] = values["canonical_provider_id"]
    if any((ns, target) in seen for (ns, _raw), target in canonical.items()):
        raise TennisEloContractError("ELO identity registry canonical IDs must not themselves be aliases")
    local: dict[PlayerKey, int] = {}
    for row in overrides:
        values = _registry_row(row, OVERRIDE_COLUMNS)
        key: PlayerKey = ("ATP" if values["namespace"] == "ATP" else "WTA", values["canonical_provider_id"])
        if not re.fullmatch(r"[1-9]\d*", values["local_player_id"]) or key in local or key in seen:
            raise TennisEloContractError(f"Invalid or duplicate ELO local override: {key}")
        if values["status"] == "proposed":
            proposed += 1
            continue
        local[key] = int(values["local_player_id"])
    if len(set(local.values())) != len(local):
        raise TennisEloContractError("Two ELO local overrides target one local player")
    return IdentityRegistry(canonical, local, proposed)


def normalize_identities(match: TennisEloMatch, registry: IdentityRegistry) -> TennisEloMatch:
    winner = registry.canonical.get(match.winner_key, match.winner_id)
    loser = registry.canonical.get(match.loser_key, match.loser_id)
    if winner == loser:
        raise TennisEloContractError(f"Identity normalization made a self-match: {match.source_key}")
    if (winner, loser) == (match.winner_id, match.loser_id):
        return match
    return replace(match, winner_id=winner, loser_id=loser)


def deduplicate(matches: Iterable[TennisEloMatch]) -> list[TennisEloMatch]:
    """Keep the first identical copy; contradictions stop the whole input batch."""
    unique: dict[str, TennisEloMatch] = {}
    for match in matches:
        previous = unique.get(match.source_key)
        if previous is not None and previous != match:
            raise ValueError(f"Conflicting TennisMyLife match: {match.source_key}")
        unique.setdefault(match.source_key, match)
    return sorted(unique.values(), key=lambda m: m.sort_key)


@dataclass(frozen=True)
class TennisEloRating:
    overall: float
    hard: float | None
    clay: float | None
    grass: float | None
    overall_matches: int
    hard_matches: int
    clay_matches: int
    grass_matches: int


class TennisEloReplay:
    """26c's unchanged math over deterministic provider-date-ordered results."""

    def __init__(self, matches: Iterable[TennisEloMatch]) -> None:
        ordered = deduplicate(matches)
        self.matches_count = len(ordered)
        self.players = tuple(sorted({key for m in ordered for key in (m.winner_key, m.loser_key)}))
        self._ids = {key: i for i, key in enumerate(self.players)}
        self._dates: dict[tuple[PlayerKey, str | None], list[date]] = {}
        replay_rows: list[tuple[date, int, int, int, str | None]] = []
        for match in ordered:
            winner, loser = self._ids[match.winner_key], self._ids[match.loser_key]
            replay_rows.append((match.provider_date, min(winner, loser), max(winner, loser),
                                winner, match.surface))
            for key in (match.winner_key, match.loser_key):
                self._dates.setdefault((key, None), []).append(match.provider_date)
                if match.surface in {"hard", "clay", "grass"}:
                    self._dates.setdefault((key, match.surface), []).append(match.provider_date)
        self._elo = EloIndex(replay_rows)

    def _count(self, player: PlayerKey, surface: str | None, before: date) -> int:
        return bisect_left(self._dates.get((player, surface), []), before)

    def rating(self, player: PlayerKey, before: date) -> TennisEloRating | None:
        """Ratings/counts from provider dates strictly before the cutoff."""
        player_id = self._ids.get(player)
        if player_id is None:
            return None
        overall = self._elo.rating(player_id, before)
        if overall is None:
            return None
        return TennisEloRating(
            overall=overall,
            hard=self._elo.surface_rating(player_id, "hard", before),
            clay=self._elo.surface_rating(player_id, "clay", before),
            grass=self._elo.surface_rating(player_id, "grass", before),
            overall_matches=self._count(player, None, before),
            hard_matches=self._count(player, "hard", before),
            clay_matches=self._count(player, "clay", before),
            grass_matches=self._count(player, "grass", before),
        )

    def probability(
        self, p1: PlayerKey, p2: PlayerKey, surface: str | None, before: date,
    ) -> float | None:
        """Use surface ratings only when both exist; otherwise use both overall."""
        if p1 == p2:
            raise ValueError("ELO probability requires distinct players")
        first, second = self.rating(p1, before), self.rating(p2, before)
        if first is None or second is None:
            return None
        surfaces = {"hard": (first.hard, second.hard), "clay": (first.clay, second.clay),
                    "grass": (first.grass, second.grass)}
        r1, r2 = surfaces.get((surface or "").strip().lower(), (None, None))
        if r1 is None or r2 is None:
            r1, r2 = first.overall, second.overall
        return expected_score(r1, r2)

    def audit_summary(self) -> str:
        return f"Replay: {self.matches_count} matches, {len(self.players)} players. {PROVIDER_DATE_NOTE}"
