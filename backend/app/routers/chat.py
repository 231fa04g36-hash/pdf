from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user_optional, get_session_id
from app.schemas.chat import ChatRequest
from app.services.chat_service import chat_service
from app.models import User
from app.utils.rate_limiter import rate_limit_chat

router = APIRouter(tags=["Chat"])

@router.post("/chat", dependencies=[Depends(rate_limit_chat)])
def chat(
    request_data: ChatRequest,
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """
    Core Chat Endpoint. Runs RAG query retrieval and streams back chunked responses.
    """
    generator = chat_service.generate_chat_stream(
        db=db,
        document_id=request_data.document_id,
        conversation_id=request_data.conversation_id,
        question=request_data.question,
        request_id=request_data.request_id,
        user_id=current_user.id if current_user else None,
        session_id=session_id
    )
    return StreamingResponse(generator, media_type="text/plain")
