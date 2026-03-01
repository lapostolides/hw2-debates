"""Tests for content filtering, reporting, and auto-removal."""

import pytest
from tests.conftest import h


# ── Content filter ───────────────────────────────────────────────────────────

def test_blocked_term_in_proposal_rejected(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(
        f"/rounds/{rid}/proposals",
        json={"content": "This is shit"},
        headers=h(agent_a),
    )
    assert r.status_code == 422
    assert "moderation" in r.json()["detail"].lower()


def test_blocked_term_in_critique_rejected(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    proposals = client.get(f"/rounds/{rid}").json()["proposals"]
    bob_prop = next(p for p in proposals if p["agent_name"] == "Bob")
    r = client.post(
        f"/rounds/{rid}/critiques",
        json={"proposal_id": bob_prop["id"], "content": "kill yourself"},
        headers=h(agent_a),
    )
    assert r.status_code == 422
    assert "moderation" in r.json()["detail"].lower()


def test_clean_content_is_accepted(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    r = client.post(
        f"/rounds/{rid}/proposals",
        json={"content": "A perfectly reasonable proposal."},
        headers=h(agent_a),
    )
    assert r.status_code == 201


# ── Reporting proposals ──────────────────────────────────────────────────────

def test_report_proposal(client, agent_a, agent_b, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    proposals = client.get(f"/rounds/{rid}/proposals").json()
    alice_prop = proposals[0]

    r = client.post(
        f"/rounds/{rid}/proposals/{alice_prop['id']}/report",
        json={"reason": "spam"},
        headers=h(agent_b),
    )
    assert r.status_code == 201
    assert r.json()["content_type"] == "proposal"
    assert r.json()["content_id"] == alice_prop["id"]


def test_cannot_report_own_proposal(client, agent_a, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    proposals = client.get(f"/rounds/{rid}/proposals").json()
    alice_prop = proposals[0]

    r = client.post(
        f"/rounds/{rid}/proposals/{alice_prop['id']}/report",
        json={},
        headers=h(agent_a),
    )
    assert r.status_code == 422


def test_duplicate_report_rejected(client, agent_a, agent_b, round_proposal):
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    prop_id = client.get(f"/rounds/{rid}/proposals").json()[0]["id"]

    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_b))
    r = client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_b))
    assert r.status_code == 409


# ── Reporting critiques ──────────────────────────────────────────────────────

def test_report_critique(client, agent_a, agent_b, agent_c, round_critique):
    rid = round_critique["id"]
    proposals = client.get(f"/rounds/{rid}").json()["proposals"]
    alice_prop = next(p for p in proposals if p["agent_name"] == "Alice")

    # Bob critiques Alice's proposal
    critique = client.post(
        f"/rounds/{rid}/critiques",
        json={"proposal_id": alice_prop["id"], "content": "Bob's critique"},
        headers=h(agent_b),
    ).json()

    r = client.post(
        f"/rounds/{rid}/critiques/{critique['id']}/report",
        json={"reason": "abusive"},
        headers=h(agent_c),
    )
    assert r.status_code == 201
    assert r.json()["content_type"] == "critique"


def test_cannot_report_own_critique(client, agent_a, agent_b, round_critique):
    rid = round_critique["id"]
    proposals = client.get(f"/rounds/{rid}").json()["proposals"]
    alice_prop = next(p for p in proposals if p["agent_name"] == "Alice")

    critique = client.post(
        f"/rounds/{rid}/critiques",
        json={"proposal_id": alice_prop["id"], "content": "Bob's critique"},
        headers=h(agent_b),
    ).json()

    r = client.post(
        f"/rounds/{rid}/critiques/{critique['id']}/report",
        json={},
        headers=h(agent_b),
    )
    assert r.status_code == 422


# ── Auto-removal ─────────────────────────────────────────────────────────────

def test_proposal_auto_removed_after_threshold(client, agent_a, agent_b, agent_c, round_proposal):
    """A proposal reported by ≥2 distinct agents is removed from listings."""
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    prop_id = client.get(f"/rounds/{rid}/proposals").json()[0]["id"]

    # First report — still visible
    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_b))
    assert any(p["id"] == prop_id for p in client.get(f"/rounds/{rid}/proposals").json())

    # Second report — should trigger auto-removal
    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_c))
    remaining = client.get(f"/rounds/{rid}/proposals").json()
    assert not any(p["id"] == prop_id for p in remaining)


def test_removed_proposal_is_removed_flag_set(client, agent_a, agent_b, agent_c, round_proposal):
    """Direct GET on a removed proposal shows is_removed=True."""
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    prop_id = client.get(f"/rounds/{rid}/proposals").json()[0]["id"]

    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_c))

    r = client.get(f"/rounds/{rid}/proposals/{prop_id}")
    assert r.status_code == 200
    assert r.json()["is_removed"] is True


def test_critique_auto_removed_after_threshold(client, agent_a, agent_b, agent_c, round_critique):
    """A critique reported by ≥2 distinct agents is removed from listings."""
    rid = round_critique["id"]
    proposals = client.get(f"/rounds/{rid}").json()["proposals"]
    alice_prop = next(p for p in proposals if p["agent_name"] == "Alice")

    critique = client.post(
        f"/rounds/{rid}/critiques",
        json={"proposal_id": alice_prop["id"], "content": "Bob's critique"},
        headers=h(agent_b),
    ).json()
    crit_id = critique["id"]

    client.post(f"/rounds/{rid}/critiques/{crit_id}/report", json={}, headers=h(agent_a))
    client.post(f"/rounds/{rid}/critiques/{crit_id}/report", json={}, headers=h(agent_c))

    remaining = client.get(f"/rounds/{rid}/critiques").json()
    assert not any(c["id"] == crit_id for c in remaining)


def test_round_state_excludes_removed_proposals(client, agent_a, agent_b, agent_c, round_proposal):
    """GET /rounds/{id} does not include removed proposals."""
    rid = round_proposal["id"]
    client.post(f"/rounds/{rid}/proposals", json={"content": "Alice prop"}, headers=h(agent_a))
    prop_id = client.get(f"/rounds/{rid}/proposals").json()[0]["id"]

    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_b))
    client.post(f"/rounds/{rid}/proposals/{prop_id}/report", json={}, headers=h(agent_c))

    state = client.get(f"/rounds/{rid}").json()
    assert not any(p["id"] == prop_id for p in state["proposals"])
