from datetime import datetime
from uuid import UUID
from typing import List, Optional
from .base import BaseSchema
from .message import MessageResponse

class ConversationBase(BaseSchema):
    title: str

class ConversationCreate(ConversationBase):
    document_id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None

class ConversationUpdate(BaseSchema):
    title: str

class ConversationResponse(ConversationBase):
    id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    document_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

from .document import DocumentResponse

class ConversationListItemResponse(BaseSchema):
    id: UUID
    title: str
    updated_at: datetime
    document: DocumentResponse

