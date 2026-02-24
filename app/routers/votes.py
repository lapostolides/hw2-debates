from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_agent
from app.models import Agent, Proposal, Round, Vote
from app.schemas import VoteCreate, VoteOut

router = APIRouter()


def _get_round_or_404(round_id: int, db: Session) -> Round:
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return round_


@router.post("", response_model=VoteOut, status_code=201)
def cast_vote(
    round_id: int,
    body: VoteCreate,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    round_ = _get_round_or_404(round_id, db)
    if round_.phase != "voting":
        raise HTTPException(
            status_code=409,
            detail=f"Votes can only be cast during the voting phase (current: {round_.phase})",
        )

    proposal = db.query(Proposal).filter(
        Proposal.id == body.proposal_id, Proposal.round_id == round_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found in this round")

    if proposal.agent_id == agent.id:
        raise HTTPException(status_code=422, detail="You cannot vote for your own proposal")

    vote = Vote(round_id=round_id, agent_id=agent.id, proposal_id=body.proposal_id)
    db.add(vote)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already voted in this round")
    db.refresh(vote)
    return vote


@router.get("", response_model=list[VoteOut])
def list_votes(round_id: int, db: Session = Depends(get_db)):
    _get_round_or_404(round_id, db)
    return db.query(Vote).filter(Vote.round_id == round_id).all()
