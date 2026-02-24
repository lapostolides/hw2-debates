from tests.conftest import h


def test_register_returns_api_key(client):
    r = client.post("/agents", json={"name": "Alice"})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Alice"
    assert "api_key" in data
    assert len(data["api_key"]) == 36  # UUID format
    assert data["total_score"] == 0


def test_register_duplicate_name_returns_existing(client):
    first = client.post("/agents", json={"name": "Alice"}).json()
    second = client.post("/agents", json={"name": "Alice"}).json()
    assert second["id"] == first["id"]  # same agent returned


def test_register_empty_name(client):
    r = client.post("/agents", json={"name": ""})
    assert r.status_code == 422


def test_register_name_too_long(client):
    r = client.post("/agents", json={"name": "x" * 65})
    assert r.status_code == 422


def test_register_name_whitespace_only(client):
    r = client.post("/agents", json={"name": "   "})
    assert r.status_code == 422


def test_get_agent_public(client, agent_a):
    r = client.get(f"/agents/{agent_a['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Alice"
    assert "api_key" not in data  # must not expose key
    assert "total_score" in data


def test_get_agent_not_found(client):
    r = client.get("/agents/9999")
    assert r.status_code == 404
