import pytest

@pytest.fixture
def created(admin_client) -> dict:
    r = admin_client.post("/sources", json={"name": "web-01"})
    assert r.status_code == 201, r.text
    return r.json()


def test_post_metrics_without_api_key_is_401(client):
    assert client.post("/metrics", json={"metrics": []}).status_code == 401