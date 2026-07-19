from datetime import datetime
from uuid import UUID
from .base import BaseSchema

class DocumentBase(BaseSchema):
    filename: str
    page_count: int
    ocr_triggered: bool = False
    chroma_collection_id: str | None = None

class DocumentCreate(DocumentBase):
    user_id: UUID | None = None
    session_id: str | None = None

class DocumentResponse(DocumentBase):
    id: UUID
    user_id: UUID | None = None
    session_id: str | None = None
    created_at: datetime

from pydantic import ConfigDict

class UploadDocumentResponse(BaseSchema):
    """
    Response schema returning exact snake_case JSON keys to match the frontend expectations.
    """
    document_id: UUID
    filename: str
    page_count: int
    ocr_triggered: bool

    # Disable camelCase generator for this specific endpoint response
    model_config = ConfigDict(
        alias_generator=None,
        populate_by_name=True,
        from_attributes=True
    )

