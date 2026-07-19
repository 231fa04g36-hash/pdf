from datetime import datetime
from uuid import UUID
from pydantic import EmailStr
from .base import BaseSchema

class UserBase(BaseSchema):
    email: EmailStr | None = None
    display_name: str | None = None

class UserCreate(UserBase):
    firebase_uid: str | None = None

class UserResponse(UserBase):
    id: UUID
    firebase_uid: str | None = None
    created_at: datetime
