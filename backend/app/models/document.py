import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    chroma_collection_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # OLD: columns definition without metadata extraction columns, kept for reference
    # detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    detected_language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    extracted_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_authors: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())



    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="documents")
    conversations: Mapped[list["Conversation"]] = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")
