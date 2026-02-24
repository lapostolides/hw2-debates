from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_agent
from app.models import Agent, Critique, Proposal, Round
from app.schemas import CritiqueCreate, CritiqueOut

router = APIRouter()


def _get_round_or_404(round_id: int, db: Session) -> Round:
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return round_


@router.post("", response_model=CritiqueOut, status_code=201)
def submit_critique(
    round_id: int,
    body: CritiqueCreate,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    round_ = _get_round_or_404(round_id, db)
    if round_.phase != "critique":
        raise HTTPException(
            status_code=409,
            detail=f"Critiques can only be submitted during the critique phase (current: {round_.phase})",
        )

    proposal = db.query(Proposal).filter(
        Proposal.id == body.proposal_id, Proposal.round_id == round_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found in this round")

    if proposal.agent_id == agent.id:
        raise HTTPException(status_code=422, detail="You cannot critique your own proposal")

    critique = Critique(
        round_id=round_id,
        agent_id=agent.id,
        proposal_id=body.proposal_id,
        content=body.content,
    )
    db.add(critique)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already critiqued this proposal")
    db.refresh(critique)
    return CritiqueOut.from_orm_with_name(critique)


@router.get("", response_model=list[CritiqueOut])
def list_critiques(round_id: int, db: Session = Depends(get_db)):
    _get_round_or_404(round_id, db)
    critiques = db.query(Critique).filter(Critique.round_id == round_id).all()
    return [CritiqueOut.from_orm_with_name(c) for c in critiques]
