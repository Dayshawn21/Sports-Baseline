"""canonical, genuinely unique h2h rows

`idx_h2h_unique` was created with Postgres's default NULLS DISTINCT. Overall
head-to-head is stored with `surface IS NULL`, and NULL never equals NULL, so the
`ON CONFLICT (p1_id, p2_id, surface)` in `upsert_h2h` never matched an existing
overall row and every ingest run inserted another copy. The table held 5369 rows
for 2693 real pairings, one pairing stored 9 times, and duplicates disagreed with
each other (pair 126/201 carried both 0-1 and 2-0).

Flipping the index to NULLS NOT DISTINCT alone would not have been enough: a
pairing can also be stored under both orientations, which are different tuples
and would never collide. So rows are canonicalized to `p1_id < p2_id` first, and
a CHECK keeps them that way. Both read paths already reorient, so this is
invisible to callers.

Requires PostgreSQL 15+ for NULLS NOT DISTINCT, which the project already needs
for the `player_rolling_stats` index added in 0003.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Duplicates disagree, so dedupe has to pick a winner and that choice is not
    # recoverable from the surviving rows. Keep a copy; drop it once the next
    # ingest has confirmed the table looks right.
    op.execute("CREATE TABLE h2h_backup_0013 AS SELECT * FROM h2h")

    # Dropped before the rewrite, not after: the old index still enforces
    # uniqueness for non-NULL surfaces, so swapping (436,378,'Clay') into
    # (378,436,'Clay') collides with the row already sitting there.
    op.execute("DROP INDEX IF EXISTS idx_h2h_unique")

    op.execute("""
        UPDATE h2h
        SET p1_id = p2_id, p2_id = p1_id,
            p1_wins = p2_wins, p2_wins = p1_wins
        WHERE p1_id > p2_id
    """)

    # Newest wins; the next ingest overwrites it with fresh API data regardless.
    op.execute("""
        DELETE FROM h2h a
        USING h2h b
        WHERE a.p1_id = b.p1_id
          AND a.p2_id = b.p2_id
          AND a.surface IS NOT DISTINCT FROM b.surface
          AND (a.updated_at, a.id) < (b.updated_at, b.id)
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_h2h_unique
        ON h2h (p1_id, p2_id, surface) NULLS NOT DISTINCT
    """)

    op.execute("ALTER TABLE h2h ADD CONSTRAINT ck_h2h_canonical_order CHECK (p1_id < p2_id)")


def downgrade() -> None:
    # Deliberately partial: the deleted duplicates are gone from `h2h`, and the
    # original orientation of the swapped rows is not recorded. This restores the
    # schema, not the data. `h2h_backup_0013` is the only route back.
    op.execute("ALTER TABLE h2h DROP CONSTRAINT IF EXISTS ck_h2h_canonical_order")
    op.execute("DROP INDEX IF EXISTS idx_h2h_unique")
    op.execute("CREATE UNIQUE INDEX idx_h2h_unique ON h2h (p1_id, p2_id, surface)")
