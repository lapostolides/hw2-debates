from tests.conftest import h


def test_create_round(client, agent_a):
    r = client.post("/rounds", json={"prompt": "What is the best approach?"}, headers=h(agent_a))
    assert r.status_code == 201
    data = r.json()
    assert data["prompt"] == "What is the best approach?"
    assert data["phase"] == "proposal"
    assert data["closed_at"] is None
    assert data["created_by"] == agent_a["id"]


def test_create_round_requires_auth(client):
    r = client.post("/rounds", json={"prompt": "Test"})
    assert r.status_code == 422  # missing header


def test_create_round_unknown_name_auto_creates(client):
    """Any agent name is accepted and auto-registered on first use."""
    r = client.post("/rounds", json={"prompt": "Test"}, headers={"X-Agent-Name": "newcomer"})
    assert r.status_code == 201


def test_create_round_empty_prompt(client, agent_a):
    r = client.post("/rounds", json={"prompt": ""}, headers=h(agent_a))
    assert r.status_code == 422


def test_create_round_prompt_too_long(client, agent_a):
    r = client.post("/rounds", json={"prompt": "x" * 2001}, headers=h(agent_a))
    assert r.status_code == 422


def test_list_rounds_newest_first(client, agent_a):
    client.post("/rounds", json={"prompt": "First"}, headers=h(agent_a))
    client.post("/rounds", json={"prompt": "Second"}, headers=h(agent_a))
    r = client.get("/rounds")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["prompt"] == "Second"  # newest first
    assert data[1]["prompt"] == "First"


def test_list_rounds_empty(client):
    r = client.get("/rounds")
    assert r.status_code == 200
    assert r.json() == []


def test_get_round_state(client, round_proposal):
    rid = round_proposal["id"]
    r = client.get(f"/rounds/{rid}")
    assert r.status_code == 200
    data = r.json()
    assert data["round"]["id"] == rid
    assert data["proposals"] == []
    assert data["critiques"] == []
    assert data["votes"] == []
    assert data["participant_count"] == 0


def test_get_round_not_found(client):
    r = client.get("/rounds/9999")
    assert r.status_code == 404
