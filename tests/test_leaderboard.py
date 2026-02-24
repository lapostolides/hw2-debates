from tests.conftest import h
from app.scoring import POINTS_PARTICIPATION, POINTS_WIN, POINTS_CRITIQUE


def test_leaderboard_empty(client):
    r = client.get("/leaderboard")
    assert r.status_code == 200
    data = r.json()
    assert data["entries"] == []
    assert "as_of" in data


def test_leaderboard_after_registration_no_rounds(client, agent_a, agent_b):
    r = client.get("/leaderboard")
    entries = r.json()["entries"]
    assert len(entries) == 2
    for e in entries:
        assert e["total_score"] == 0
        assert e["rounds_participated"] == 0


def test_leaderboard_ranking_after_closed_round(client, agent_a, agent_b):
    # Drive full round: Alice wins
    r = client.post("/rounds", json={"prompt": "LB test"}, headers=h(agent_a))
    rid = r.json()["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "c"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "c"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    r = client.get("/leaderboard")
    entries = r.json()["entries"]
    assert entries[0]["name"] == "Alice"  # winner ranked first
    assert entries[0]["rank"] == 1
    assert entries[0]["total_score"] == POINTS_PARTICIPATION + POINTS_WIN + POINTS_CRITIQUE
    assert entries[1]["rank"] == 2
    assert entries[1]["total_score"] == POINTS_PARTICIPATION + POINTS_CRITIQUE


def test_rounds_participated_counts_proposals_only(client, agent_a, agent_b):
    """rounds_participated reflects rounds where agent submitted a proposal."""
    r = client.post("/rounds", json={"prompt": "Participation test"}, headers=h(agent_a))
    rid = r.json()["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "c"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "c"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    entries = client.get("/leaderboard").json()["entries"]
    for e in entries:
        assert e["rounds_participated"] == 1


def test_round_scores_endpoint(client, agent_a, agent_b):
    r = client.post("/rounds", json={"prompt": "Score events test"}, headers=h(agent_a))
    rid = r.json()["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    state = client.get(f"/rounds/{rid}").json()
    alice_prop = next(p for p in state["proposals"] if p["agent_name"] == "Alice")
    bob_prop = next(p for p in state["proposals"] if p["agent_name"] == "Bob")
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": bob_prop["id"], "content": "c"}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques",
                json={"proposal_id": alice_prop["id"], "content": "c"}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))
    client.post(f"/rounds/{rid}/votes",
                json={"proposal_id": alice_prop["id"]}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    r = client.get(f"/leaderboard/rounds/{rid}")
    assert r.status_code == 200
    events = r.json()
    reasons = {e["reason"] for e in events}
    assert "participation" in reasons
    assert "win" in reasons
    assert "critique_bonus" in reasons


def test_round_scores_not_found(client):
    r = client.get("/leaderboard/rounds/9999")
    assert r.status_code == 404
