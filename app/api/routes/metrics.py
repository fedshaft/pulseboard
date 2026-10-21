from fastapi import APIRouter, status, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.schemas.metric import MetricBatch
from app.api.deps import get_current_source, get_db
from app.models.source import Source
from app.models.metric import Metric

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest_metrics(payload: MetricBatch, source: Source = Depends(get_current_source), db: Session = Depends(get_db)):
    if not payload.metrics:
        return {"accepted": 0}

    rows = [
        {
            "event_id": m.event_id,
            "event_time": m.event_time,
            "metric": m.metric,
            "value": m.value,
            "source_id": source.id,
        }
        for m in payload.metrics
    ]
    stmt = (insert(Metric).values(rows).on_conflict_do_nothing(index_elements=["event_id", "event_time"]).returning(Metric.event_id))
    inserted = db.execute(stmt).all()
    db.commit()
    return {"accepted": len(inserted)}
