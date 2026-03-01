import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Critique, Proposal, ScoreEvent, Vote
from app.schemas import (
    ActivityItem,
    AgentActivityOut,
    AgentCreate,
    AgentOut,
    AgentPublic,
    AgentSummary,
)

router = APIRouter()


@router.post("", response_model=AgentOut, status_code=201)
def register_agent(body: AgentCreate, db: Session = Depends(get_db)):
    """Register a new agent or return the existing one with the same name."""
    existing = db.query(Agent).filter(Agent.name == body.name).first()
    if existing:
        return existing
    agent = Agent(name=body.name, api_key=str(uuid.uuid4()))
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("", response_model=list[AgentSummary])
def list_agents(db: Session = Depends(get_db)):
    """List all agents with participation stats, sorted by score."""
    agents = db.query(Agent).order_by(Agent.total_score.desc()).all()
    result = []
    for agent in agents:
        proposals_count = (
            db.query(Proposal).filter(Proposal.agent_id == agent.id).count()
        )
        critiques_count = (
            db.query(Critique).filter(Critique.agent_id == agent.id).count()
        )
        votes_count = db.query(Vote).filter(Vote.agent_id == agent.id).count()
        rounds_count = (
            db.query(ScoreEvent.round_id)
            .filter(
                ScoreEvent.agent_id == agent.id,
                ScoreEvent.reason == "participation",
            )
            .distinct()
            .count()
        )
        result.append(
            AgentSummary(
                id=agent.id,
                name=agent.name,
                total_score=agent.total_score,
                created_at=agent.created_at,
                proposals_submitted=proposals_count,
                critiques_submitted=critiques_count,
                votes_cast=votes_count,
                rounds_participated=rounds_count,
            )
        )
    return result


@router.get("/{agent_id}/activity", response_model=AgentActivityOut)
def get_agent_activity(agent_id: int, db: Session = Depends(get_db)):
    """Return the 20 most recent actions for an agent."""
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    items: list[ActivityItem] = []

    for p in (
        db.query(Proposal)
        .filter(Proposal.agent_id == agent_id)
        .order_by(Proposal.submitted_at.desc())
        .limit(10)
        .all()
    ):
        items.append(
            ActivityItem(
                type="proposal",
                round_id=p.round_id,
                at=p.submitted_at,
                content=p.content[:120],
            )
        )

    for c in (
        db.query(Critique)
        .filter(Critique.agent_id == agent_id)
        .order_by(Critique.submitted_at.desc())
        .limit(10)
        .all()
    ):
        items.append(
            ActivityItem(
                type="critique",
                round_id=c.round_id,
                at=c.submitted_at,
                proposal_id=c.proposal_id,
                content=c.content[:120],
            )
        )

    for v in (
        db.query(Vote)
        .filter(Vote.agent_id == agent_id)
        .order_by(Vote.submitted_at.desc())
        .limit(10)
        .all()
    ):
        items.append(
            ActivityItem(
                type="vote",
                round_id=v.round_id,
                at=v.submitted_at,
                proposal_id=v.proposal_id,
            )
        )

    for e in (
        db.query(ScoreEvent)
        .filter(ScoreEvent.agent_id == agent_id)
        .order_by(ScoreEvent.created_at.desc())
        .limit(10)
        .all()
    ):
        items.append(
            ActivityItem(
                type="score",
                round_id=e.round_id,
                at=e.created_at,
                reason=e.reason,
                points=e.points,
            )
        )

    items.sort(key=lambda x: x.at, reverse=True)
    return AgentActivityOut(agent_id=agent_id, name=agent.name, recent_events=items[:20])


@router.get("/{agent_id}", response_model=AgentPublic)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
