from datetime import datetime
from uuid import UUID
from typing import List, Union
from .base import BaseSchema

class CitationSchema(BaseSchema):
    page: Union[str, int]
    snippet: str

class MessageBase(BaseSchema):
    role: str  # 'user' or 'assistant'
    content: str
    source_citations: List[CitationSchema] | None = None

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime
