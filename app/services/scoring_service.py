from typing import Optional
from sqlalchemy.orm import Session

from app.models.bet import Bet
from app.models.match import CachedMatch


def _coerce_int(value, default: Optional[int] = 0) -> Optional[int]:
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


def _shootout_winner(raw: dict) -> Optional[str]:
    """Retorna 'home'/'away' se o jogo foi decidido nos pênaltis, senão None.

    Considera pênaltis quando o placar regular é empate e a API traz
    home_penalty_score e away_penalty_score numéricos distintos.
    """
    home = _coerce_int(raw.get("home_score"), None)
    away = _coerce_int(raw.get("away_score"), None)
    if home is None or away is None or home != away:
        return None
    home_pk = _coerce_int(raw.get("home_penalty_score"), None)
    away_pk = _coerce_int(raw.get("away_penalty_score"), None)
    if home_pk is None or away_pk is None or home_pk == away_pk:
        return None
    return "home" if home_pk > away_pk else "away"


def calculate_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
    predicted_classifier: Optional[str],
    shootout_winner: Optional[str],
) -> int:
    predicted_result = _get_result(predicted_home, predicted_away)
    exact = predicted_home == actual_home and predicted_away == actual_away
    same_result = predicted_result == _get_result(actual_home, actual_away)

    if exact:
        points = 5
    elif same_result:
        points = 2
    else:
        points = 0

    if shootout_winner:
        if predicted_result == "draw":
            if predicted_classifier == shootout_winner:
                points += 1
        else:
            # Vitória prevista para o time que se classificou nos pênaltis.
            if predicted_result == shootout_winner:
                points += 1

    return points


class ScoringService:
    def __init__(self, db: Session):
        self.db = db

    def update_match_scores(self, match_id: int) -> int:
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
        shootout = _shootout_winner(raw)

        bets = self.db.query(Bet).filter(Bet.match_id == match_id).all()
        updated = 0
        for bet in bets:
            pts = calculate_points(
                bet.predicted_home_score,
                bet.predicted_away_score,
                actual_home,
                actual_away,
                bet.predicted_classifier,
                shootout,
            )
            bet.points = pts
            updated += 1

        self.db.commit()
        return updated

    def score_pending_finished_matches(self) -> int:
        """Pontua apostas (points IS NULL) de jogos já finalizados.

        Chamado a cada list_matches para que o ranking reflita resultados
        automaticamente.
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
                total += self.update_match_scores(match_id)
            except Exception:
                continue
        return total
