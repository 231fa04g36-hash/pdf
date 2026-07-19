import uuid
from fastapi import APIRouter, Depends, File, UploadFile, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user_optional, get_session_id
from app.schemas.envelope import ResponseEnvelope
from app.schemas.document import UploadDocumentResponse
from app.services.document_service import document_service
from app.models import User
from app.utils.rate_limiter import rate_limit_upload

router = APIRouter(tags=["Documents"])

@router.post("/documents/upload", response_model=ResponseEnvelope[UploadDocumentResponse], dependencies=[Depends(rate_limit_upload)])
def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session_id: str | None = Depends(get_session_id),
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> ResponseEnvelope[UploadDocumentResponse]:
    """
    Upload a PDF document. Verifies magic bytes signature, size limits (10MB),
    parses pages text, triggers optional OCR fallback, and saves DB entry.
    """
    # Read content length from request headers safely
    content_length_str = request.headers.get("content-length")
    content_length = int(content_length_str) if content_length_str else None

    # Delegate upload pipeline execution to the service layer (thin controller)
    result = document_service.process_pdf_upload(
        db=db,
        file=file,
        content_length=content_length,
        current_user=current_user,
        session_id=session_id
    )

    return ResponseEnvelope(
        success=True,
        message="Document uploaded and processed successfully.",
        data=UploadDocumentResponse(**result)
    )

@router.delete("/documents/{id}", status_code=204)
def delete_document(
    id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    """
    Deletes a document, checking ownership and triggering ChromaDB collection cleanup.
    Logs deletion at INFO level.
    """
    import logging
    from app.core.exceptions import NotFoundException, ForbiddenException
    from app.repositories.document_repo import get_document_by_id

    logger = logging.getLogger("app.routers.document")
    doc = get_document_by_id(db, id)
    if not doc:
        raise NotFoundException("Document not found")

    user_id = current_user.id if current_user else None
    if doc.user_id is not None:
        if user_id is None or doc.user_id != user_id:
            raise ForbiddenException("Access forbidden")
    else:
        if session_id is None or doc.session_id != session_id:
            raise ForbiddenException("Access forbidden")

    success = document_service.delete_document(db, id)
    if not success:
        raise NotFoundException("Document not found")

    logger.info(f"AUDIT LOG: Document deleted. actor_user_id={user_id}, actor_session_id={session_id}, document_id={id}")
    return

@router.get("/documents/{id}/file")
def get_document_file(
    id: uuid.UUID,
    current_user: User | None = Depends(get_current_user_optional),
    session_id: str | None = Depends(get_session_id),
    db: Session = Depends(get_db)
):
    """
    Retrieves the raw PDF file for a document.
    Checks ownership using the same rules as delete_document.
    """
    import os
    from fastapi.responses import FileResponse
    from app.core.exceptions import NotFoundException, ForbiddenException
    from app.repositories.document_repo import get_document_by_id

    doc = get_document_by_id(db, id)
    if not doc:
        raise NotFoundException("Document not found")

    user_id = current_user.id if current_user else None
    if doc.user_id is not None:
        if user_id is None or doc.user_id != user_id:
            raise ForbiddenException("Access forbidden")
    else:
        if session_id is None or doc.session_id != session_id:
            raise ForbiddenException("Access forbidden")

    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    file_path = os.path.join(uploads_dir, f"{id}.pdf")
    if not os.path.exists(file_path):
        raise NotFoundException("Physical file not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=doc.filename
    )


