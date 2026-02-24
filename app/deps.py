import uuid

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent


def get_current_agent(
    x_agent_name: str = Header(..., description="Agent name (auto-registered on first use)"),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.query(Agent).filter(Agent.name == x_agent_name).first()
    if not agent:
        agent = Agent(name=x_agent_name, api_key=str(uuid.uuid4()))
        db.add(agent)
        db.commit()
        db.refresh(agent)
    return agent
