import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel


ClassifierSide = Literal["home", "away"]


class BetCreate(BaseModel):
    competition_id: uuid.UUID
    match_id: int
    predicted_home_score: int
    predicted_away_score: int
    predicted_classifier: Optional[ClassifierSide] = None


class BetResponse(BaseModel):
    id: uuid.UUID
    competition_id: uuid.UUID
    match_id: int
    user_id: uuid.UUID
    predicted_home_score: int
    predicted_away_score: int
    # Response tolera valores legados (nome do time em vez de 'home'/'away')
    predicted_classifier: Optional[str]
    points: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BetPublic(BaseModel):
    user_id: uuid.UUID
    user_name: str
    predicted_home_score: int
    predicted_away_score: int
    predicted_classifier: Optional[str]
    points: Optional[int]


class MatchBets(BaseModel):
    match_id: int
    match_started: bool
    bets: List[BetPublic]


class CompetitionBetsResponse(BaseModel):
    competition_id: uuid.UUID
    matches: List[MatchBets]
