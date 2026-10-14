from fastapi import APIRouter, status, Depends
from app.schemas.metric import MetricBatch
from app.api.deps import get_current_source
from app.models.source import Source

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.post("", status_code=status.HTTP_202_ACCEPTED)
def ingest_metrics(payload: MetricBatch, source: Source = Depends(get_current_source)):
    pass