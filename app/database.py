import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./claw_council.db")

# Render/Heroku use postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs check_same_thread=False; other DBs don't accept that arg
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def run_schema_migrations():
    """Add missing columns to existing tables (e.g. after deploy to DB created before is_removed existed)."""
    # Postgres supports ADD COLUMN IF NOT EXISTS; SQLite 3.35+ does too
    migrations = [
        "ALTER TABLE proposals ADD COLUMN IF NOT EXISTS is_removed BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE critiques ADD COLUMN IF NOT EXISTS is_removed BOOLEAN NOT NULL DEFAULT FALSE",
    ]
    for sql in migrations:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
            logger.info("Migration applied: %s", sql[:60] + "...")
        except Exception as e:
            # SQLite < 3.35 lacks IF NOT EXISTS; column may already exist; table may not exist yet
            logger.debug("Migration skip or fail (may be ok): %s", e)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
