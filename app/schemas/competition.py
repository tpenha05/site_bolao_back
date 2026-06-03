import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CompetitionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CompetitionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    invite_code: str
    created_at: datetime
    is_admin: bool

    model_config = {"from_attributes": True}


class ParticipantRank(BaseModel):
    user_id: uuid.UUID
    user_name: str
    total_points: int
    bets_count: int


class CompetitionDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    invite_code: str
    created_at: datetime
    is_admin: bool
    participants: List[ParticipantRank]

    model_config = {"from_attributes": True}


class JoinCompetitionRequest(BaseModel):
    invite_code: str


class InviteCodeResponse(BaseModel):
    invite_code: str
