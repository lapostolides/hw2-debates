from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ── Agents ────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 64:
            raise ValueError("name must be 64 characters or fewer")
        return v


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    api_key: str
    total_score: int
    created_at: datetime


class AgentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    total_score: int
    created_at: datetime


# ── Rounds ────────────────────────────────────────────────────────────────────

class RoundCreate(BaseModel):
    prompt: str

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("prompt must not be empty")
        if len(v) > 2000:
            raise ValueError("prompt must be 2000 characters or fewer")
        return v


class RoundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prompt: str
    phase: str
    created_at: datetime
    closed_at: Optional[datetime]
    created_by: int


# ── Proposals ─────────────────────────────────────────────────────────────────

class ProposalCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        if len(v) > 4000:
            raise ValueError("content must be 4000 characters or fewer")
        return v


class ProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    round_id: int
    agent_id: int
    agent_name: str
    content: str
    submitted_at: datetime
    vote_count: int

    @classmethod
    def from_orm_with_name(cls, proposal) -> "ProposalOut":
        return cls(
            id=proposal.id,
            round_id=proposal.round_id,
            agent_id=proposal.agent_id,
            agent_name=proposal.agent.name,
            content=proposal.content,
            submitted_at=proposal.submitted_at,
            vote_count=proposal.vote_count,
        )


# ── Critiques ─────────────────────────────────────────────────────────────────

class CritiqueCreate(BaseModel):
    proposal_id: int
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        if len(v) > 2000:
            raise ValueError("content must be 2000 characters or fewer")
        return v


class CritiqueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    round_id: int
    agent_id: int
    agent_name: str
    proposal_id: int
    content: str
    submitted_at: datetime

    @classmethod
    def from_orm_with_name(cls, critique) -> "CritiqueOut":
        return cls(
            id=critique.id,
            round_id=critique.round_id,
            agent_id=critique.agent_id,
            agent_name=critique.agent.name,
            proposal_id=critique.proposal_id,
            content=critique.content,
            submitted_at=critique.submitted_at,
        )


# ── Votes ─────────────────────────────────────────────────────────────────────

class VoteCreate(BaseModel):
    proposal_id: int


class VoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    round_id: int
    agent_id: int
    proposal_id: int
    submitted_at: datetime


# ── Round state (full view) ───────────────────────────────────────────────────

class RoundState(BaseModel):
    round: RoundOut
    proposals: List[ProposalOut]
    critiques: List[CritiqueOut]
    votes: List[VoteOut]
    participant_count: int


# ── Phase transition ──────────────────────────────────────────────────────────

class PhaseTransitionOut(BaseModel):
    round_id: int
    previous_phase: str
    new_phase: str
    message: str


# ── Leaderboard ───────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: int
    name: str
    total_score: int
    rounds_participated: int


class LeaderboardOut(BaseModel):
    entries: List[LeaderboardEntry]
    as_of: datetime


# ── Score events ──────────────────────────────────────────────────────────────

class ScoreEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    round_id: int
    reason: str
    points: int
    created_at: datetime
