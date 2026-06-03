from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel


class TeamInfo(BaseModel):
    id: str
    name_en: str
    fifa_code: str
    flag: Optional[str]


class MatchResponse(BaseModel):
    match_id: int
    finished: bool
    kickoff_utc: Optional[datetime]
    data: Dict[str, Any]

    model_config = {"from_attributes": True}


class MatchDetailResponse(BaseModel):
    match_id: int
    finished: bool
    kickoff_utc: Optional[datetime]
    data: Dict[str, Any]
    home_team: Optional[TeamInfo]
    away_team: Optional[TeamInfo]

    model_config = {"from_attributes": True}


class SyncResponse(BaseModel):
    synced: int
    errors: int
    message: str
