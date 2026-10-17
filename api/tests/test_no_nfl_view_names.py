"""No app code may name the nfl_* views that 0041 drops, or their old column names.

The views and columns fail only at runtime, in whichever cron or page reaches the
query first, so this catches a reintroduced name before it ships.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).parents[1] / "app"
MIGRATIONS = APP / "db" / "migrations"

# A preceding `.` is a module path (`app.ingest.nfl_prop_predictions`), not a table.
# `nflverse_id` alone stays a Python parameter name; only the qualified column is banned.
OLD_NAMES = re.compile(
    r"(?<![\w.])nfl_(?:teams|players|player_aliases|games|prop_lines|game_odds|prop_predictions)\b"
    r"|\bnflverse_game_id\b|\bnfl_player_id\b|\b\w+\.nflverse_id\b"
)


def test_the_pattern_catches_old_sql_and_allows_module_paths() -> None:
    for sql in ("FROM nfl_games g", "JOIN nfl_players p ON p.id = 1", "INSERT INTO nfl_prop_lines (",
                "SELECT nflverse_game_id", "a.nfl_player_id = p.id", "p.nflverse_id = v.player_key"):
        assert OLD_NAMES.search(sql), sql
    for allowed in ("python -m app.ingest.nfl_prop_predictions", "FROM nfl_player_weekly_stats s",
                    "JOIN nfl_team_elo h", "nflverse_id: str", "FROM sport_games g"):
        assert not OLD_NAMES.search(allowed), allowed


def test_no_app_module_names_an_old_nfl_table_or_column() -> None:
    hits = [
        f"{path.relative_to(APP)}:{number}: {line.strip()}"
        for path in sorted(APP.rglob("*.py"))
        if MIGRATIONS not in path.parents
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if OLD_NAMES.search(line)
    ]
    assert hits == []
