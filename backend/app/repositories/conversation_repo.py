import uuid
from typing import List
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message

def get_conversation_by_id(db: Session, conv_id: uuid.UUID) -> Conversation | None:
    """Fetch conversation by ID, ensuring it has not been soft-deleted."""
    return db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.is_deleted == False
    ).first()

def list_conversations_for_user(
    db: Session, 
    user_id: uuid.UUID | None = None, 
    session_id: str | None = None
) -> List[Conversation]:
    """List all active conversations for a user or anonymous session, sorted by recent updates."""
    query = db.query(Conversation).filter(Conversation.is_deleted == False)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    elif session_id:
        query = query.filter(Conversation.session_id == session_id, Conversation.user_id == None)
    else:
        return []
    return query.order_by(Conversation.updated_at.desc()).all()

def create_conversation(
    db: Session,
    title: str,
    document_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
    session_id: str | None = None
) -> Conversation:
    """Create a new conversation DB entry."""
    conv = Conversation(
        id=uuid.uuid4(),
        title=title,
        document_id=document_id,
        user_id=user_id,
        session_id=session_id
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

def rename_conversation(db: Session, conv_id: uuid.UUID, new_title: str) -> Conversation | None:
    """Rename a conversation's title."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.is_deleted == False).first()
    if not conv:
        return None
    conv.title = new_title
    db.commit()
    db.refresh(conv)
    return conv

def soft_delete_conversation(db: Session, conv_id: uuid.UUID) -> bool:
    """Soft delete a conversation by setting is_deleted=True and cascades to its Messages."""
    conv = db.query(Conversation).filter(Conversation.id == conv_id, Conversation.is_deleted == False).first()
    if not conv:
        return False
    conv.is_deleted = True
    # Cascade is_deleted=True to its Messages
    db.query(Message).filter(Message.conversation_id == conv_id, Message.is_deleted == False).update({Message.is_deleted: True})
    db.commit()
    return True

def clear_all_conversations(db: Session, user_id: uuid.UUID | None = None, session_id: str | None = None) -> int:
    """Soft delete all conversations belonging to a user or session, cascading to messages."""
    query = db.query(Conversation).filter(Conversation.is_deleted == False)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    elif session_id:
        query = query.filter(Conversation.session_id == session_id, Conversation.user_id == None)
    else:
        return 0

    active_conversations = query.all()
    count = 0
    for conv in active_conversations:
        conv.is_deleted = True
        # Cascade to messages under this conversation
        db.query(Message).filter(Message.conversation_id == conv.id, Message.is_deleted == False).update({Message.is_deleted: True})
        count += 1
    
    if count > 0:
        db.commit()
    
    return count
