import secrets
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.competition import Competition, CompetitionParticipant
from app.models.bet import Bet
from app.schemas.competition import (
    CompetitionCreate,
    CompetitionResponse,
    CompetitionDetailResponse,
    JoinCompetitionRequest,
    InviteCodeResponse,
    ParticipantRank,
)

router = APIRouter(prefix="/competitions", tags=["competitions"])


def _generate_invite_code() -> str:
    return secrets.token_hex(4).upper()


def _build_response(competition: Competition, is_admin: bool) -> CompetitionResponse:
    return CompetitionResponse(
        id=competition.id,
        name=competition.name,
        description=competition.description,
        invite_code=competition.invite_code,
        created_at=competition.created_at,
        is_admin=is_admin,
    )


@router.post("", response_model=CompetitionResponse, status_code=201)
def create_competition(
    body: CompetitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    code = _generate_invite_code()
    while db.query(Competition).filter(Competition.invite_code == code).first():
        code = _generate_invite_code()

    competition = Competition(name=body.name, description=body.description, invite_code=code)
    db.add(competition)
    db.flush()

    participant = CompetitionParticipant(
        competition_id=competition.id,
        user_id=current_user.id,
        is_admin=True,
    )
    db.add(participant)
    db.commit()
    db.refresh(competition)
    return _build_response(competition, is_admin=True)


@router.get("", response_model=List[CompetitionResponse])
def list_competitions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Competition, CompetitionParticipant.is_admin)
        .join(CompetitionParticipant, CompetitionParticipant.competition_id == Competition.id)
        .filter(CompetitionParticipant.user_id == current_user.id)
        .all()
    )
    return [_build_response(comp, is_admin) for comp, is_admin in rows]


@router.get("/{competition_id}", response_model=CompetitionDetailResponse)
def get_competition(
    competition_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participant = db.query(CompetitionParticipant).filter_by(
        competition_id=competition_id, user_id=current_user.id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Competição não encontrada ou acesso negado")

    competition = db.get(Competition, competition_id)

    ranking_rows = (
        db.query(
            User.id.label("user_id"),
            User.name.label("user_name"),
            func.coalesce(func.sum(Bet.points), 0).label("total_points"),
            func.count(Bet.id).label("bets_count"),
        )
        .join(CompetitionParticipant, CompetitionParticipant.user_id == User.id)
        .outerjoin(
            Bet,
            (Bet.user_id == User.id) & (Bet.competition_id == competition_id),
        )
        .filter(CompetitionParticipant.competition_id == competition_id)
        .group_by(User.id, User.name)
        .order_by(func.coalesce(func.sum(Bet.points), 0).desc())
        .all()
    )

    participants = [
        ParticipantRank(
            user_id=row.user_id,
            user_name=row.user_name,
            total_points=int(row.total_points),
            bets_count=int(row.bets_count),
        )
        for row in ranking_rows
    ]

    return CompetitionDetailResponse(
        id=competition.id,
        name=competition.name,
        description=competition.description,
        invite_code=competition.invite_code,
        created_at=competition.created_at,
        is_admin=participant.is_admin,
        participants=participants,
    )


@router.post("/{competition_id}/invite", response_model=InviteCodeResponse)
def rotate_invite_code(
    competition_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participant = db.query(CompetitionParticipant).filter_by(
        competition_id=competition_id, user_id=current_user.id, is_admin=True
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Somente administradores podem gerar convites")

    competition = db.get(Competition, competition_id)
    new_code = _generate_invite_code()
    while db.query(Competition).filter(Competition.invite_code == new_code).first():
        new_code = _generate_invite_code()

    competition.invite_code = new_code
    db.commit()
    return InviteCodeResponse(invite_code=new_code)


@router.post("/join", response_model=CompetitionResponse)
def join_competition(
    body: JoinCompetitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    competition = db.query(Competition).filter(Competition.invite_code == body.invite_code).first()
    if not competition:
        raise HTTPException(status_code=404, detail="Código de convite inválido")

    existing = db.query(CompetitionParticipant).filter_by(
        competition_id=competition.id, user_id=current_user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Você já participa desta competição")

    participant = CompetitionParticipant(
        competition_id=competition.id,
        user_id=current_user.id,
        is_admin=False,
    )
    db.add(participant)
    db.commit()
    return _build_response(competition, is_admin=False)


@router.delete("/{competition_id}", status_code=204)
def delete_competition(
    competition_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participant = db.query(CompetitionParticipant).filter_by(
        competition_id=competition_id, user_id=current_user.id, is_admin=True
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail="Somente administradores podem encerrar a competição")

    competition = db.get(Competition, competition_id)
    db.delete(competition)
    db.commit()
