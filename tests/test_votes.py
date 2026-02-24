from tests.conftest import h


def test_cast_vote(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    r = client.post(f"/rounds/{rid}/votes",
                    json={"proposal_id": alice_prop["id"]},
                    headers=h(agent_b))
    assert r.status_code == 201
    data = r.json()
    assert data["proposal_id"] == alice_prop["id"]
    assert data["agent_id"] == agent_b["id"]


def test_vote_requires_auth(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    r = client.post(f"/rounds/{rid}/votes", json={"proposal_id": alice_prop["id"]})
    assert r.status_code == 422


def test_vote_wrong_phase(client, agent_a, agent_b, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice"}, headers=h(agent_a))
    r = client.post(f"/rounds/{rid}/votes",
                    json={"proposal_id": 1},
                    headers=h(agent_b))
    assert r.status_code == 409


def test_self_vote_rejected(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    r = client.post(f"/rounds/{rid}/votes",
                    json={"proposal_id": alice_prop["id"]},
                    headers=h(agent_a))
    assert r.status_code == 422
    assert "own" in r.json()["detail"].lower()


def test_duplicate_vote_rejected(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]},
                headers=h(agent_b))
    r = client.post(f"/rounds/{rid}/votes",
                    json={"proposal_id": alice_prop["id"]},
                    headers=h(agent_b))
    assert r.status_code == 409


def test_vote_proposal_not_in_round(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    r = client.post(f"/rounds/{rid}/votes",
                    json={"proposal_id": 9999},
                    headers=h(agent_b))
    assert r.status_code == 404


def test_list_votes(client, agent_a, agent_b, round_voting):
    rid = round_voting["id"]
    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")

    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]},
                headers=h(agent_b))

    r = client.get(f"/rounds/{rid}/votes")
    assert r.status_code == 200
    assert len(r.json()) == 1
