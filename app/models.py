from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    api_key = Column(String(36), unique=True, nullable=False, index=True)
    total_score = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    proposals = relationship("Proposal", back_populates="agent")
    critiques = relationship("Critique", back_populates="agent")
    votes = relationship("Vote", back_populates="agent")
    score_events = relationship("ScoreEvent", back_populates="agent")


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    phase = Column(String(16), nullable=False, default="proposal")
    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("agents.id"), nullable=False)

    proposals = relationship("Proposal", back_populates="round")
    score_events = relationship("ScoreEvent", back_populates="round")


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    content = Column(Text, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    vote_count = Column(Integer, default=0, nullable=False)

    round = relationship("Round", back_populates="proposals")
    agent = relationship("Agent", back_populates="proposals")
    critiques = relationship("Critique", back_populates="proposal")
    votes = relationship("Vote", back_populates="proposal")

    __table_args__ = (
        UniqueConstraint("round_id", "agent_id", name="uq_one_proposal_per_round"),
    )


class Critique(Base):
    __tablename__ = "critiques"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False)
    content = Column(Text, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round")
    agent = relationship("Agent", back_populates="critiques")
    proposal = relationship("Proposal", back_populates="critiques")

    __table_args__ = (
        UniqueConstraint(
            "round_id", "agent_id", "proposal_id", name="uq_one_critique_per_proposal"
        ),
    )


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    proposal_id = Column(Integer, ForeignKey("proposals.id"), nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)

    round = relationship("Round")
    agent = relationship("Agent", back_populates="votes")
    proposal = relationship("Proposal", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("round_id", "agent_id", name="uq_one_vote_per_round"),
    )


class ScoreEvent(Base):
    __tablename__ = "score_events"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    round_id = Column(Integer, ForeignKey("rounds.id"), nullable=False)
    reason = Column(String(32), nullable=False)  # participation | win | critique_bonus
    points = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="score_events")
    round = relationship("Round", back_populates="score_events")
