from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.services.scoring_service import ScoringService
from app.schemas.scoring import ScoringUpdateRequest, ScoringResult

router = APIRouter(prefix="/scoring", tags=["scoring"])


@router.post("/update/{match_id}", response_model=ScoringResult, dependencies=[Depends(require_admin)])
def update_match_scoring(
    match_id: int,
    body: ScoringUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        service = ScoringService(db)
        updated = service.update_match_scores(match_id, top_scorer=body.top_scorer)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return ScoringResult(
        match_id=match_id,
        bets_updated=updated,
        message=f"Pontuação calculada para {updated} apostas no jogo {match_id}.",
    )
