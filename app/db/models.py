import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20))
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    sender: Mapped[str] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    body: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    classification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # pending / approved / dismissed
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Preference(Base):
    __tablename__ = "preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # sender / topic / tone
    type: Mapped[str] = mapped_column(String(20))
    value: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
