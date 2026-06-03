"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-02

"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "competitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("invite_code", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_competitions_invite_code", "competitions", ["invite_code"], unique=True)

    op.create_table(
        "competition_participants",
        sa.Column("competition_id", UUID(as_uuid=True), sa.ForeignKey("competitions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_competition_participants_user_id", "competition_participants", ["user_id"])

    op.create_table(
        "cached_stadiums",
        sa.Column("stadium_id", sa.String(10), primary_key=True),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("city_en", sa.String(255), nullable=False),
        sa.Column("country_en", sa.String(255), nullable=False),
        sa.Column("raw_data", JSONB, nullable=False),
    )

    op.create_table(
        "cached_teams",
        sa.Column("team_id", sa.String(10), primary_key=True),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.Column("fifa_code", sa.String(10), nullable=False),
        sa.Column("groups", sa.String(5), nullable=False),
        sa.Column("flag", sa.String(500), nullable=True),
        sa.Column("raw_data", JSONB, nullable=False),
    )

    op.create_table(
        "cached_matches",
        sa.Column("match_id", sa.Integer, primary_key=True),
        sa.Column("raw_data", JSONB, nullable=False),
        sa.Column("finished", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("kickoff_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stadium_id", sa.String(10), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cached_matches_finished", "cached_matches", ["finished"])

    op.create_table(
        "bets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("competition_id", UUID(as_uuid=True), sa.ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("match_id", sa.Integer, sa.ForeignKey("cached_matches.match_id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predicted_home_score", sa.Integer, nullable=False),
        sa.Column("predicted_away_score", sa.Integer, nullable=False),
        sa.Column("predicted_top_scorer", sa.String(255), nullable=True),
        sa.Column("points", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("competition_id", "match_id", "user_id", name="uq_bet_competition_match_user"),
    )
    op.create_index("ix_bets_competition_id", "bets", ["competition_id"])
    op.create_index("ix_bets_match_id", "bets", ["match_id"])
    op.create_index("ix_bets_user_id", "bets", ["user_id"])


def downgrade() -> None:
    op.drop_table("bets")
    op.drop_table("cached_matches")
    op.drop_table("cached_teams")
    op.drop_table("cached_stadiums")
    op.drop_table("competition_participants")
    op.drop_table("competitions")
    op.drop_table("users")
