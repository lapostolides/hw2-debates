import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentOut, AgentPublic

router = APIRouter()


@router.post("", response_model=AgentOut, status_code=201)
def register_agent(body: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(name=body.name, api_key=str(uuid.uuid4()))
    db.add(agent)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Agent name '{body.name}' is already taken")
    db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentPublic)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
