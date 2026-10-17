"""Move the cross-sport NFL tables into sport-keyed sport_* tables (item 17a).

Each table is renamed in place, so rows, ids, sequences, indexes and the inbound
foreign keys from the NFL stat tables all carry over. A `sport` column (no base
default) keys every row to the new `sports` registry.

The old nfl_* names become auto-updatable views exposing exactly the pre-17a
columns, so NFL code keeps reading and writing them unchanged until 17b moves it.
The view's own `sport` default makes an old-code insert land as nfl, and the
check option rejects any other sport through the view. The single-column unique
indexes stay global because they are the ON CONFLICT arbiters inferred through
the views; 17b rescopes them by sport.

Revision ID: 0039
Revises: 0038
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0039"
down_revision: Union[str, Sequence[str], None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPORT = "nfl"

TABLE_RENAMES: dict[str, str] = {
    "nfl_teams": "sport_teams",
    "nfl_players": "sport_players",
    "nfl_player_aliases": "sport_player_aliases",
    "nfl_games": "sport_games",
    "nfl_prop_lines": "sport_prop_lines",
    "nfl_game_odds": "sport_game_odds",
    "nfl_prop_predictions": "sport_prop_predictions",
}

# old view name -> {old column: new column}
COLUMN_RENAMES: dict[str, dict[str, str]] = {
    "nfl_players": {"nflverse_id": "source_player_id"},
    "nfl_player_aliases": {"nfl_player_id": "player_id"},
    "nfl_games": {"nflverse_game_id": "source_game_id"},
}

# The exact columns each table had before 17a, in order; the views expose these.
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

WEEK_CHECK = "ck_sport_games_nfl_week"


def view_select(view: str) -> str:
    renames = COLUMN_RENAMES.get(view, {})
    columns = [
        f"{renames[column]} AS {column}" if column in renames else column
        for column in VIEW_COLUMNS[view]
    ]
    return f"SELECT {', '.join(columns)}, sport FROM {TABLE_RENAMES[view]} WHERE sport = '{SPORT}'"


def upgrade() -> None:
    op.execute("CREATE TABLE sports (code text PRIMARY KEY, name text NOT NULL)")
    op.execute(f"INSERT INTO sports (code, name) VALUES ('{SPORT}', 'NFL')")

    for view, table in TABLE_RENAMES.items():
        op.execute(f"ALTER TABLE {view} RENAME TO {table}")
        for old, new in COLUMN_RENAMES.get(view, {}).items():
            op.execute(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
        # The default only backfills existing rows; new rows must name their sport.
        op.execute(f"ALTER TABLE {table} ADD COLUMN sport text NOT NULL DEFAULT '{SPORT}' REFERENCES sports(code)")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN sport DROP DEFAULT")

    op.execute("ALTER TABLE sport_games ALTER COLUMN week DROP NOT NULL")
    op.execute(f"ALTER TABLE sport_games ADD CONSTRAINT {WEEK_CHECK} CHECK (sport <> '{SPORT}' OR week IS NOT NULL)")

    for view in TABLE_RENAMES:
        op.execute(f"CREATE VIEW {view} AS {view_select(view)} WITH LOCAL CHECK OPTION")
        op.execute(f"ALTER VIEW {view} ALTER COLUMN sport SET DEFAULT '{SPORT}'")

    # Every view filters on sport, which has no statistics yet. The planner then
    # expects one row per filter and picked a slate plan that ran for minutes
    # instead of seconds; autoanalyze does not fire because no row changed.
    for table in TABLE_RENAMES.values():
        op.execute(f"ANALYZE {table}")


def downgrade() -> None:
    for table in TABLE_RENAMES.values():
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM {table} WHERE sport <> '{SPORT}') THEN
                    RAISE EXCEPTION '{table} holds non-{SPORT} rows; remove them before downgrading 0039';
                END IF;
            END $$
        """)

    for view in TABLE_RENAMES:
        op.execute(f"DROP VIEW {view}")

    op.execute(f"ALTER TABLE sport_games DROP CONSTRAINT {WEEK_CHECK}")
    op.execute("ALTER TABLE sport_games ALTER COLUMN week SET NOT NULL")

    for view, table in TABLE_RENAMES.items():
        op.execute(f"ALTER TABLE {table} DROP COLUMN sport")
        for old, new in COLUMN_RENAMES.get(view, {}).items():
            op.execute(f"ALTER TABLE {table} RENAME COLUMN {new} TO {old}")
        op.execute(f"ALTER TABLE {table} RENAME TO {view}")

    op.execute("DROP TABLE sports")
