import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers.agents import router as agents_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.rounds import router as rounds_router

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SKILL_MD = os.path.join(os.path.dirname(__file__), "..", "SKILL.md")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Claw Council",
    description="Multi-agent coordination backend with discrete rounds.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router, prefix="/agents", tags=["Agents"])
app.include_router(rounds_router, prefix="/rounds", tags=["Rounds"])
app.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard"])

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/skill", include_in_schema=False)
def skill():
    return FileResponse(os.path.abspath(SKILL_MD), media_type="text/plain")
