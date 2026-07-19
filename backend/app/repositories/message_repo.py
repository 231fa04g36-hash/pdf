import uuid
from typing import List
from sqlalchemy.orm import Session
from app.models.message import Message

def get_message_by_id(db: Session, msg_id: uuid.UUID) -> Message | None:
    """Fetch message by ID, checking that it has not been soft-deleted."""
    return db.query(Message).filter(
        Message.id == msg_id,
        Message.is_deleted == False
    ).first()

def list_messages_for_conversation(db: Session, conversation_id: uuid.UUID) -> List[Message]:
    """Fetch all active messages under a conversation, sorted by creation timestamp."""
    return db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.is_deleted == False
    ).order_by(Message.created_at.asc()).all()

def create_message(
    db: Session,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    source_citations: List[dict] | None = None
) -> Message:
    """Create a new message database entry."""
    msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        source_citations=source_citations
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg

def soft_delete_message(db: Session, msg_id: uuid.UUID) -> bool:
    """Soft delete a message by setting is_deleted=True."""
    msg = db.query(Message).filter(Message.id == msg_id, Message.is_deleted == False).first()
    if not msg:
        return False
    msg.is_deleted = True
    db.commit()
    return True
