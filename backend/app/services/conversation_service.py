import uuid
import logging
from typing import List
from sqlalchemy.orm import Session
from app.models.conversation import Conversation
from app.models.message import Message
from app.core.exceptions import NotFoundException, ForbiddenException, ValidationException
from app.repositories.conversation_repo import get_conversation_by_id

logger = logging.getLogger("app.services.conversation")

class ConversationService:
    def verify_conversation_ownership(
        self,
        db: Session,
        conv_id: uuid.UUID,
        user_id: uuid.UUID | None,
        session_id: str | None
    ) -> Conversation:
        """
        Shared DRY validation logic to verify conversation ownership.
        Raises NotFoundException if missing, ForbiddenException if owned by someone else.
        """
        conv = get_conversation_by_id(db, conv_id)
        if not conv:
            raise NotFoundException("Conversation not found")

        # Check if conversation is owned by a registered user
        if conv.user_id is not None:
            if user_id is None or conv.user_id != user_id:
                logger.warning(f"Unauthorized access attempt to user conversation '{conv_id}'")
                raise ForbiddenException("Access to this conversation is forbidden")
        else:
            # Owned by anonymous session
            if session_id is None or conv.session_id != session_id:
                logger.warning(f"Unauthorized access attempt to anonymous session conversation '{conv_id}'")
                raise ForbiddenException("Access to this conversation is forbidden")
                
        return conv

    def list_conversations_paginated(
        self,
        db: Session,
        user_id: uuid.UUID | None,
        session_id: str | None,
        page: int = 0,
        size: int = 20
    ) -> List[Conversation]:
        """
        Paginates active conversations for a user/session, sorted by updatedAt DESC.
        """
        query = db.query(Conversation).filter(Conversation.is_deleted == False)

        if user_id:
            query = query.filter(Conversation.user_id == user_id)
        elif session_id:
            # Filter strictly by session ID and ensure user_id is null for guest access
            query = query.filter(Conversation.session_id == session_id, Conversation.user_id == None)
        else:
            return []

        # Sort by updated_at DESC and apply pagination offsets
        return (
            query.order_by(Conversation.updated_at.desc())
            .offset(page * size)
            .limit(size)
            .all()
        )

    def list_messages_paginated(
        self,
        db: Session,
        conv_id: uuid.UUID,
        user_id: uuid.UUID | None,
        session_id: str | None,
        page: int = 0,
        size: int = 50
    ) -> List[Message]:
        """
        Paginates active messages for a conversation, ordered by createdAt ASC.
        Reuses shared verify_conversation_ownership logic.
        """
        # Enforce DRY ownership verification
        self.verify_conversation_ownership(db, conv_id, user_id, session_id)

        # Retrieve messages sorted by creation timestamp ascending
        return (
            db.query(Message)
            .filter(Message.conversation_id == conv_id, Message.is_deleted == False)
            .order_by(Message.created_at.asc())
            .offset(page * size)
            .limit(size)
            .all()
        )

    def rename_conversation(
        self,
        db: Session,
        conv_id: uuid.UUID,
        user_id: uuid.UUID | None,
        session_id: str | None,
        title: str
    ) -> Conversation:
        """
        Renames a conversation's title. Reuses ownership checks and validates title bounds.
        """
        # Validate title boundaries
        stripped_title = title.strip()
        if not stripped_title:
            raise ValidationException("Conversation title must be non-empty.")
        if len(stripped_title) > 100:
            raise ValidationException("Conversation title exceeds maximum limit of 100 characters.")

        # Enforce DRY ownership verification
        conv = self.verify_conversation_ownership(db, conv_id, user_id, session_id)

        # Apply update
        conv.title = stripped_title
        db.commit()
        db.refresh(conv)
        logger.info(f"Conversation '{conv_id}' successfully renamed to '{stripped_title}'")
        return conv

    def delete_conversation(
        self,
        db: Session,
        conv_id: uuid.UUID,
        user_id: uuid.UUID | None,
        session_id: str | None
    ) -> bool:
        """
        Soft deletes a conversation and cascades is_deleted=true to its messages.
        Reuses verify_conversation_ownership to verify ownership.
        """
        # Reuses verify_conversation_ownership to check ownership
        self.verify_conversation_ownership(db, conv_id, user_id, session_id)
        from app.repositories.conversation_repo import soft_delete_conversation
        return soft_delete_conversation(db, conv_id)

    def delete_all_conversations(
        self,
        db: Session,
        user_id: uuid.UUID | None,
        session_id: str | None
    ) -> int:
        """
        Soft deletes all conversations for the user/session, cascading to messages.
        """
        from app.repositories.conversation_repo import clear_all_conversations
        return clear_all_conversations(db, user_id, session_id)

# Instantiate singleton conversation service instance
conversation_service = ConversationService()

