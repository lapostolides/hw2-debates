from tests.conftest import h


# ── proposal → critique ────────────────────────────────────────────────────

def test_advance_proposal_to_critique(client, agent_a, agent_b, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 200
    data = r.json()
    assert data["previous_phase"] == "proposal"
    assert data["new_phase"] == "critique"


def test_advance_fails_with_zero_proposals(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 409
    assert "2" in r.json()["detail"]


def test_advance_fails_with_one_proposal(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Only one"}, headers=h(agent_a))
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 409


# ── critique → voting ──────────────────────────────────────────────────────

def test_advance_critique_to_voting(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")

    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "A on B"},
                headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "B on A"},
                headers=h(agent_b))

    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 200
    assert r.json()["new_phase"] == "voting"


def test_advance_critique_blocked_when_agent_hasnt_critiqued(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")

    # Only Alice critiques; Bob has not
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "A on B"},
                headers=h(agent_a))

    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 409
    assert "Bob" in r.json()["detail"]


# ── voting → closed ────────────────────────────────────────────────────────

def test_advance_voting_to_closed(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]},
                headers=h(agent_b))
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 200
    data = r.json()
    assert data["new_phase"] == "closed"
    assert "Alice" in data["message"]


def test_advance_voting_blocked_with_no_votes(client, agent_a, round_voting):
    rid = round_voting["id"]
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 409
    assert "vote" in r.json()["detail"].lower()


# ── closed ─────────────────────────────────────────────────────────────────

def test_advance_closed_round_rejected(client, agent_a, round_closed):
    rid = round_closed["id"]
    r = client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    assert r.status_code == 409
    assert "closed" in r.json()["detail"].lower()


# ── auth ───────────────────────────────────────────────────────────────────

def test_advance_requires_auth(client, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/advance")
    assert r.status_code == 422


def test_advance_round_not_found(client, agent_a):
    r = client.post("/rounds/9999/advance", headers=h(agent_a))
    assert r.status_code == 404
