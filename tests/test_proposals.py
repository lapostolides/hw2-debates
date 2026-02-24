from tests.conftest import h


def test_submit_proposal(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/proposals",
                    json={"content": "My proposal"},
                    headers=h(agent_a))
    assert r.status_code == 201
    data = r.json()
    assert data["content"] == "My proposal"
    assert data["agent_name"] == "Alice"
    assert data["vote_count"] == 0


def test_submit_proposal_requires_auth(client, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/proposals", json={"content": "Test"})
    assert r.status_code == 422


def test_submit_proposal_wrong_phase(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    r = client.post(f"/rounds/{rid}/proposals",
                    json={"content": "Late proposal"},
                    headers=h(agent_a))
    assert r.status_code == 409
    assert "proposal" in r.json()["detail"].lower()


def test_submit_proposal_duplicate(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "First"}, headers=h(agent_a))
    r = client.post(f"/rounds/{rid}/proposals", json={"content": "Second"}, headers=h(agent_a))
    assert r.status_code == 409


def test_submit_proposal_empty_content(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/proposals", json={"content": ""}, headers=h(agent_a))
    assert r.status_code == 422


def test_submit_proposal_content_too_long(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(f"/rounds/{rid}/proposals",
                    json={"content": "x" * 4001},
                    headers=h(agent_a))
    assert r.status_code == 422


def test_submit_proposal_round_not_found(client, agent_a):
    r = client.post("/rounds/9999/proposals",
                    json={"content": "Test"},
                    headers=h(agent_a))
    assert r.status_code == 404


def test_list_proposals(client, agent_a, agent_b, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "Bob"}, headers=h(agent_b))
    r = client.get(f"/rounds/{rid}/proposals")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    names = {p["agent_name"] for p in data}
    assert names == {"Alice", "Bob"}


def test_get_single_proposal(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    created = client.post(f"/rounds/{rid}/proposals",
                          json={"content": "My prop"},
                          headers=h(agent_a)).json()
    r = client.get(f"/rounds/{rid}/proposals/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_get_proposal_not_found(client, round_proposal):
    rid = round_proposal["id"]
    r = client.get(f"/rounds/{rid}/proposals/9999")
    assert r.status_code == 404
