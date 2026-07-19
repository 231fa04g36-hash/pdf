from typing import Generic, TypeVar, Optional, List, Any
from .base import BaseSchema

T = TypeVar("T")

class ResponseEnvelope(BaseSchema, Generic[T]):
    """
    Standard envelope format for successful responses.
    """
    success: bool = True
    message: str
    data: Optional[T] = None

class ErrorEnvelope(BaseSchema):
    """
    Standard envelope format for error responses.
    """
    success: bool = False
    message: str
    errors: List[Any] = []
