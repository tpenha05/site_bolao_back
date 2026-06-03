import os
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt

from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(user_id: str) -> str:
    expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, os.getenv("JWT_SECRET", ""), algorithm="HS256")


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user = User(
        name=body.name,
        email=body.email,
        hashed_password=_hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = _create_token(str(user.id))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not _verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    token = _create_token(str(user.id))
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
