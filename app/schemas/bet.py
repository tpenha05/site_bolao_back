import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class BetCreate(BaseModel):
    competition_id: uuid.UUID
    match_id: int
    predicted_home_score: int
    predicted_away_score: int
    predicted_top_scorer: Optional[str] = None


class BetResponse(BaseModel):
    id: uuid.UUID
    competition_id: uuid.UUID
    match_id: int
    user_id: uuid.UUID
    predicted_home_score: int
    predicted_away_score: int
    predicted_top_scorer: Optional[str]
    points: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BetPublic(BaseModel):
    user_id: uuid.UUID
    user_name: str
    predicted_home_score: int
    predicted_away_score: int
    predicted_top_scorer: Optional[str]
    points: Optional[int]


class MatchBets(BaseModel):
    match_id: int
    match_started: bool
    bets: List[BetPublic]


class CompetitionBetsResponse(BaseModel):
    competition_id: uuid.UUID
    matches: List[MatchBets]
