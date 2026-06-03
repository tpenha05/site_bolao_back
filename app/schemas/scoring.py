from typing import Optional
from pydantic import BaseModel


class ScoringUpdateRequest(BaseModel):
    top_scorer: Optional[str] = None


class ScoringResult(BaseModel):
    match_id: int
    bets_updated: int
    message: str
