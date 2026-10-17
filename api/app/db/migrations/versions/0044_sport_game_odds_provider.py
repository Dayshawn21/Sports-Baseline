"""Tag each `sport_game_odds` row with the feed it came from (item 36a).

Every row before this revision came from The Odds API `us` region, the set
item 28's pre-registered CLV rule was written against, so readers filter to
`the_odds_api_us` and new feeds (Pinnacle, Odds-API.io) never reach them.
The default stays so workflows still running pre-36a code insert valid rows.

Revision ID: 0044
Revises: 0043
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: Union[str, Sequence[str], None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sport_game_odds",
        sa.Column("provider", sa.Text(), nullable=False, server_default="the_odds_api_us"),
    )
    op.create_check_constraint(
        "ck_sport_game_odds_provider",
        "sport_game_odds",
        "provider IN ('the_odds_api_us', 'the_odds_api_eu', 'odds_api_io')",
    )
    op.execute("ANALYZE sport_game_odds")


def downgrade() -> None:
    # Pre-36a code reads the table unfiltered, so other feeds' rows go first.
    op.execute("DELETE FROM sport_game_odds WHERE provider <> 'the_odds_api_us'")
    op.drop_constraint("ck_sport_game_odds_provider", "sport_game_odds", type_="check")
    op.drop_column("sport_game_odds", "provider")
