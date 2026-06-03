from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, require_admin
from app.models.user import User
from app.models.match import CachedMatch, CachedTeam
from app.services.match_service import MatchService
from app.services.scoring_service import ScoringService
from app.schemas.match import MatchResponse, MatchDetailResponse, SyncResponse, TeamInfo


class CurrentRoundResponse(BaseModel):
    matchday: int

router = APIRouter(prefix="/matches", tags=["matches"])


def _match_to_response(m: CachedMatch) -> MatchResponse:
    return MatchResponse(
        match_id=m.match_id,
        finished=m.finished,
        kickoff_utc=m.kickoff_utc,
        data=m.raw_data,
    )


def _team_to_info(team: Optional[CachedTeam]) -> Optional[TeamInfo]:
    if not team:
        return None
    return TeamInfo(
        id=team.team_id,
        name_en=team.name_en,
        fifa_code=team.fifa_code,
        flag=team.flag,
    )


def _match_to_detail(m: CachedMatch, service: MatchService) -> MatchDetailResponse:
    raw = m.raw_data or {}
    home_team = _team_to_info(service.get_team(raw.get("home_team_id", "0")))
    away_team = _team_to_info(service.get_team(raw.get("away_team_id", "0")))
    return MatchDetailResponse(
        match_id=m.match_id,
        finished=m.finished,
        kickoff_utc=m.kickoff_utc,
        data=raw,
        home_team=home_team,
        away_team=away_team,
    )


@router.get("", response_model=List[MatchDetailResponse])
def list_matches(
    round: Optional[int] = None,
    date: Optional[str] = None,
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = MatchService(db)
    matches = service.list_matches(round=round, date=date, stage=stage)

    # Pontua automaticamente apostas pendentes de jogos finalizados.
    # Roda só se houver alguma rodada finalizada na consulta atual — barato.
    if any(m.finished for m in matches):
        try:
            ScoringService(db).score_pending_finished_matches()
        except Exception:
            pass

    # Coleta todos os IDs de times únicos e carrega em uma única query — elimina N+1
    team_ids: set = set()
    for m in matches:
        raw = m.raw_data or {}
        team_ids.add(raw.get("home_team_id", "0"))
        team_ids.add(raw.get("away_team_id", "0"))
    teams_map = service.get_teams_batch(team_ids)

    # Se algum time referenciado (não-TBD) está faltando no cache, sincroniza todos
    # uma vez e recarrega — evita devolver home_team/away_team nulos na fase de grupos.
    expected_ids = {tid for tid in team_ids if tid and tid != "0"}
    if expected_ids - set(teams_map.keys()):
        service.sync_all_teams()
        teams_map = service.get_teams_batch(team_ids)

    result = []
    for m in matches:
        raw = m.raw_data or {}
        home_id = raw.get("home_team_id", "0")
        away_id = raw.get("away_team_id", "0")
        result.append(MatchDetailResponse(
            match_id=m.match_id,
            finished=m.finished,
            kickoff_utc=m.kickoff_utc,
            data=raw,
            home_team=_team_to_info(teams_map.get(home_id)),
            away_team=_team_to_info(teams_map.get(away_id)),
        ))
    return result


@router.get("/current-round", response_model=CurrentRoundResponse)
def get_current_round(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rodada do próximo jogo a acontecer (ou em andamento). Cai para a última se tudo já passou."""
    service = MatchService(db)
    # garante cache populado
    if db.query(CachedMatch).count() < 10:
        service.sync_all_matches()

    now = datetime.now(timezone.utc)
    matches = db.query(CachedMatch).all()

    upcoming_md: Optional[int] = None
    upcoming_kickoff: Optional[datetime] = None
    last_md = 1

    for m in matches:
        raw = m.raw_data or {}
        try:
            md = int(raw.get("matchday", 0))
        except (TypeError, ValueError):
            continue
        if md < 1:
            continue
        if md > last_md:
            last_md = md
        if not m.kickoff_utc:
            continue
        ko = m.kickoff_utc if m.kickoff_utc.tzinfo else m.kickoff_utc.replace(tzinfo=timezone.utc)
        # "em andamento" = começou há menos de 3h (jogo + intervalo + acréscimos)
        if (ko - now).total_seconds() > -3 * 3600:
            if upcoming_kickoff is None or ko < upcoming_kickoff:
                upcoming_kickoff = ko
                upcoming_md = md

    return CurrentRoundResponse(matchday=upcoming_md or last_md)


@router.get("/{match_id}", response_model=MatchDetailResponse)
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if match_id < 1 or match_id > 104:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")
    service = MatchService(db)
    try:
        match = service.get_match(match_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao buscar jogo na API externa: {exc}")

    raw = match.raw_data or {}
    home_team_id = raw.get("home_team_id", "0")
    away_team_id = raw.get("away_team_id", "0")
    home_team = _team_to_info(service.get_team(home_team_id))
    away_team = _team_to_info(service.get_team(away_team_id))

    return MatchDetailResponse(
        match_id=match.match_id,
        finished=match.finished,
        kickoff_utc=match.kickoff_utc,
        data=raw,
        home_team=home_team,
        away_team=away_team,
    )


@router.post("/sync", response_model=SyncResponse, dependencies=[Depends(require_admin)])
def sync_matches(db: Session = Depends(get_db)):
    service = MatchService(db)
    synced, errors = service.sync_all_matches()
    return SyncResponse(
        synced=synced,
        errors=errors,
        message=f"Sincronização concluída: {synced} jogos atualizados, {errors} erros.",
    )
