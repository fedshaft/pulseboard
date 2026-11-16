from datetime import datetime
from pydantic import BaseModel


class MetricPoint(BaseModel):
    event_time: datetime
    value: float

class MetricBucket(BaseModel):
    bucket_start: datetime
    avg: float
    min: float
    max: float
    count: int
