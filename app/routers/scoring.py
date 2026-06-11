from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.bet import Bet
from app.models.match import CachedMatch
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/scoring", tags=["scoring"], dependencies=[Depends(require_admin)])


class RecomputeResponse(BaseModel):
    match_id: int | None = None
    updated_bets: int
    message: str


class RecomputeAllResponse(BaseModel):
    processed_matches: int
    updated_bets: int
    message: str


@router.post("/recompute/{match_id}", response_model=RecomputeResponse)
def recompute_match(match_id: int, db: Session = Depends(get_db)):
    """Zera points das apostas do jogo e recalcula a partir do raw_data atual."""
    cached = db.get(CachedMatch, match_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Jogo não encontrado no cache")

    db.query(Bet).filter(Bet.match_id == match_id).update({Bet.points: None})
    db.commit()

    updated = ScoringService(db).update_match_scores(match_id)
    return RecomputeResponse(
        match_id=match_id,
        updated_bets=updated,
        message=f"{updated} aposta(s) recalculada(s) para o jogo {match_id}.",
    )


@router.post("/recompute-all", response_model=RecomputeAllResponse)
def recompute_all(db: Session = Depends(get_db)):
    """Zera points de todas as apostas em jogos finalizados e recalcula tudo."""
    finished_match_ids = [
        mid for (mid,) in db.query(CachedMatch.match_id)
        .filter(CachedMatch.finished.is_(True))
        .all()
    ]
    if not finished_match_ids:
        return RecomputeAllResponse(
            processed_matches=0,
            updated_bets=0,
            message="Nenhum jogo finalizado para recalcular.",
        )

    db.query(Bet).filter(Bet.match_id.in_(finished_match_ids)).update(
        {Bet.points: None}, synchronize_session=False
    )
    db.commit()

    service = ScoringService(db)
    total_bets = 0
    processed = 0
    for mid in finished_match_ids:
        try:
            total_bets += service.update_match_scores(mid)
            processed += 1
        except HTTPException:
            continue

    return RecomputeAllResponse(
        processed_matches=processed,
        updated_bets=total_bets,
        message=f"{total_bets} aposta(s) recalculada(s) em {processed} jogo(s).",
    )
