import uuid
from .base import BaseSchema

class ChatRequest(BaseSchema):
    """
    Request schema for the core chat streaming endpoint.
    Converts snake_case to camelCase attributes automatically.
    """
    document_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    question: str
    request_id: uuid.UUID
