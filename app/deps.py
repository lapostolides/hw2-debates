from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent


def get_current_agent(
    x_agent_key: str = Header(..., description="Agent API key from registration"),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.query(Agent).filter(Agent.api_key == x_agent_key).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Unknown agent key")
    return agent
