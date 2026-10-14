from fastapi import APIRouter, status
from app.schemas.metric import MetricBatch

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest_metrics(payload: MetricBatch):
    pass