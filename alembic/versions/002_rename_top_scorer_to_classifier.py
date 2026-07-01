"""rename predicted_top_scorer to predicted_classifier

Revision ID: 002
Revises: 001
Create Date: 2026-07-01

"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dados antigos guardavam nome de jogador — não fazem sentido como
    # classificado ('home'/'away'). Limpa antes de encolher a coluna.
    op.execute("UPDATE bets SET predicted_top_scorer = NULL")
    op.alter_column(
        "bets",
        "predicted_top_scorer",
        new_column_name="predicted_classifier",
        existing_type=sa.String(255),
        type_=sa.String(10),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "bets",
        "predicted_classifier",
        new_column_name="predicted_top_scorer",
        existing_type=sa.String(10),
        type_=sa.String(255),
        existing_nullable=True,
    )
