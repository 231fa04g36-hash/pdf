import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user_optional, get_session_id
from app.schemas.envelope import ResponseEnvelope
from app.schemas.conversation import ConversationListItemResponse, ConversationUpdate
from app.schemas.message import MessageResponse
from app.services.conversation_service import conversation_service
from app.models import User

logger = logging.getLogger("app.routers.conversation")

router = APIRouter(tags=["Conversations"])

@router.get("/conversations", response_model=ResponseEnvelope[List[ConversationListItemResponse]])
def list_conversations(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
) -> ResponseEnvelope[List[ConversationListItemResponse]]:
    """
    List active conversations for the user/session, paginated and sorted by recent updates.
    """
    conversations = conversation_service.list_conversations_paginated(
        db=db,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
        page=page,
        size=size
    )
    # Map to schema output list
    data = [ConversationListItemResponse.model_validate(c) for c in conversations]
    return ResponseEnvelope(
        success=True,
        message="Conversations listed successfully.",
        data=data
    )

@router.get("/conversations/{id}/messages", response_model=ResponseEnvelope[List[MessageResponse]])
def list_conversation_messages(
    id: uuid.UUID,
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
) -> ResponseEnvelope[List[MessageResponse]]:
    """
    Lists messages of a conversation in chronological order, verifying user/session ownership.
    """
    messages = conversation_service.list_messages_paginated(
        db=db,
        conv_id=id,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
        page=page,
        size=size
    )
    data = [MessageResponse.model_validate(m) for m in messages]
    return ResponseEnvelope(
        success=True,
        message="Conversation messages listed successfully.",
        data=data
    )

@router.patch("/conversations/{id}", response_model=ResponseEnvelope[ConversationListItemResponse])
def rename_conversation(
    id: uuid.UUID,
    payload: ConversationUpdate,
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
) -> ResponseEnvelope[ConversationListItemResponse]:
    """
    Renames a conversation's title, checking ownership validation.
    """
    updated_conv = conversation_service.rename_conversation(
        db=db,
        conv_id=id,
        user_id=current_user.id if current_user else None,
        session_id=session_id,
        title=payload.title
    )
    return ResponseEnvelope(
        success=True,
        message="Conversation renamed successfully.",
        data=ConversationListItemResponse.model_validate(updated_conv)
    )

@router.delete("/conversations/{id}", status_code=204)
def delete_conversation(
    id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    """
    Soft deletes a specific conversation and cascades is_deleted=true to its messages.
    Returns 204 No Content. Logs delete at INFO level.
    """
    conversation_service.delete_conversation(
        db=db,
        conv_id=id,
        user_id=current_user.id if current_user else None,
        session_id=session_id
    )
    logger.info(f"AUDIT LOG: Conversation soft-deleted. actor_user_id={current_user.id if current_user else None}, actor_session_id={session_id}, conversation_id={id}")
    return

@router.delete("/conversations", status_code=204)
def bulk_delete_conversations(
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    """
    Bulk soft-deletes all conversations for the current user/session.
    Returns 204 No Content. Logs delete at INFO level.
    """
    deleted_count = conversation_service.delete_all_conversations(
        db=db,
        user_id=current_user.id if current_user else None,
        session_id=session_id
    )
    logger.info(f"AUDIT LOG: Bulk conversations soft-deleted. actor_user_id={current_user.id if current_user else None}, actor_session_id={session_id}, deleted_count={deleted_count}")
    return

