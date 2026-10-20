"""Pure parsing of TennisMyLife CSV rows into player-oriented box scores."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime


_REQUIRED_COLUMNS = frozenset({
    "tourney_id", "tourney_name", "tourney_date", "surface", "round", "score",
    "winner_name", "loser_name",
    "w_ace", "w_df", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_SvGms", "l_bpSaved", "l_bpFaced",
})


@dataclass(frozen=True)
class TmlBoxScore:
    player_name: str
    tour: str
    source_match_key: str
    match_date: date
    surface: str | None
    result: str
    aces: int | None
    double_faults: int | None
    service_games: int | None
    break_points_faced: int | None
    break_points_saved: int | None
    break_chances_created: int | None
    break_points_converted: int | None
    opponent_name: str
    round: str
    tournament: str | None
    score: str | None


@dataclass(frozen=True)
class PlayerNameIndex:
    canonical: Mapping[tuple[str, str], int]
    aliases: Mapping[str, int]


def resolve_name(index: PlayerNameIndex, name_norm: str, tour: str) -> int | None:
    """Resolve a normalized name by tour, then by globally unique alias."""
    player_id = index.canonical.get((name_norm, tour.upper()))
    return player_id if player_id is not None else index.aliases.get(name_norm)


def _optional_int(value: str | None) -> int | None:
    try:
        number = float(value) if value is not None else float("nan")
        return int(number) if number.is_integer() and number >= 0 else None
    except (ValueError, OverflowError):
        return None


def _required_text(row: Mapping[str, str | None], column: str) -> str:
    value = (row[column] or "").strip()
    if not value:
        raise ValueError(f"Empty TennisMyLife field: {column}")
    return value


def _parse_side(row: Mapping[str, str | None], tour: str, winner: bool) -> TmlBoxScore | None:
    side, opponent_side = ("w", "l") if winner else ("l", "w")
    aces = _optional_int(row[f"{side}_ace"])
    double_faults = _optional_int(row[f"{side}_df"])
    service_games = _optional_int(row[f"{side}_SvGms"])
    if aces is None and double_faults is None and service_games is None:
        return None
    player_name = _required_text(row, "winner_name" if winner else "loser_name")
    opponent = _required_text(row, "loser_name" if winner else "winner_name")
    tourney_id = _required_text(row, "tourney_id")
    round_name = _required_text(row, "round")
    key = f"tml-v1|{tourney_id}|{round_name}|{opponent.lower()}"
    chances_created = _optional_int(row[f"{opponent_side}_bpFaced"])
    opponent_saved = _optional_int(row[f"{opponent_side}_bpSaved"])
    converted = None
    if chances_created is not None and opponent_saved is not None:
        converted = max(chances_created - opponent_saved, 0)
    surface = (row["surface"] or "").strip()
    return TmlBoxScore(
        player_name=player_name,
        tour=tour,
        source_match_key=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        match_date=datetime.strptime(_required_text(row, "tourney_date"), "%Y%m%d").date(),
        surface=surface if surface in {"Hard", "Clay", "Grass"} else None,
        result="W" if winner else "L",
        aces=aces,
        double_faults=double_faults,
        service_games=service_games,
        break_points_faced=_optional_int(row[f"{side}_bpFaced"]),
        break_points_saved=_optional_int(row[f"{side}_bpSaved"]),
        break_chances_created=chances_created,
        break_points_converted=converted,
        opponent_name=opponent,
        round=round_name,
        tournament=(row["tourney_name"] or "").strip() or None,
        score=(row["score"] or "").strip() or None,
    )


def parse_rows(rows: Iterable[Mapping[str, str | None]], tour: str) -> list[TmlBoxScore]:
    """Keep each side with stats; malformed columns or identity fields raise ValueError."""
    stats: list[TmlBoxScore] = []
    for row in rows:
        missing = _REQUIRED_COLUMNS.difference(row)
        if missing:
            raise ValueError(f"Missing TennisMyLife columns: {', '.join(sorted(missing))}")
        if (row["score"] or "").strip().upper() in {"W/O", "WO", "WALKOVER"}:
            continue
        for winner in (True, False):
            stat = _parse_side(row, tour, winner)
            if stat is not None:
                stats.append(stat)
    return stats
