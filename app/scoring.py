from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Agent, Proposal, ScoreEvent, Vote

POINTS_PARTICIPATION = 10
POINTS_WIN = 25
POINTS_CRITIQUE = 5


def score_round(db: Session, round_id: int) -> list[ScoreEvent]:
    """
    Tally votes, determine winner(s), award points, and emit ScoreEvent rows.
    Must be called inside the same transaction that closes the round.
    Returns the list of ScoreEvent objects created.
    """
    proposals = db.query(Proposal).filter(Proposal.round_id == round_id).all()
    votes = db.query(Vote).filter(Vote.round_id == round_id).all()

    # Count votes per proposal
    vote_counts: dict[int, int] = {p.id: 0 for p in proposals}
    for vote in votes:
        vote_counts[vote.proposal_id] = vote_counts.get(vote.proposal_id, 0) + 1

    # Update denormalized vote_count on each proposal
    for proposal in proposals:
        proposal.vote_count = vote_counts.get(proposal.id, 0)

    max_votes = max(vote_counts.values(), default=0)
    winner_proposal_ids = {
        pid for pid, count in vote_counts.items() if count == max_votes and max_votes > 0
    }

    # Sets of agent_ids by action
    proposing_agents = {p.agent_id for p in proposals}
    from app.models import Critique
    critiques = db.query(Critique).filter(Critique.round_id == round_id).all()
    critiquing_agents = {c.agent_id for c in critiques}
    winning_agents = {
        p.agent_id for p in proposals if p.id in winner_proposal_ids
    }

    events: list[ScoreEvent] = []

    def _award(agent_id: int, reason: str, points: int) -> None:
        event = ScoreEvent(
            agent_id=agent_id,
            round_id=round_id,
            reason=reason,
            points=points,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        events.append(event)
        agent = db.get(Agent, agent_id)
        if agent:
            agent.total_score += points

    for agent_id in proposing_agents:
        _award(agent_id, "participation", POINTS_PARTICIPATION)

    for agent_id in winning_agents:
        _award(agent_id, "win", POINTS_WIN)

    for agent_id in critiquing_agents & proposing_agents:
        _award(agent_id, "critique_bonus", POINTS_CRITIQUE)

    return events
