import pytest
import uuid

@pytest.fixture
def created(admin_client) -> dict:
    r = admin_client.post("/sources", json={"name": "web-01"})
    assert r.status_code == 201, r.text
    return r.json()


def test_post_metrics_without_api_key_is_401(client):
    assert client.post("/metrics", json={"metrics": []}).status_code == 401

def test_post_one_metric_is_accepted(client, created):
    r = client.post(
        "/metrics",
        headers={"X-API-Key": created["api_key"]},
        json={
            "metrics": [
                {
                    "metric": "cpu",
                    "value": 42.5,
                    "event_time": "2026-10-15T10:00:00Z",
                    "event_id": str(uuid.uuid4()),
                }
            ]
        },
    )
    assert r.status_code == 202
    assert r.json() == {"accepted": 1}

def test_retried_batch_is_accepted_and_not_stored_twice(client, created, db):
    from sqlalchemy import func, select
    from app.models.metric import Metric

    body = {
        "metrics": [
            {
                "metric": "cpu",
                "value": 42.5,
                "event_time": "2026-10-15T10:00:00Z",
                "event_id": str(uuid.uuid4()),
            }
        ]
    }
    headers = {"X-API-Key": created["api_key"]}

    first = client.post("/metrics", headers=headers, json=body)
    second = client.post("/metrics", headers=headers, json=body)

    assert first.json() == {"accepted": 1}
    assert second.status_code == 202
    assert second.json() == {"accepted": 0}
    assert db.execute(select(func.count()).select_from(Metric)).scalar_one() == 1


def test_empty_batch_is_accepted(client, created):
    r = client.post("/metrics", headers={"X-API-Key": created["api_key"]}, json={"metrics": []})
    assert r.status_code == 202
    assert r.json() == {"accepted": 0}
