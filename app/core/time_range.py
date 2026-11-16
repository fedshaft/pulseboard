from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import HTTPException, status

RangeName = Literal["15m", "1h", "24h", "7d"]
RANGES: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}

IntervalName = Literal["1m", "5m", "15m", "1h", "1d"]
INTERVALS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

def resolve_range(
    range_: RangeName | None,
    start: datetime | None,
    end: datetime | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    
    if range_ is not None:
        if start is not None or end is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "use either range or start/end, not both")
        end = now or datetime.now(timezone.utc)
        return end - RANGES[range_], end

    if start is None or end is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "give a range, or both start and end")
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start and end need a timezone, e.g. 2026-10-20T10:00:00Z")
    if start >= end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start must be before end")
    return start, end
