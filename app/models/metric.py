import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (Index("ix_metrics_source_id_metric_event_time", "source_id", "metric", "event_time"),)

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sources.id"))
    metric: Mapped[str] = mapped_column(Text)
    value: Mapped[Decimal] = mapped_column(Numeric)
    ingest_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
