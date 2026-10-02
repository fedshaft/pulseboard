from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    key_prefix: str
    created_at: datetime
    revoked_at: datetime | None


class SourceCreated(SourceOut):
    api_key: str
