from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_agent
from app.models import Agent, Critique, Proposal, Round, Vote
from app.schemas import (
    PhaseTransitionOut,
    ProposalOut,
    CritiqueOut,
    RoundCreate,
    RoundOut,
    RoundState,
    VoteOut,
)
from app.scoring import score_round
from app.routers.proposals import router as proposals_router
from app.routers.critiques import router as critiques_router
from app.routers.votes import router as votes_router

router = APIRouter()

# Nest sub-resources under /rounds/{round_id}/...
router.include_router(proposals_router, prefix="/{round_id}/proposals", tags=["Proposals"])
router.include_router(critiques_router, prefix="/{round_id}/critiques", tags=["Critiques"])
router.include_router(votes_router, prefix="/{round_id}/votes", tags=["Votes"])


@router.post("", response_model=RoundOut, status_code=201)
def create_round(
    body: RoundCreate,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    round_ = Round(prompt=body.prompt, created_by=agent.id)
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


@router.get("", response_model=list[RoundOut])
def list_rounds(db: Session = Depends(get_db)):
    return db.query(Round).order_by(Round.created_at.desc()).all()


@router.get("/{round_id}", response_model=RoundState)
def get_round(round_id: int, db: Session = Depends(get_db)):
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")

    proposals = db.query(Proposal).filter(Proposal.round_id == round_id).all()
    critiques = db.query(Critique).filter(Critique.round_id == round_id).all()
    votes = db.query(Vote).filter(Vote.round_id == round_id).all()

    return RoundState(
        round=RoundOut.model_validate(round_),
        proposals=[ProposalOut.from_orm_with_name(p) for p in proposals],
        critiques=[CritiqueOut.from_orm_with_name(c) for c in critiques],
        votes=[VoteOut.model_validate(v) for v in votes],
        participant_count=len({p.agent_id for p in proposals}),
    )


@router.post("/{round_id}/advance", response_model=PhaseTransitionOut)
def advance_phase(
    round_id: int,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")

    previous_phase = round_.phase

    if previous_phase == "closed":
        raise HTTPException(status_code=409, detail="Round is already closed")

    proposals = db.query(Proposal).filter(Proposal.round_id == round_id).all()
    critiques = db.query(Critique).filter(Critique.round_id == round_id).all()
    votes = db.query(Vote).filter(Vote.round_id == round_id).all()

    if previous_phase == "proposal":
        if len(proposals) < 2:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot advance: need at least 2 proposals (have {len(proposals)})",
            )
        round_.phase = "critique"
        message = f"Advanced to critique phase with {len(proposals)} proposals."

    elif previous_phase == "critique":
        proposing_agents = {p.agent_id for p in proposals}
        critiquing_agents = {c.agent_id for c in critiques}
        # Each critiquing agent must have critiqued a proposal that isn't theirs
        # (enforced at submission time, so we just check coverage)
        missing = proposing_agents - critiquing_agents
        if missing:
            missing_names = []
            for aid in missing:
                a = db.get(Agent, aid)
                missing_names.append(a.name if a else str(aid))
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot advance: the following agents have not submitted a critique yet: "
                    f"{', '.join(missing_names)}"
                ),
            )
        round_.phase = "voting"
        message = "Advanced to voting phase."

    elif previous_phase == "voting":
        if not votes:
            raise HTTPException(
                status_code=409, detail="Cannot advance: no votes have been cast yet"
            )
        events = score_round(db, round_id)
        round_.phase = "closed"
        round_.closed_at = datetime.utcnow()

        win_events = [e for e in events if e.reason == "win"]
        if win_events:
            # Flush so IDs are available, then build winner summary
            db.flush()
            winner_agent_ids = {e.agent_id for e in win_events}
            winner_names = []
            for aid in winner_agent_ids:
                a = db.get(Agent, aid)
                winner_names.append(a.name if a else str(aid))
            message = f"Round closed. Winner(s): {', '.join(winner_names)}. Scores awarded."
        else:
            message = "Round closed. No votes were cast; participation points awarded."
    else:
        raise HTTPException(status_code=500, detail=f"Unknown phase: {previous_phase}")

    db.commit()

    return PhaseTransitionOut(
        round_id=round_id,
        previous_phase=previous_phase,
        new_phase=round_.phase,
        message=message,
    )
