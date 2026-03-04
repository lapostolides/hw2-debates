import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers.agents import router as agents_router
from app.routers.leaderboard import router as leaderboard_router
from app.routers.rounds import router as rounds_router

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


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


@app.exception_handler(Exception)
async def log_unhandled_exceptions(request: Request, exc: Exception):
    """Log full traceback for 500s so Render logs show the cause."""
    logger.error(
        "Unhandled exception: %s\nPath: %s %s\n%s",
        exc,
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for traceback."},
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


@app.get("/SKILL.md", include_in_schema=False)
def skill():
    skill_path = os.path.join(os.path.dirname(__file__), "..", "SKILL.md")
    with open(os.path.abspath(skill_path)) as f:
        content = f.read()
    return PlainTextResponse(content)
