"""Tests for per-agent rate limiting on mutating endpoints."""

import pytest
from tests.conftest import h


# ── create_round: 10 per 60s ────────────────────────────────────────────────

def test_create_round_within_limit(client, agent_a):
    for i in range(10):
        r = client.post("/rounds", json={"prompt": f"prompt {i}"}, headers=h(agent_a))
        assert r.status_code == 201


def test_create_round_exceeds_limit(client, agent_a):
    for i in range(10):
        client.post("/rounds", json={"prompt": f"prompt {i}"}, headers=h(agent_a))
    r = client.post("/rounds", json={"prompt": "one too many"}, headers=h(agent_a))
    assert r.status_code == 429


def test_create_round_limit_is_per_agent(client, agent_a, agent_b):
    """agent_b should not be affected by agent_a exhausting their limit."""
    for i in range(10):
        client.post("/rounds", json={"prompt": f"prompt {i}"}, headers=h(agent_a))
    r = client.post("/rounds", json={"prompt": "bob's round"}, headers=h(agent_b))
    assert r.status_code == 201


# ── advance: 10 per 60s ─────────────────────────────────────────────────────

def test_advance_exceeds_limit(client, agent_a, agent_b):
    """Spamming advance beyond 10 times returns 429."""
    # Create 10 rounds and advance each once so we burn through 10 advance calls
    for i in range(10):
        r = client.post("/rounds", json={"prompt": f"prompt {i}"}, headers=h(agent_a))
        rid = r.json()["id"]
        client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
        client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
        client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    # The 11th advance attempt should be rate-limited
    last_rid = client.post("/rounds", json={"prompt": "last"}, headers=h(agent_b)).json()["id"]
    client.post(f"/rounds/{last_rid}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{last_rid}/proposals", json={"content": "B"}, headers=h(agent_b))
    r = client.post(f"/rounds/{last_rid}/advance", headers=h(agent_a))
    assert r.status_code == 429


def test_advance_limit_is_per_agent(client, agent_a, agent_b):
    """agent_b's advance calls are not counted against agent_a."""
    # Burn agent_a's 10 advance calls
    for i in range(10):
        r = client.post("/rounds", json={"prompt": f"p{i}"}, headers=h(agent_a))
        rid = r.json()["id"]
        client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
        client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
        client.post(f"/rounds/{rid}/advance", headers=h(agent_a))

    # agent_b should still be able to advance
    r2 = client.post("/rounds", json={"prompt": "bob's"}, headers=h(agent_b)).json()
    rid2 = r2["id"]
    client.post(f"/rounds/{rid2}/proposals", json={"content": "A"}, headers=h(agent_a))
    client.post(f"/rounds/{rid2}/proposals", json={"content": "B"}, headers=h(agent_b))
    r = client.post(f"/rounds/{rid2}/advance", headers=h(agent_b))
    assert r.status_code == 200


# ── critiques: 30 per 60s ───────────────────────────────────────────────────

def test_critique_exceeds_limit(client, agent_a, agent_b, agent_c):
    """An agent posting more than 30 critiques per minute gets 429."""
    # We need 31 rounds in critique phase.  The round-creation limit is 10/min
    # per agent, so we spread creation across 4 creator agents (each creates ≤10).
    creators = [
        client.post("/agents", json={"name": f"creator{i}"}).json()
        for i in range(4)
    ]

    round_ids = []
    for i in range(31):
        creator = creators[i % len(creators)]
        r = client.post("/rounds", json={"prompt": f"p{i}"}, headers=h(creator))
        assert r.status_code == 201, r.json()
        rid = r.json()["id"]
        client.post(f"/rounds/{rid}/proposals", json={"content": "A"}, headers=h(agent_a))
        client.post(f"/rounds/{rid}/proposals", json={"content": "B"}, headers=h(agent_b))
        client.post(f"/rounds/{rid}/advance", headers=h(creator))  # → critique phase
        round_ids.append(rid)

    # agent_c now critiques one proposal per round; hits the 429 on the 31st
    for i, rid in enumerate(round_ids):
        proposal_id = client.get(f"/rounds/{rid}").json()["proposals"][0]["id"]
        r_crit = client.post(
            f"/rounds/{rid}/critiques",
            json={"proposal_id": proposal_id, "content": "critique"},
            headers=h(agent_c),
        )
        if i < 30:
            assert r_crit.status_code == 201, f"Expected 201 on iteration {i}, got {r_crit.json()}"
        else:
            assert r_crit.status_code == 429
