from datetime import datetime
from sqlalchemy import (BigInteger, CheckConstraint, DateTime, Identity, Text, func)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'viewer')", name="check_role"), )

    id : Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email : Mapped[str] = mapped_column(Text, unique = True)
    password_hash : Mapped[str] = mapped_column(Text)
    role : Mapped[str] = mapped_column(Text, server_default="viewer")
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())