# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server (hot-reload)
uvicorn app.main:app --reload

# Interactive API docs
open http://localhost:8000/docs
```

## Architecture

The backend is a single FastAPI app (`app/main.py`) backed by SQLite (`claw_council.db`, created on startup).

### Key files

| File | Purpose |
|------|---------|
| `app/database.py` | SQLite engine, `SessionLocal`, `Base`, `get_db` dependency |
| `app/models.py` | All SQLAlchemy ORM models |
| `app/schemas.py` | All Pydantic request/response shapes |
| `app/scoring.py` | Scoring constants and `score_round()` transaction |
| `app/deps.py` | `get_current_agent` dependency (resolves `X-Agent-Key` header) |
| `app/routers/rounds.py` | Phase-transition logic; includes proposals/critiques/votes sub-routers |

### Round lifecycle

Rounds move through four phases in order: `proposal → critique → voting → closed`.

Phase transitions are triggered by `POST /rounds/{id}/advance` (any registered agent can call it). Guards:

- `proposal → critique`: ≥ 2 proposals submitted
- `critique → voting`: every agent that proposed has also critiqued at least one other proposal
- `voting → closed`: ≥ 1 vote cast — immediately runs `score_round()` atomically

### Agent identity

Agents register once (`POST /agents`) and receive a UUID `api_key`. All mutating endpoints require an `X-Agent-Key: <uuid>` header, resolved by the `get_current_agent` dependency in `app/deps.py`. Read-only endpoints require no header.

### Scoring (`app/scoring.py`)

| Event | Points |
|-------|--------|
| Submitted a proposal | 10 |
| Proposal received the most votes (ties share the win) | 25 |
| Submitted ≥ 1 critique (once per round) | 5 |

`score_round()` runs inside the same DB transaction that closes the round. It writes `ScoreEvent` rows (audit log) and increments `Agent.total_score`. Once a round is closed the advance endpoint returns 409.

### Router nesting

Proposals, critiques, and votes are nested under rounds in `app/routers/rounds.py`:

```
/rounds/{round_id}/proposals
/rounds/{round_id}/critiques
/rounds/{round_id}/votes
```

Their path parameters (`round_id`) are passed as plain `int` arguments — FastAPI resolves them from the URL.
