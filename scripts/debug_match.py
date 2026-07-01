"""Diagnóstico de pontuação para um jogo — imprime raw_data e apostas.

Uso: python scripts/debug_match.py 75
"""
import json
import sys
from app.database import SessionLocal
from app.models.bet import Bet
from app.models.match import CachedMatch
from app.services.scoring_service import (
    _shootout_winner,
    calculate_points,
    _coerce_int,
)


def main(match_id: int) -> None:
    db = SessionLocal()
    try:
        cached = db.get(CachedMatch, match_id)
        if not cached:
            print(f"Match {match_id} nao esta no cache.")
            return

        raw = cached.raw_data or {}
        print(f"=== Match {match_id} raw_data (campos relevantes) ===")
        for k in (
            "finished", "home_score", "away_score",
            "home_penalty_score", "away_penalty_score",
            "home_team_id", "away_team_id",
            "home_team_name_en", "away_team_name_en",
            "type", "matchday",
        ):
            print(f"  {k}: {raw.get(k)!r}")

        shootout = _shootout_winner(raw)
        actual_home = _coerce_int(raw.get("home_score"))
        actual_away = _coerce_int(raw.get("away_score"))
        print(f"\nDetectado shootout_winner = {shootout!r}")
        print(f"Placar interpretado: {actual_home} x {actual_away}")

        bets = db.query(Bet).filter(Bet.match_id == match_id).all()
        print(f"\n=== {len(bets)} apostas ===")
        for b in bets:
            expected = calculate_points(
                b.predicted_home_score,
                b.predicted_away_score,
                actual_home,
                actual_away,
                b.predicted_classifier,
                shootout,
            )
            marker = "OK" if expected == b.points else "!!"
            print(
                f"  {marker} user={b.user_id} "
                f"palpite={b.predicted_home_score}x{b.predicted_away_score} "
                f"classif={b.predicted_classifier!r} "
                f"points_no_db={b.points} esperado={expected}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    mid = int(sys.argv[1]) if len(sys.argv) > 1 else 75
    main(mid)
