from datetime import datetime
from pydantic import BaseModel
from decimal import Decimal

class MetricIn(BaseModel):
    metric: str
    value: Decimal
    event_time: datetime

class MetricBatch(BaseModel):
    metrics: list[MetricIn]