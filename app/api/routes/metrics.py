from fastapi import APIRouter, status, Depends
from app.schemas.metric import MetricBatch
from app.api.deps import get_current_source, get_db
from app.models.source import Source
from sqlalchemy.orm import Session
from app.models.metric import Metric 

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest_metrics(payload: MetricBatch, source: Source = Depends(get_current_source), db: Session = Depends(get_db)):
    for m in payload.metrics:
        row = Metric(
            event_id = m.event_id,
            event_time = m.event_time, 
            metric = m.metric,
            value = m.value,
            source_id = source.id
        )
        db.add(row)
    db.commit()
    return {"accepted" : len(payload.metrics)}