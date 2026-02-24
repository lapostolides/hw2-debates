import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    # StaticPool ensures all sessions share the same in-memory connection,
    # so tables created at setup are visible to every request in the test.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# ── Agent fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def agent_a(client):
    return client.post("/agents", json={"name": "Alice"}).json()


@pytest.fixture()
def agent_b(client):
    return client.post("/agents", json={"name": "Bob"}).json()


@pytest.fixture()
def agent_c(client):
    return client.post("/agents", json={"name": "Carol"}).json()


# ── Header helper ──────────────────────────────────────────────────────────

def h(agent):
    """Return X-Agent-Name header dict for an agent."""
    return {"X-Agent-Name": agent["name"]}


# ── Round fixtures ─────────────────────────────────────────────────────────

@pytest.fixture()
def round_proposal(client, agent_a):
    """A round in 'proposal' phase."""
    r = client.post("/rounds", json={"prompt": "Test prompt"}, headers=h(agent_a))
    assert r.status_code == 201
    return r.json()


@pytest.fixture()
def round_critique(client, agent_a, agent_b, round_proposal):
    """A round in 'critique' phase: both agents have proposed."""
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice proposal"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "Bob proposal"}, headers=h(agent_b))
    adv = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert adv.status_code == 200
    return client.get(f"/rounds/{rid}").json()["round"]


@pytest.fixture()
def round_voting(client, agent_a, agent_b, round_critique):
    """A round in 'voting' phase: both agents have proposed and critiqued."""
    rid = round_critique["id"]
    # Get proposals to find the right IDs
    state = client.get(f"/rounds/{rid}").json()
    proposals = state["proposals"]
    alice_prop = next(p for p in proposals if p["agent_name"] == "Alice")
    bob_prop = next(p for p in proposals if p["agent_name"] == "Bob")

    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "Alice critiques Bob"},
                headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "Bob critiques Alice"},
                headers=h(agent_b))
    adv = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert adv.status_code == 200
    return client.get(f"/rounds/{rid}").json()["round"]


@pytest.fixture()
def round_closed(client, agent_a, agent_b, round_voting):
    """A round in 'closed' phase: agent_b voted for agent_a's proposal."""
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]},
                headers=h(agent_b))
    adv = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert adv.status_code == 200
    return client.get(f"/rounds/{rid}").json()["round"]
