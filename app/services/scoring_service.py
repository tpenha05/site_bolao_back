from typing import Optional
from sqlalchemy.orm import Session

from app.models.bet import Bet
from app.models.match import CachedMatch


def _coerce_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_result(home: int, away: int) -> str:
    if home > away:
        return "home"
    if away > home:
        return "away"
    return "draw"


def calculate_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
    predicted_scorer: Optional[str],
    actual_scorer: Optional[str],
) -> int:
    if predicted_home == actual_home and predicted_away == actual_away:
        points = 5
    elif _get_result(predicted_home, predicted_away) == _get_result(actual_home, actual_away):
        points = 2
    else:
        points = 0

    if (
        points > 0
        and predicted_scorer
        and actual_scorer
        and predicted_scorer.strip().lower() == actual_scorer.strip().lower()
    ):
        points += 1

    return points


class ScoringService:
    def __init__(self, db: Session):
        self.db = db

    def update_match_scores(self, match_id: int, top_scorer: Optional[str] = None) -> int:
        cached_match = self.db.get(CachedMatch, match_id)
        if not cached_match:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Jogo não encontrado no cache")

        raw = cached_match.raw_data or {}
        finished = str(raw.get("finished", "FALSE")).upper() == "TRUE"
        if not finished:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="O jogo ainda não terminou")

        actual_home = _coerce_int(raw.get("home_score"))
        actual_away = _coerce_int(raw.get("away_score"))

        bets = self.db.query(Bet).filter(Bet.match_id == match_id).all()
        updated = 0
        for bet in bets:
            pts = calculate_points(
                bet.predicted_home_score,
                bet.predicted_away_score,
                actual_home,
                actual_away,
                bet.predicted_top_scorer,
                top_scorer,
            )
            bet.points = pts
            updated += 1

        self.db.commit()
        return updated

    def score_pending_finished_matches(self) -> int:
        """Pontua apostas (points IS NULL) de jogos já finalizados.

        Chamado a cada list_matches para que o ranking reflita resultados
        sem depender de ação manual do admin. Artilheiro fica None aqui;
        admin pode rodar POST /scoring/update/{id} depois para aplicar bônus.
        """
        pending_match_ids = (
            self.db.query(Bet.match_id)
            .join(CachedMatch, CachedMatch.match_id == Bet.match_id)
            .filter(Bet.points.is_(None), CachedMatch.finished.is_(True))
            .distinct()
            .all()
        )
        total = 0
        for (match_id,) in pending_match_ids:
            try:
                total += self.update_match_scores(match_id, top_scorer=None)
            except Exception:
                # não derruba a request da listagem se um jogo específico falhar
                continue
        return total
