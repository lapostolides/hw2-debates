from tests.conftest import h


def test_submit_critique(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")

    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": bob_prop["id"], "content": "Good point but..."},
                    headers=h(agent_a))
    assert r.status_code == 201
    data = r.json()
    assert data["agent_name"] == "Alice"
    assert data["proposal_id"] == bob_prop["id"]
    assert data["content"] == "Good point but..."


def test_submit_critique_requires_auth(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": bob_prop["id"], "content": "Test"})
    assert r.status_code == 422


def test_submit_critique_wrong_phase(client, agent_a, agent_b, round_proposal):
    """Cannot critique during proposal phase."""
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "Bob"}, headers=h(agent_b))
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": bob_prop["id"], "content": "Too early"},
                    headers=h(agent_a))
    assert r.status_code == 409


def test_self_critique_rejected(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": alice_prop["id"], "content": "Self-critique"},
                    headers=h(agent_a))
    assert r.status_code == 422
    assert "own" in r.json()["detail"].lower()


def test_duplicate_critique_rejected(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "First"},
                headers=h(agent_a))
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": bob_prop["id"], "content": "Second"},
                    headers=h(agent_a))
    assert r.status_code == 409


def test_critique_empty_content(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": bob_prop["id"], "content": ""},
                    headers=h(agent_a))
    assert r.status_code == 422


def test_critique_proposal_not_in_round(client, agent_a, round_critique):
    rid = round_critique["id"]
    r = client.post(f"/rounds/{rid}/critiques",
                    json={"proposal_id": 9999, "content": "Critique"},
                    headers=h(agent_a))
    assert r.status_code == 404


def test_list_critiques(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    state = client.get(f"/rounds/{rid}").json()
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "A on B"},
                headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "B on A"},
                headers=h(agent_b))

    r = client.get(f"/rounds/{rid}/critiques")
    assert r.status_code == 200
    assert len(r.json()) == 2
