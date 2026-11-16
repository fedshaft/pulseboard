from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from app.core.time_range import resolve_range

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)

def test_preset_range_ends_now():
    assert resolve_range("1h", None, None, now=NOW) == (NOW - timedelta(hours=1), NOW)

def test_custom_range_is_returned_as_given():
    start = NOW - timedelta(days=2)
    assert resolve_range(None, start, NOW) == (start, NOW)

@pytest.mark.parametrize(
    "range_, start, end",
    [
        ("1h", NOW, None),                                
        (None, None, None),                               
        (None, NOW, None),                                 
        (None, NOW, NOW),                                  
        (None, NOW, NOW - timedelta(hours=1)),             
        (None, datetime(2026, 10, 20), datetime(2026, 10, 21)), 
    ],
)
def test_bad_ranges_are_422(range_, start, end):
    with pytest.raises(HTTPException) as e:
        resolve_range(range_, start, end)
    assert e.value.status_code == 422
