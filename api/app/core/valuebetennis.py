"""One Valuebetennis season-CSV row as a typed match, for the 26c closing-line backtest.

Valuebetennis open data (https://www.valuebetennis.com, CC BY 4.0) labels in
French: `genre` atp/wta, `categorie` Grand Chelem, surfaces dur / terre battue /
gazon. Scores are written from joueur1's side and cut at 20 characters, which
truncates long five-setters mid-set.

Pure: takes a row mapping, never a file.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.core.tennis_grading import _finished_set, is_completed_score

SCORE_FIELD_LIMIT = 20
MAIN_DRAW_FIRST_ROUND = 4

_TOURS = {"atp": "ATP", "wta": "WTA"}
_CATEGORIES = {"Grand Chelem": "Grand Slam"}
_SURFACES = {"dur": "hard", "dur intérieur": "hard", "terre battue": "clay", "gazon": "grass"}
_FULL_SET = re.compile(r"(\d+)-(\d+)(?:\(\d+\))?")

SkipReason = Literal["no_match_id", "no_players", "winner_not_a_player", "no_date", "unknown_tour"]


@dataclass(frozen=True)
class VbtMatch:
    match_id: int
    tour: str
    category: str
    round_code: int
    match_date: date
    season: int
    tournament: str
    surface: str | None
    best_of: int
    p1_id: int
    p2_id: int
    winner_id: int
    score: str | None
    completed: bool
    truncated: bool
    p1_open: float | None
    p2_open: float | None
    p1_close: float | None
    p2_close: float | None


def _int(value: str | None) -> int | None:
    try:
        return int((value or "").strip())
    except ValueError:
        return None


def _odds(value: str | None) -> float | None:
    try:
        price = float((value or "").strip())
    except ValueError:
        return None
    return price if price > 1.0 else None


def _date(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "").strip()[:10])
    except ValueError:
        return None


def is_truncated_finish(score: str | None) -> bool:
    """A score cut at the field limit whose every set before the cut is finished.

    Only long matches reach 20 characters, so a clean prefix of finished sets is
    read as a completed match. Any retirement text before the cut fails it.
    """
    if score is None or len(score) != SCORE_FIELD_LIMIT:
        return False
    before_cut = score.split()[:-1]
    if len(before_cut) < 2:
        return False
    for token in before_cut:
        found = _FULL_SET.fullmatch(token)
        if found is None or not _finished_set(int(found.group(1)), int(found.group(2))):
            return False
    return True


def row_problem(row: Mapping[str, str]) -> SkipReason | None:
    """Why a row cannot become a match, or None when it can."""
    if _int(row.get("match_id")) is None:
        return "no_match_id"
    p1_id, p2_id = _int(row.get("joueur1_id")), _int(row.get("joueur2_id"))
    if p1_id is None or p2_id is None:
        return "no_players"
    if _int(row.get("vainqueur_id")) not in (p1_id, p2_id):
        return "winner_not_a_player"
    if _date(row.get("date")) is None:
        return "no_date"
    if (row.get("genre") or "").strip().lower() not in _TOURS:
        return "unknown_tour"
    return None


def parse_row(row: Mapping[str, str]) -> VbtMatch | None:
    """None when the row cannot be a scoreable singles result (see `row_problem`)."""
    if row_problem(row) is not None:
        return None
    match_id = int(row["match_id"])
    p1_id, p2_id = int(row["joueur1_id"]), int(row["joueur2_id"])
    winner_id = int(row["vainqueur_id"])
    match_date = date.fromisoformat(row["date"].strip()[:10])
    tour = _TOURS[row["genre"].strip().lower()]

    category_label = (row.get("categorie") or "").strip()
    category = _CATEGORIES.get(category_label, category_label)
    # An unreadable round code counts as qualifying, so it never enters the scored set.
    round_code = _int(row.get("tour")) or 0
    best_of = 5 if tour == "ATP" and category == "Grand Slam" and round_code >= MAIN_DRAW_FIRST_ROUND else 3
    score = (row.get("score") or "").strip() or None
    finished = is_completed_score(score, best_of)
    truncated = not finished and is_truncated_finish(score)

    return VbtMatch(
        match_id=match_id,
        tour=tour,
        category=category,
        round_code=round_code,
        match_date=match_date,
        season=match_date.year,
        tournament=(row.get("tournoi") or "").strip(),
        surface=_SURFACES.get((row.get("surface") or "").strip()),
        best_of=best_of,
        p1_id=p1_id,
        p2_id=p2_id,
        winner_id=winner_id,
        score=score,
        completed=finished or truncated,
        truncated=truncated,
        p1_open=_odds(row.get("cote1_ouverture")),
        p2_open=_odds(row.get("cote2_ouverture")),
        p1_close=_odds(row.get("cote1_cloture")),
        p2_close=_odds(row.get("cote2_cloture")),
    )
