import uuid
from datetime import datetime, timedelta, timezone
import pytest

T0 = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def source(admin_client) -> dict:
    r = admin_client.post("/sources", json={"name": "web-01"})
    assert r.status_code == 201, r.text
    return r.json()


def send(client, source, metric, points):
    body = {
        "metrics": [
            {
                "metric": metric,
                "value": value,
                "event_time": (T0 + timedelta(minutes=m)).isoformat(),
                "event_id": str(uuid.uuid4()),
            }
            for m, value in points
        ]
    }
    r = client.post("/metrics", headers={"X-API-Key": source["api_key"]}, json=body)
    assert r.status_code == 202, r.text


def window(start_min, end_min):
    return {
        "start": (T0 + timedelta(minutes=start_min)).isoformat(),
        "end": (T0 + timedelta(minutes=end_min)).isoformat(),
    }


def test_queries_need_login(client):
    assert client.get("/metrics/latest", params={"source_id": 1, "metric": "cpu"}).status_code == 401


def test_latest_returns_newest_point(client, viewer_client, source):
    send(client, source, "cpu", [(0, 10), (2, 30), (1, 20)])
    send(client, source, "mem", [(5, 99)])

    r = viewer_client.get("/metrics/latest", params={"source_id": source["id"], "metric": "cpu"})

    assert r.status_code == 200
    assert r.json()["value"] == 30


def test_latest_with_no_data_is_404(viewer_client, source):
    r = viewer_client.get("/metrics/latest", params={"source_id": source["id"], "metric": "cpu"})
    assert r.status_code == 404


def test_unknown_source_is_404(viewer_client):
    r = viewer_client.get("/metrics/latest", params={"source_id": 999, "metric": "cpu"})
    assert r.status_code == 404


def test_raw_range_returns_points_in_window_oldest_first(client, viewer_client, source):
    send(client, source, "cpu", [(0, 1), (5, 2), (10, 3), (15, 4)])

    r = viewer_client.get(
        "/metrics", params={"source_id": source["id"], "metric": "cpu", **window(5, 15)}
    )

    assert r.status_code == 200
    assert [p["value"] for p in r.json()] == [2, 3]


def test_raw_range_rejects_range_and_start_together(viewer_client, source):
    params = {"source_id": source["id"], "metric": "cpu", "range": "1h", **window(0, 5)}
    assert viewer_client.get("/metrics", params=params).status_code == 422


def test_raw_range_rejects_unknown_preset(viewer_client, source):
    params = {"source_id": source["id"], "metric": "cpu", "range": "3h"}
    assert viewer_client.get("/metrics", params=params).status_code == 422


def test_aggregate_groups_points_into_buckets(client, viewer_client, source):
    send(client, source, "cpu", [(0, 10), (2, 20), (4, 30), (6, 50)])

    r = viewer_client.get(
        "/metrics/aggregate",
        params={"source_id": source["id"], "metric": "cpu", "interval": "5m", **window(0, 10)},
    )

    assert r.status_code == 200
    assert r.json() == [
        {"bucket_start": "2026-10-20T10:00:00Z", "avg": 20.0, "min": 10.0, "max": 30.0, "count": 3},
        {"bucket_start": "2026-10-20T10:05:00Z", "avg": 50.0, "min": 50.0, "max": 50.0, "count": 1},
    ]
