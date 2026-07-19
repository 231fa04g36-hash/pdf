from .base import BaseSchema

class LinkSessionRequest(BaseSchema):
    """
    Schema for session linking requests containing the anonymous session_id.
    """
    session_id: str
