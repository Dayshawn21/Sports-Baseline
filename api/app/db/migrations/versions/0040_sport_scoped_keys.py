"""Scope the shared tables' provider keys by sport, and drop the nfl_ object names (item 17b).

Additive for the ON CONFLICT arbiters: each sport-scoped unique index is created
beside the global one it replaces. Postgres infers an arbiter by its exact column
list, so code still on the nfl_* views keeps resolving the global index while 17b's
code resolves the scoped one. 0041 drops the global indexes with the views.

The renames are names only. Indexes, constraints and sequence defaults bind by OID,
and no code names any of them (checked 2026-10-02). The four global indexes keep
their nfl_ names because 0041 drops them.

Revision ID: 0040
Revises: 0039
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0040"
down_revision: Union[str, Sequence[str], None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# new index -> (table, columns); each replaces the global index named in GLOBAL_KEYS
SCOPED_KEYS: dict[str, tuple[str, tuple[str, ...]]] = {
    "uq_sport_teams_code": ("sport_teams", ("sport", "team_code")),
    "uq_sport_players_source_id": ("sport_players", ("sport", "source_player_id")),
    "uq_sport_games_source_id": ("sport_games", ("sport", "source_game_id")),
    "uq_sport_player_aliases_norm": ("sport_player_aliases", ("sport", "alias_name_norm")),
}

GLOBAL_KEYS: dict[str, str] = {
    "uq_sport_teams_code": "idx_nfl_teams_code",
    "uq_sport_players_source_id": "idx_nfl_players_nflverse_id",
    "uq_sport_games_source_id": "idx_nfl_games_provider",
    "uq_sport_player_aliases_norm": "idx_nfl_aliases_norm",
}

# Read from the live catalog on 2026-10-02.
INDEX_RENAMES: dict[str, str] = {
    "idx_nfl_players_team": "idx_sport_players_team",
    "idx_nfl_aliases_player": "idx_sport_player_aliases_player",
    "idx_nfl_games_slate": "idx_sport_games_slate",
    "idx_nfl_games_espn_event": "idx_sport_games_espn_event",
    "idx_nfl_prop_lines_slate": "idx_sport_prop_lines_slate",
    "idx_nfl_prop_lines_provider": "idx_sport_prop_lines_provider",
    "idx_nfl_prop_lines_segment": "idx_sport_prop_lines_segment",
    "idx_nfl_prop_lines_odds_type": "idx_sport_prop_lines_odds_type",
    "idx_nfl_game_odds_lookup": "idx_sport_game_odds_lookup",
    "idx_nfl_game_odds_fetched": "idx_sport_game_odds_fetched",
    "idx_nfl_prop_predictions_line": "idx_sport_prop_predictions_line",
    "uq_nfl_prop_predictions_line_version": "uq_sport_prop_predictions_line_version",
}

# table -> {old constraint: new constraint}; a primary key rename also renames its index
CONSTRAINT_RENAMES: dict[str, dict[str, str]] = {
    "sport_teams": {"nfl_teams_pkey": "sport_teams_pkey"},
    "sport_players": {
        "nfl_players_pkey": "sport_players_pkey",
        "nfl_players_team_id_fkey": "sport_players_team_id_fkey",
    },
    "sport_player_aliases": {
        "nfl_player_aliases_pkey": "sport_player_aliases_pkey",
        "nfl_player_aliases_nfl_player_id_fkey": "sport_player_aliases_player_id_fkey",
    },
    "sport_games": {
        "nfl_games_pkey": "sport_games_pkey",
        "nfl_games_home_team_id_fkey": "sport_games_home_team_id_fkey",
        "nfl_games_away_team_id_fkey": "sport_games_away_team_id_fkey",
    },
    "sport_prop_lines": {
        "nfl_prop_lines_pkey": "sport_prop_lines_pkey",
        "nfl_prop_lines_player_id_fkey": "sport_prop_lines_player_id_fkey",
        "nfl_prop_lines_game_id_fkey": "sport_prop_lines_game_id_fkey",
    },
    "sport_game_odds": {
        "nfl_game_odds_pkey": "sport_game_odds_pkey",
        "nfl_game_odds_game_id_fkey": "sport_game_odds_game_id_fkey",
        "ck_nfl_game_odds_market": "ck_sport_game_odds_market",
        "ck_nfl_game_odds_distinct_sides": "ck_sport_game_odds_distinct_sides",
    },
    "sport_prop_predictions": {
        "nfl_prop_predictions_pkey": "sport_prop_predictions_pkey",
        "nfl_prop_predictions_prop_line_id_fkey": "sport_prop_predictions_prop_line_id_fkey",
    },
}

SEQUENCE_RENAMES: dict[str, str] = {
    f"nfl_{name}_id_seq": f"sport_{name}_id_seq"
    for name in ("teams", "players", "player_aliases", "games", "prop_lines", "game_odds", "prop_predictions")
}


def upgrade() -> None:
    for index, (table, columns) in SCOPED_KEYS.items():
        op.execute(f"CREATE UNIQUE INDEX {index} ON {table} ({', '.join(columns)})")
    for old, new in INDEX_RENAMES.items():
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")
    for table, renames in CONSTRAINT_RENAMES.items():
        for old, new in renames.items():
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")
    for old, new in SEQUENCE_RENAMES.items():
        op.execute(f"ALTER SEQUENCE {old} RENAME TO {new}")


def downgrade() -> None:
    for old, new in SEQUENCE_RENAMES.items():
        op.execute(f"ALTER SEQUENCE {new} RENAME TO {old}")
    for table, renames in CONSTRAINT_RENAMES.items():
        for old, new in renames.items():
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")
    for old, new in INDEX_RENAMES.items():
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    for index in SCOPED_KEYS:
        op.execute(f"DROP INDEX {index}")
