from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from app.core.nba_teammate_split import classify_games, split_teammates


@dataclass(frozen=True)
class Entry:
    player_id: int | None
    player_name: str
    team: str = "PHI"
    athlete_team: str | None = None
    status: str = "Out"


@dataclass(frozen=True)
class Game:
    game_id: int
    game_date: dt.date


def names(entries: list[Entry]) -> list[str]:
    return [entry.player_name for entry in entries]


def test_out_and_suspension_kept_in_any_case() -> None:
    entries = [Entry(1, "Joel Embiid", status="OUT"), Entry(2, "Kelly Oubre", status="suspension")]
    assert names(split_teammates(entries, "PHI", 99)) == ["Joel Embiid", "Kelly Oubre"]


def test_day_to_day_dropped() -> None:
    assert split_teammates([Entry(1, "Joel Embiid", status="Day-To-Day")], "PHI", 99) == []


def test_other_team_moved_athlete_and_unlinked_dropped() -> None:
    entries = [
        Entry(1, "Jalen Brunson", team="NY"),
        Entry(2, "Moved Player", athlete_team="BOS"),
        Entry(None, "Unlinked Player"),
        Entry(3, "Same Team", athlete_team="PHI"),
    ]
    assert names(split_teammates(entries, "PHI", 99)) == ["Same Team"]


def test_player_himself_dropped() -> None:
    assert split_teammates([Entry(99, "Tyrese Maxey")], "PHI", 99) == []


def test_dedupe_by_player_and_sort_by_name() -> None:
    entries = [Entry(2, "Paul George"), Entry(1, "Joel Embiid"), Entry(2, "Paul George", status="Suspension")]
    kept = split_teammates(entries, "PHI", 99)
    assert names(kept) == ["Joel Embiid", "Paul George"]
    assert kept[1].status == "Out"


GAMES = [Game(30, dt.date(2026, 11, 10)), Game(20, dt.date(2026, 11, 5)), Game(10, dt.date(2026, 11, 1))]


def test_with_without_and_before() -> None:
    assert classify_games(GAMES, dt.date(2026, 11, 3), {30}) == ["with", "without", "before"]


def test_first_team_date_is_inclusive() -> None:
    assert classify_games(GAMES, dt.date(2026, 11, 1), {10}) == ["without", "without", "with"]


def test_no_first_team_date_judges_nothing() -> None:
    assert classify_games(GAMES, None, set()) == ["before", "before", "before"]
