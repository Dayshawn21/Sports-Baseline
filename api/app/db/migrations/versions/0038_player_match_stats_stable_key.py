"""Key TennisAbstract box scores on the match, not the raw row, and merge the copies.

source_match_key was a hash of the whole raw row, and TennisAbstract edits a row as
a match goes from scheduled to scored to full stats, so each stage was stored as a
new row. Ingest now keys on (tournament start, tournament, round, opponent); see
box_score_key in app/ingest/player_stats.py, whose fixed test vector this SQL must
reproduce. Each duplicate group keeps its most complete, newest row. Rows missing a
key part (pre-26e) keep the raw-row key and are never merged.

The full table is snapshotted first so the downgrade restores it exactly; rows
written after the upgrade are lost on downgrade. Drop the snapshot in a later
migration once the fix has held.

Revision ID: 0038
Revises: 0037
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0038"
down_revision: Union[str, Sequence[str], None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SNAPSHOT = "player_match_stats_pre_0038"

KEYED = "tournament IS NOT NULL AND round IS NOT NULL AND opponent_name IS NOT NULL"

# One row per match survives: stats beat a bare score, a score beats a placeholder,
# then the newest fetch. Shared with the dry run so both count the same rows.
RANKED = f"""
    SELECT id, row_number() OVER (
        PARTITION BY player_id, source, match_date,
                     lower(trim(tournament)), lower(trim(round)), lower(trim(opponent_name))
        ORDER BY (aces IS NOT NULL OR double_faults IS NOT NULL
                  OR break_chances_created IS NOT NULL OR service_games IS NOT NULL) DESC,
                 (score IS NOT NULL) DESC,
                 fetched_at DESC,
                 id DESC
    ) AS rn
    FROM player_match_stats
    WHERE {KEYED}
"""

V2_KEY = (
    "encode(sha256(convert_to('v2|' || to_char(match_date, 'YYYYMMDD') || '|' || "
    "lower(trim(tournament)) || '|' || lower(trim(round)) || '|' || lower(trim(opponent_name)), "
    "'UTF8')), 'hex')"
)


def upgrade() -> None:
    op.execute(f"CREATE TABLE {SNAPSHOT} AS TABLE player_match_stats")
    op.execute(f"DELETE FROM player_match_stats p USING ({RANKED}) r WHERE p.id = r.id AND r.rn > 1")
    op.execute(f"UPDATE player_match_stats SET source_match_key = {V2_KEY} WHERE {KEYED}")


def downgrade() -> None:
    op.execute("DELETE FROM player_match_stats")
    op.execute(f"INSERT INTO player_match_stats SELECT * FROM {SNAPSHOT}")
    op.execute(f"DROP TABLE {SNAPSHOT}")
