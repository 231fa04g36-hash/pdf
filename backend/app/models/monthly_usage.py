import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class MonthlyUsage(Base):
    __tablename__ = "monthly_usages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    month: Mapped[str] = mapped_column(String(7), unique=True, nullable=False, index=True)  # Format: YYYY-MM e.g. "2026-07"
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_estimate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
