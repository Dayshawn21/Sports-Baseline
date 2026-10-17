"""Drop the nfl_* compatibility views and the global provider keys (item 17b).

From here only the sport_* tables exist, and each provider key is unique per sport
(0040), so a second sport can reuse a team code or provider id. Code still written
against the views fails, which is why this is applied only together with the push
of 17b's code.

The downgrade restores 0039's views and the global unique indexes. It refuses while
any non-nfl row exists, because such a row could violate a global index and would
be invisible through the views.

Revision ID: 0041
Revises: 0040
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0041"
down_revision: Union[str, Sequence[str], None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPORT = "nfl"

# Copied from 0039 rather than imported, so this migration never changes with another file.
TABLE_RENAMES: dict[str, str] = {
    "nfl_teams": "sport_teams",
    "nfl_players": "sport_players",
    "nfl_player_aliases": "sport_player_aliases",
    "nfl_games": "sport_games",
    "nfl_prop_lines": "sport_prop_lines",
    "nfl_game_odds": "sport_game_odds",
    "nfl_prop_predictions": "sport_prop_predictions",
}

COLUMN_RENAMES: dict[str, dict[str, str]] = {
    "nfl_players": {"nflverse_id": "source_player_id"},
    "nfl_player_aliases": {"nfl_player_id": "player_id"},
    "nfl_games": {"nflverse_game_id": "source_game_id"},
}

VIEW_COLUMNS: dict[str, tuple[str, ...]] = {
    "nfl_teams": ("id", "team_code", "name", "conference", "division", "created_at"),
    "nfl_players": ("id", "nflverse_id", "name", "position", "team_id", "created_at", "updated_at"),
    "nfl_player_aliases": ("id", "nfl_player_id", "alias_name", "alias_name_norm", "source", "created_at"),
    "nfl_games": (
        "id", "nflverse_game_id", "season", "week", "game_type", "game_date", "start_utc",
        "home_team_id", "away_team_id", "home_score", "away_score", "status", "created_at",
        "updated_at", "espn_event_id", "spread_line", "total_line", "home_moneyline",
        "away_moneyline", "roof", "home_rest", "away_rest", "temp", "wind",
    ),
    "nfl_prop_lines": (
        "id", "provider", "provider_prop_id", "player_id", "game_id", "market", "line",
        "over_odds", "under_odds", "start_time", "fetched_at", "raw_json", "segment", "odds_type",
    ),
    "nfl_game_odds": (
        "id", "game_id", "book", "market", "line", "first_side", "second_side", "first_odds",
        "second_odds", "first_market_prob", "second_market_prob", "fetched_at", "raw_json",
    ),
    "nfl_prop_predictions": (
        "id", "prop_line_id", "model_version", "projection", "p_over", "p_under", "edge",
        "confidence", "quality_flags", "feature_snapshot", "generated_at", "over_probability_version",
    ),
}

# The global unique indexes 0040 left in place: name -> (table, column).
GLOBAL_KEYS: dict[str, tuple[str, str]] = {
    "idx_nfl_teams_code": ("sport_teams", "team_code"),
    "idx_nfl_players_nflverse_id": ("sport_players", "source_player_id"),
    "idx_nfl_games_provider": ("sport_games", "source_game_id"),
    "idx_nfl_aliases_norm": ("sport_player_aliases", "alias_name_norm"),
}


def view_select(view: str) -> str:
    renames = COLUMN_RENAMES.get(view, {})
    columns = [
        f"{renames[column]} AS {column}" if column in renames else column
        for column in VIEW_COLUMNS[view]
    ]
    return f"SELECT {', '.join(columns)}, sport FROM {TABLE_RENAMES[view]} WHERE sport = '{SPORT}'"


def upgrade() -> None:
    for view in TABLE_RENAMES:
        op.execute(f"DROP VIEW {view}")
    for index in GLOBAL_KEYS:
        op.execute(f"DROP INDEX {index}")


def downgrade() -> None:
    for table in TABLE_RENAMES.values():
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM {table} WHERE sport <> '{SPORT}') THEN
                    RAISE EXCEPTION '{table} holds non-{SPORT} rows; remove them before downgrading 0041';
                END IF;
            END $$
        """)
    for index, (table, column) in GLOBAL_KEYS.items():
        op.execute(f"CREATE UNIQUE INDEX {index} ON {table} ({column})")
    for view in TABLE_RENAMES:
        op.execute(f"CREATE VIEW {view} AS {view_select(view)} WITH LOCAL CHECK OPTION")
        op.execute(f"ALTER VIEW {view} ALTER COLUMN sport SET DEFAULT '{SPORT}'")
