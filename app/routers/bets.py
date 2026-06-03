import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.competition import CompetitionParticipant
from app.models.match import CachedMatch
from app.models.bet import Bet
from app.services.match_service import MatchService
from app.schemas.bet import BetCreate, BetResponse, CompetitionBetsResponse, MatchBets, BetPublic

router = APIRouter(prefix="/bets", tags=["bets"])


def _match_started(cached: Optional[CachedMatch]) -> bool:
    if not cached or not cached.kickoff_utc:
        return False
    now = datetime.now(timezone.utc)
    kickoff = cached.kickoff_utc
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    return now >= kickoff


@router.post("", response_model=BetResponse, status_code=201)
def create_or_update_bet(
    body: BetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = db.query(CompetitionParticipant).filter_by(
        competition_id=body.competition_id, user_id=current_user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Você não participa desta competição")

    service = MatchService(db)
    try:
        cached_match = service.get_match(body.match_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar jogo: {exc}")

    if _match_started(cached_match):
        raise HTTPException(status_code=403, detail="Apostas encerradas — o jogo já começou")

    existing = db.query(Bet).filter_by(
        competition_id=body.competition_id,
        match_id=body.match_id,
        user_id=current_user.id,
    ).first()

    if existing:
        existing.predicted_home_score = body.predicted_home_score
        existing.predicted_away_score = body.predicted_away_score
        existing.predicted_top_scorer = body.predicted_top_scorer
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return BetResponse.model_validate(existing)

    bet = Bet(
        competition_id=body.competition_id,
        match_id=body.match_id,
        user_id=current_user.id,
        predicted_home_score=body.predicted_home_score,
        predicted_away_score=body.predicted_away_score,
        predicted_top_scorer=body.predicted_top_scorer,
    )
    db.add(bet)
    db.commit()
    db.refresh(bet)
    return BetResponse.model_validate(bet)


@router.get("", response_model=BetResponse)
def get_my_bet(
    competition_id: uuid.UUID,
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bet = db.query(Bet).filter_by(
        competition_id=competition_id,
        match_id=match_id,
        user_id=current_user.id,
    ).first()
    if not bet:
        raise HTTPException(status_code=404, detail="Aposta não encontrada")
    return BetResponse.model_validate(bet)


@router.get("/competition/{competition_id}", response_model=CompetitionBetsResponse)
def get_competition_bets(
    competition_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    membership = db.query(CompetitionParticipant).filter_by(
        competition_id=competition_id, user_id=current_user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Você não participa desta competição")

    all_bets = (
        db.query(Bet, User.name.label("user_name"))
        .join(User, User.id == Bet.user_id)
        .filter(Bet.competition_id == competition_id)
        .all()
    )

    matches_map: dict[int, list] = {}
    for bet, user_name in all_bets:
        matches_map.setdefault(bet.match_id, []).append((bet, user_name))

    match_bets_list: List[MatchBets] = []
    for match_id, bet_pairs in sorted(matches_map.items()):
        cached = db.get(CachedMatch, match_id)
        started = _match_started(cached)

        visible_bets: List[BetPublic] = []
        for bet, user_name in bet_pairs:
            if not started and bet.user_id != current_user.id:
                continue
            visible_bets.append(BetPublic(
                user_id=bet.user_id,
                user_name=user_name,
                predicted_home_score=bet.predicted_home_score,
                predicted_away_score=bet.predicted_away_score,
                predicted_top_scorer=bet.predicted_top_scorer,
                points=bet.points,
            ))

        match_bets_list.append(MatchBets(
            match_id=match_id,
            match_started=started,
            bets=visible_bets,
        ))

    return CompetitionBetsResponse(competition_id=competition_id, matches=match_bets_list)
