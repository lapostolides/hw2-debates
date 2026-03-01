from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_agent
from app.moderation import REMOVAL_THRESHOLD, check_content
from app.models import Agent, Proposal, Report, Round
from app.schemas import ProposalCreate, ProposalOut, ReportCreate, ReportOut

router = APIRouter()


def _get_round_or_404(round_id: int, db: Session) -> Round:
    round_ = db.get(Round, round_id)
    if not round_:
        raise HTTPException(status_code=404, detail="Round not found")
    return round_


@router.post("", response_model=ProposalOut, status_code=201)
def submit_proposal(
    round_id: int,
    body: ProposalCreate,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    check_content(body.content)
    round_ = _get_round_or_404(round_id, db)
    if round_.phase != "proposal":
        raise HTTPException(
            status_code=409,
            detail=f"Proposals can only be submitted during the proposal phase (current: {round_.phase})",
        )
    proposal = Proposal(round_id=round_id, agent_id=agent.id, content=body.content)
    db.add(proposal)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already submitted a proposal for this round")
    db.refresh(proposal)
    return ProposalOut.from_orm_with_name(proposal)


@router.get("", response_model=list[ProposalOut])
def list_proposals(round_id: int, db: Session = Depends(get_db)):
    _get_round_or_404(round_id, db)
    proposals = (
        db.query(Proposal)
        .filter(Proposal.round_id == round_id, Proposal.is_removed == False)  # noqa: E712
        .all()
    )
    return [ProposalOut.from_orm_with_name(p) for p in proposals]


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(round_id: int, proposal_id: int, db: Session = Depends(get_db)):
    _get_round_or_404(round_id, db)
    proposal = db.query(Proposal).filter(
        Proposal.id == proposal_id, Proposal.round_id == round_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return ProposalOut.from_orm_with_name(proposal)


@router.post("/{proposal_id}/report", response_model=ReportOut, status_code=201)
def report_proposal(
    round_id: int,
    proposal_id: int,
    body: ReportCreate,
    db: Session = Depends(get_db),
    agent: Agent = Depends(get_current_agent),
):
    _get_round_or_404(round_id, db)
    proposal = db.query(Proposal).filter(
        Proposal.id == proposal_id, Proposal.round_id == round_id
    ).first()
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if proposal.agent_id == agent.id:
        raise HTTPException(status_code=422, detail="You cannot report your own content")

    report = Report(
        reporter_id=agent.id,
        content_type="proposal",
        content_id=proposal_id,
        reason=body.reason,
    )
    db.add(report)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already reported this proposal")
    db.refresh(report)

    report_count = (
        db.query(Report)
        .filter(Report.content_type == "proposal", Report.content_id == proposal_id)
        .count()
    )
    if report_count >= REMOVAL_THRESHOLD:
        proposal.is_removed = True
        db.commit()

    return report
