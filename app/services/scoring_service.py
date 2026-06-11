import re
import unicodedata
from collections import Counter
from typing import Optional
from sqlalchemy.orm import Session

from app.models.bet import Bet
from app.models.match import CachedMatch


_QUOTE_CHARS = "\"'“”‘’"
# Sufixo de minuto que a API anexa ao nome: " 9'", " 67'", " 90+2'".
# A apóstrofe é opcional porque o strip de aspas já pode tê-la consumido.
_MINUTE_SUFFIX = re.compile(r"\s+\d+(?:\+\d+)?\s*['’]?\s*$")


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


def _normalize_name(name: str) -> str:
    """Normaliza nome para comparação: minúsculas, sem acentos, sem espaços extras."""
    stripped = name.strip().lower()
    nfd = unicodedata.normalize("NFD", stripped)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


def _parse_scorers(scorers_field) -> list[str]:
    """Converte 'home_scorers'/'away_scorers' da API em lista normalizada.

    A API envia no formato Postgres-array com aspas e minuto do gol:
        {"J. Quiñones 9'","R. Jiménez 67'"}
    Remove braces externas, aspas (retas e curvas) e o sufixo de minuto.
    Nomes repetidos representam múltiplos gols do mesmo jogador.
    Trata também: None, 'null' (string), string vazia.
    """
    if not scorers_field:
        return []
    raw = str(scorers_field).strip()
    if not raw or raw.lower() == "null":
        return []
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]
    cleaned: list[str] = []
    for p in raw.split(","):
        name = p.strip().strip(_QUOTE_CHARS).strip()
        name = _MINUTE_SUFFIX.sub("", name).strip()
        if name:
            cleaned.append(_normalize_name(name))
    return cleaned


def compute_top_scorers(home_scorers_field, away_scorers_field) -> set[str]:
    """Retorna o set de nomes normalizados empatados no maior número de gols.

    Combina os artilheiros dos dois times — quem fez mais gols no jogo, indepen-
    dente do lado. Em caso de empate, todos os líderes contam.
    """
    all_scorers = _parse_scorers(home_scorers_field) + _parse_scorers(away_scorers_field)
    if not all_scorers:
        return set()
    counts = Counter(all_scorers)
    max_goals = max(counts.values())
    return {name for name, n in counts.items() if n == max_goals}


def calculate_points(
    predicted_home: int,
    predicted_away: int,
    actual_home: int,
    actual_away: int,
    predicted_scorer: Optional[str],
    actual_top_scorers: set[str],
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
        and actual_top_scorers
        and _normalize_name(predicted_scorer) in actual_top_scorers
    ):
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
        actual_top_scorers = compute_top_scorers(
            raw.get("home_scorers"), raw.get("away_scorers")
        )

        bets = self.db.query(Bet).filter(Bet.match_id == match_id).all()
        updated = 0
        for bet in bets:
            pts = calculate_points(
                bet.predicted_home_score,
                bet.predicted_away_score,
                actual_home,
                actual_away,
                bet.predicted_top_scorer,
                actual_top_scorers,
            )
            bet.points = pts
            updated += 1

        self.db.commit()
        return updated

    def score_pending_finished_matches(self) -> int:
        """Pontua apostas (points IS NULL) de jogos já finalizados.

        Chamado a cada list_matches para que o ranking reflita resultados
        automaticamente. Lê os artilheiros direto do raw_data da API externa.
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
