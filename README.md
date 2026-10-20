# PulseBoard

A small time-series monitoring platform, like a mini Grafana or Datadog.
Machines send metrics (CPU, memory, and so on) over HTTP. People log in to a
dashboard to see charts and alerts.

Stack: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic.

## Running the tests

```
docker compose up -d
uv run pytest
```

## Schema: why the metrics index is `(source_id, metric, event_time)`

Every dashboard query asks the same shape of question:

> "Give me **this** source's **cpu** values **between 10:00 and 11:00**."

That is two exact matches (`source_id = ?`, `metric = ?`) followed by one
range (`event_time BETWEEN ? AND ?`).

A composite index is sorted like a phone book: by the first column, then the
second inside that, then the third inside that. Postgres can only use the
columns from the left, in order, and it can only use a range on the **last**
column it uses.

With `(source_id, metric, event_time)` Postgres jumps straight to "web-01 /
cpu", and inside that block the rows are already in time order. It reads one
continuous slice from 10:00 to 11:00 and stops. Nothing outside the answer is
touched.

Why not other orders:

- **`(event_time, source_id, metric)`**: time comes first, so the hour from
  10:00 to 11:00 contains every source and every metric mixed together.
  Postgres has to read all of them and throw most away.
- **`(metric, source_id, event_time)`**: this works for the same query, since
  both equality columns come before the range. `source_id` goes first because
  every query is scoped to one source, and a source-only lookup ("what
  metrics does web-01 send?") can still use the index.
- **No index**: every chart load scans the whole table, which only grows.

Rule of thumb: equality columns first, the range column last.

## Schema: why the metrics primary key is `(event_id, event_time)`

`event_id` is a UUID the sender generates. If a sender retries a batch after
a timeout, the same `event_id` arrives twice and the database rejects the
duplicate. The database enforces uniqueness, so the application doesn't have
to check. `event_time` is in the key because Phase 3 partitions the table by
time, and Postgres requires the partition column to be part of the primary
key.
