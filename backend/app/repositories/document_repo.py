import uuid
from typing import List
from sqlalchemy.orm import Session
from app.models.document import Document

def get_document_by_id(db: Session, doc_id: uuid.UUID) -> Document | None:
    """Fetch document by ID, checking that it has not been soft-deleted."""
    return db.query(Document).filter(
        Document.id == doc_id,
        Document.is_deleted == False
    ).first()

def list_documents_for_user(
    db: Session, 
    user_id: uuid.UUID | None = None, 
    session_id: str | None = None
) -> List[Document]:
    """List all active (non-soft-deleted) documents for a user or anonymous session."""
    query = db.query(Document).filter(Document.is_deleted == False)
    if user_id:
        query = query.filter(Document.user_id == user_id)
    elif session_id:
        # If user is anonymous, filter strictly by session ID and ensure user_id is null
        query = query.filter(Document.session_id == session_id, Document.user_id == None)
    else:
        return []
    return query.order_by(Document.created_at.desc()).all()

# OLD: create_document without detected_language support — replaced below to add detected_language database column values
# def create_document(
#     db: Session,
#     filename: str,
#     page_count: int,
#     ocr_triggered: bool = False,
#     chroma_collection_id: str | None = None,
#     user_id: uuid.UUID | None = None,
#     session_id: str | None = None,
#     embedding_model: str | None = None
# ) -> Document:
#     """Create a new document database entry."""
#     doc = Document(
#         id=uuid.uuid4(),
#         user_id=user_id,
#         session_id=session_id,
#         filename=filename,
#         page_count=page_count,
#         ocr_triggered=ocr_triggered,
#         chroma_collection_id=chroma_collection_id,
#         embedding_model=embedding_model
#     )
#     db.add(doc)
#     db.commit()
#     db.refresh(doc)
#     return doc

# OLD: create_document without extracted_title and extracted_authors support, kept for reference
# def create_document(
#     db: Session,
#     filename: str,
#     page_count: int,
#     ocr_triggered: bool = False,
#     chroma_collection_id: str | None = None,
#     user_id: uuid.UUID | None = None,
#     session_id: str | None = None,
#     embedding_model: str | None = None,
#     detected_language: str | None = None
# ) -> Document:
#     """Create a new document database entry."""
#     doc = Document(
#         id=uuid.uuid4(),
#         user_id=user_id,
#         session_id=session_id,
#         filename=filename,
#         page_count=page_count,
#         ocr_triggered=ocr_triggered,
#         chroma_collection_id=chroma_collection_id,
#         embedding_model=embedding_model,
#         detected_language=detected_language
#     )
#     db.add(doc)
#     db.commit()
#     db.refresh(doc)
#     return doc

def create_document(
    db: Session,
    filename: str,
    page_count: int,
    ocr_triggered: bool = False,
    chroma_collection_id: str | None = None,
    user_id: uuid.UUID | None = None,
    session_id: str | None = None,
    embedding_model: str | None = None,
    detected_language: str | None = None,
    extracted_title: str | None = None,
    extracted_authors: str | None = None
) -> Document:
    """Create a new document database entry."""
    doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        session_id=session_id,
        filename=filename,
        page_count=page_count,
        ocr_triggered=ocr_triggered,
        chroma_collection_id=chroma_collection_id,
        embedding_model=embedding_model,
        detected_language=detected_language,
        extracted_title=extracted_title,
        extracted_authors=extracted_authors
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def soft_delete_document(db: Session, doc_id: uuid.UUID) -> bool:
    """Soft delete a document by setting is_deleted=True."""
    doc = db.query(Document).filter(Document.id == doc_id, Document.is_deleted == False).first()
    if not doc:
        return False
    doc.is_deleted = True
    db.commit()
    return True
