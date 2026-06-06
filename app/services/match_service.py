import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import pytz
from sqlalchemy.orm import Session

from app.models.match import CachedMatch, CachedStadium, CachedTeam

EXTERNAL_API_BASE = "https://worldcup26.ir"
CACHE_TTL_SECONDS = 300  # 5 minutos para jogos não finalizados

# Mapeamento de cidade/país → fuso horário das sedes da Copa 2026
_CITY_TIMEZONE: dict[str, str] = {
    "east rutherford": "America/New_York",
    "new york": "America/New_York",
    "new jersey": "America/New_York",
    "dallas": "America/Chicago",
    "los angeles": "America/Los_Angeles",
    "inglewood": "America/Los_Angeles",
    "santa clara": "America/Los_Angeles",
    "miami": "America/New_York",
    "miami gardens": "America/New_York",
    "atlanta": "America/New_York",
    "houston": "America/Chicago",
    "philadelphia": "America/New_York",
    "foxborough": "America/New_York",
    "boston": "America/New_York",
    "seattle": "America/Los_Angeles",
    "kansas city": "America/Chicago",
    "mexico city": "America/Mexico_City",
    "ciudad de mexico": "America/Mexico_City",
    "guadalajara": "America/Mexico_City",
    "monterrey": "America/Monterrey",
    "vancouver": "America/Vancouver",
    "toronto": "America/Toronto",
}


def _resolve_timezone(city_en: str, country_en: str) -> str:
    city_lower = city_en.lower()
    for key, tz in _CITY_TIMEZONE.items():
        if key in city_lower:
            return tz
    country_lower = country_en.lower()
    if "mexico" in country_lower:
        return "America/Mexico_City"
    if "canada" in country_lower:
        return "America/Toronto"
    return "UTC"


def _parse_local_date_to_utc(local_date_str: str, tz_name: str) -> Optional[datetime]:
    try:
        naive_dt = datetime.strptime(local_date_str, "%m/%d/%Y %H:%M")
        local_tz = pytz.timezone(tz_name)
        aware_dt = local_tz.localize(naive_dt)
        return aware_dt.astimezone(pytz.utc)
    except Exception:
        return None


class MatchService:
    def __init__(self, db: Session):
        self.db = db

    def _get_headers(self) -> dict:
        token = os.getenv("WORLDCUP_API_TOKEN", "")
        return {"Authorization": f"Bearer {token}"}

    def _renew_token(self) -> str:
        email = os.getenv("WORLDCUP_API_EMAIL", "")
        password = os.getenv("WORLDCUP_API_PASSWORD", "")
        response = httpx.post(
            f"{EXTERNAL_API_BASE}/auth/authenticate",
            json={"email": email, "password": password},
            timeout=10.0,
        )
        response.raise_for_status()
        token = response.json()["token"]
        self._save_token_to_env(token)
        return token

    def _save_token_to_env(self, token: str) -> None:
        os.environ["WORLDCUP_API_TOKEN"] = token
        env_path = Path(".env")
        if not env_path.exists():
            return
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("WORLDCUP_API_TOKEN="):
                new_lines.append(f"WORLDCUP_API_TOKEN={token}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"WORLDCUP_API_TOKEN={token}")
        env_path.write_text("\n".join(new_lines), encoding="utf-8")

    def _get(self, path: str) -> dict | list:
        headers = self._get_headers()
        response = httpx.get(f"{EXTERNAL_API_BASE}{path}", headers=headers, timeout=15.0)
        if response.status_code == 401:
            token = self._renew_token()
            headers["Authorization"] = f"Bearer {token}"
            response = httpx.get(f"{EXTERNAL_API_BASE}{path}", headers=headers, timeout=15.0)
        response.raise_for_status()
        return response.json()

    def _get_or_sync_stadiums(self) -> None:
        count = self.db.query(CachedStadium).count()
        if count > 0:
            return
        data = self._get("/get/stadiums")
        stadiums = data if isinstance(data, list) else data.get("stadiums", [])
        for s in stadiums:
            stadium_id = str(s.get("id", ""))
            if not stadium_id:
                continue
            existing = self.db.get(CachedStadium, stadium_id)
            if existing:
                existing.raw_data = s
                existing.name_en = s.get("name_en", "")
                existing.city_en = s.get("city_en", "")
                existing.country_en = s.get("country_en", "")
            else:
                self.db.add(CachedStadium(
                    stadium_id=stadium_id,
                    name_en=s.get("name_en", ""),
                    city_en=s.get("city_en", ""),
                    country_en=s.get("country_en", ""),
                    raw_data=s,
                ))
        self.db.commit()

    def _get_stadium_timezone(self, stadium_id: str) -> str:
        self._get_or_sync_stadiums()
        stadium = self.db.get(CachedStadium, stadium_id)
        if not stadium:
            return "UTC"
        return _resolve_timezone(stadium.city_en, stadium.country_en)

    def _cache_match_data(self, data: dict) -> CachedMatch:
        match_id = int(data["id"])
        finished = str(data.get("finished", "FALSE")).upper() == "TRUE"
        stadium_id = str(data.get("stadium_id", ""))
        local_date = data.get("local_date", "")

        kickoff_utc: Optional[datetime] = None
        if local_date and stadium_id:
            tz = self._get_stadium_timezone(stadium_id)
            kickoff_utc = _parse_local_date_to_utc(local_date, tz)

        existing = self.db.get(CachedMatch, match_id)
        if existing:
            existing.raw_data = data
            existing.finished = finished
            existing.kickoff_utc = kickoff_utc
            existing.stadium_id = stadium_id or None
            existing.last_updated = datetime.utcnow()
        else:
            existing = CachedMatch(
                match_id=match_id,
                raw_data=data,
                finished=finished,
                kickoff_utc=kickoff_utc,
                stadium_id=stadium_id or None,
                last_updated=datetime.utcnow(),
            )
            self.db.add(existing)
        self.db.commit()
        self.db.refresh(existing)
        return existing

    def _is_stale(self, cached: CachedMatch) -> bool:
        if cached.finished:
            return False
        last = cached.last_updated
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last).total_seconds()
        return age >= CACHE_TTL_SECONDS

    def get_match(self, match_id: int) -> CachedMatch:
        cached = self.db.get(CachedMatch, match_id)
        if cached and not self._is_stale(cached):
            return cached
        # /get/game/{id} da API externa retorna 400 — usamos o /get/games (lista
        # completa) para refrescar todos os jogos de uma vez. São só 104 jogos.
        self.sync_all_matches()
        refreshed = self.db.get(CachedMatch, match_id)
        if refreshed:
            return refreshed
        if cached:
            return cached
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    def get_team(self, team_id: str) -> Optional[CachedTeam]:
        if team_id == "0":
            return None
        cached = self.db.get(CachedTeam, team_id)
        if cached:
            return cached
        try:
            data = self._get(f"/get/team/{team_id}")
            team = data if isinstance(data, dict) else None
            if not team:
                return None
            obj = CachedTeam(
                team_id=str(team.get("id", team_id)),
                name_en=team.get("name_en", ""),
                fifa_code=team.get("fifa_code", ""),
                groups=team.get("groups", ""),
                flag=team.get("flag"),
                raw_data=team,
            )
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)
            return obj
        except Exception:
            return None

    def get_teams_batch(self, team_ids: set) -> dict:
        """Busca vários times de uma vez no DB — evita N+1 queries."""
        ids = {t for t in team_ids if t and t != "0"}
        if not ids:
            return {}
        teams = self.db.query(CachedTeam).filter(CachedTeam.team_id.in_(ids)).all()
        return {t.team_id: t for t in teams}

    def sync_all_teams(self) -> None:
        """Baixa todos os 48 times em uma única chamada à API externa e cacheia no DB."""
        try:
            data = self._get("/get/teams")
            teams = data if isinstance(data, list) else data.get("teams", [])
        except Exception:
            return
        for t in teams:
            team_id = str(t.get("id", ""))
            if not team_id:
                continue
            existing = self.db.get(CachedTeam, team_id)
            if existing:
                existing.name_en = t.get("name_en", "")
                existing.fifa_code = t.get("fifa_code", "")
                existing.groups = t.get("groups", "")
                existing.flag = t.get("flag")
                existing.raw_data = t
            else:
                self.db.add(CachedTeam(
                    team_id=team_id,
                    name_en=t.get("name_en", ""),
                    fifa_code=t.get("fifa_code", ""),
                    groups=t.get("groups", ""),
                    flag=t.get("flag"),
                    raw_data=t,
                ))
        self.db.commit()

    def sync_all_matches(self) -> tuple[int, int]:
        synced = 0
        errors = 0
        try:
            data = self._get("/get/games")
            games = data if isinstance(data, list) else data.get("games", [])
        except Exception:
            return 0, 1

        for game in games:
            try:
                self._cache_match_data(game)
                synced += 1
            except Exception:
                errors += 1

        # Sincroniza todos os times em uma única chamada para evitar N+1 no list_matches
        self.sync_all_teams()

        return synced, errors

    def list_matches(
        self,
        round: Optional[int] = None,
        date: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> list[CachedMatch]:
        count = self.db.query(CachedMatch).count()
        if count < 10:
            self.sync_all_matches()

        query = self.db.query(CachedMatch)
        results = query.all()

        filtered = []
        for m in results:
            raw = m.raw_data or {}
            if round is not None and str(raw.get("matchday", "")) != str(round):
                continue
            if stage is not None and raw.get("type", "") != stage:
                continue
            if date is not None and m.kickoff_utc:
                match_date = m.kickoff_utc.date().isoformat()
                if match_date != date:
                    continue
            filtered.append(m)

        return filtered
