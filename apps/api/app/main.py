from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, auth, company, oauth, teams
from db.session import SessionLocal, check_db_connection
from services.seed import ensure_super_admin
from services.teams_platform import ensure_teams_platform_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        ensure_super_admin(db)
        ensure_teams_platform_config(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI Dev Platform API",
    description="Multi-tenant AI development automation platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(company.router)
app.include_router(teams.router)
app.include_router(oauth.router)


@app.get("/health")
def health_check() -> dict:
    db_ok = False
    try:
        db_ok = check_db_connection()
    except Exception:
        pass
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}


@app.get("/")
def root() -> dict:
    return {"message": "AI Dev Platform API", "docs": "/docs"}
