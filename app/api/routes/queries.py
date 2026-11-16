from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.core.time_range import INTERVALS, IntervalName, RangeName, resolve_range
from app.models.metric import Metric
from app.models.source import Source
from app.models.user import User
from app.schemas.query import MetricBucket, MetricPoint


router = APIRouter(prefix="/metrics", tags=["metrics"])


BUCKET_ORIGIN = datetime(2000, 1, 1, tzinfo=timezone.utc)


def ensure_source_exists(db: Session, source_id: int) -> None:
    if db.get(Source, source_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")


@router.get("/latest", response_model=MetricPoint)
def latest_value(
    source_id: int,
    metric: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ensure_source_exists(db, source_id)
    row = db.execute(
        select(Metric.event_time, Metric.value)
        .where(Metric.source_id == source_id, Metric.metric == metric)
        .order_by(Metric.event_time.desc())
        .limit(1)
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this metric")
    return MetricPoint(event_time=row.event_time, value=row.value)


@router.get("", response_model=list[MetricPoint])
def raw_range(
    source_id: int,
    metric: str,
    range_: RangeName | None = Query(default=None, alias="range"),
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ensure_source_exists(db, source_id)
    start, end = resolve_range(range_, start, end)
    rows = db.execute(
        select(Metric.event_time, Metric.value)
        .where(
            Metric.source_id == source_id,
            Metric.metric == metric,
            Metric.event_time >= start,
            Metric.event_time < end,
        )
        .order_by(Metric.event_time)
    ).all()
    return [MetricPoint(event_time=r.event_time, value=r.value) for r in rows]


@router.get("/aggregate", response_model=list[MetricBucket])
def aggregated_range(
    source_id: int,
    metric: str,
    interval: IntervalName,
    range_: RangeName | None = Query(default=None, alias="range"),
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ensure_source_exists(db, source_id)
    start, end = resolve_range(range_, start, end)
    bucket = func.date_bin(INTERVALS[interval], Metric.event_time, BUCKET_ORIGIN).label("bucket_start")
    rows = db.execute(
        select(
            bucket,
            func.avg(Metric.value).label("avg"),
            func.min(Metric.value).label("min"),
            func.max(Metric.value).label("max"),
            func.count().label("count"),
        )
        .where(
            Metric.source_id == source_id,
            Metric.metric == metric,
            Metric.event_time >= start,
            Metric.event_time < end,
        )
        .group_by(bucket)
        .order_by(bucket)
    ).all()
    return [
        MetricBucket(bucket_start=r.bucket_start, avg=r.avg, min=r.min, max=r.max, count=r.count)
        for r in rows
    ]
