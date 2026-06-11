import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.routers import auth, competitions, matches, bets, scoring

app = FastAPI(
    title="Bolão da Copa 2026",
    description="API para bolão de apostas na Copa do Mundo 2026",
    version="1.0.0",
)

cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(competitions.router)
app.include_router(matches.router)
app.include_router(bets.router)
app.include_router(scoring.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
