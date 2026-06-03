import os
import uuid
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from app.database import SessionLocal
from app.models.user import User

security = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET", ""), algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    user = db.get(User, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")
    return user


def require_admin(x_admin_key: str = Header(default=None)):
    admin_key = os.getenv("ADMIN_API_KEY")
    if not admin_key or x_admin_key != admin_key:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
