from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Round, ScoreEvent
from app.schemas import LeaderboardEntry, LeaderboardOut, ScoreEventOut

router = APIRouter()


@router.get("", response_model=LeaderboardOut)
def get_leaderboard(db: Session = Depends(get_db)):
    agents = db.query(Agent).order_by(Agent.total_score.desc()).all()

    # Count distinct rounds each agent participated in (via score_events)
    participation_counts: dict[int, int] = {}
    rows = (
        db.query(ScoreEvent.agent_id, func.count(ScoreEvent.round_id.distinct()))
        .filter(ScoreEvent.reason == "participation")
        .group_by(ScoreEvent.agent_id)
        .all()
    )
    for agent_id, count in rows:
        participation_counts[agent_id] = count

    entries = []
    for rank, agent in enumerate(agents, start=1):
        entries.append(
            LeaderboardEntry(
                rank=rank,
                agent_id=agent.id,
                name=agent.name,
                total_score=agent.total_score,
                rounds_participated=participation_counts.get(agent.id, 0),
            )
        )

    return LeaderboardOut(entries=entries, as_of=datetime.utcnow())


@router.get("/rounds/{round_id}", response_model=list[ScoreEventOut])
def get_round_scores(round_id: int, db: Session = Depends(get_db)):
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return db.query(ScoreEvent).filter(ScoreEvent.round_id == round_id).all()
