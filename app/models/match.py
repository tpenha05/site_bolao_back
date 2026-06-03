from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CachedMatch(Base):
    __tablename__ = "cached_matches"

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    finished: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    kickoff_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stadium_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CachedStadium(Base):
    __tablename__ = "cached_stadiums"

    stadium_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    city_en: Mapped[str] = mapped_column(String(255), nullable=False)
    country_en: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)


class CachedTeam(Base):
    __tablename__ = "cached_teams"

    team_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    fifa_code: Mapped[str] = mapped_column(String(10), nullable=False)
    groups: Mapped[str] = mapped_column(String(5), nullable=False)
    flag: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
