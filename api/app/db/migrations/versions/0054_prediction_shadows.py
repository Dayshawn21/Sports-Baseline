"""Store shadow probabilities beside served tennis predictions (item 66a).

A shadow is never a `predictions` row: the pre-start loaders take the newest row of
any version, so a second row there would be served and graded as the model. One
shadow per (prediction, version); the probability is for p1, as on `predictions`.

Revision ID: 0054
Revises: 0053
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: Union[str, Sequence[str], None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prediction_shadows",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "prediction_id", sa.BigInteger,
            sa.ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("model_version", sa.Text, nullable=False),
        sa.Column("p1_prob", sa.Float, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prediction_id", "model_version", name="uq_prediction_shadows_prediction_version"),
        sa.CheckConstraint("p1_prob > 0 AND p1_prob < 1", name="ck_prediction_shadows_p1_prob"),
    )


def downgrade() -> None:
    op.drop_table("prediction_shadows")
