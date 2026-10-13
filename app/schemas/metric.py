from datetime import datetime
from pydantic import BaseModel
from decimal import Decimal
import uuid

class MetricIn(BaseModel):
    metric: str
    value: Decimal
    event_time: datetime
    event_id: uuid.UUID

class MetricBatch(BaseModel):
    metrics: list[MetricIn]