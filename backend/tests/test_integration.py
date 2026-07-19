import pytest
import uuid
import json
from unittest.mock import MagicMock
from app.models.document import Document
from app.models.conversation import Conversation
from app.models.message import Message

valid_pdf_content = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
    b"/Resources << >> /Contents 4 0 R >>\nendobj\n"
    b"4 0 obj\n<< /Length 45 >>\nstream\n"
    b"BT /F1 12 Tf 70 700 Td (Hello, PDF parsing!) Tj ET\nendstream\nendobj\n"
    b"xref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000062 00000 n\n"
    b"0000000121 00000 n\n0000000244 00000 n\ntrailer\n"
    b"<< /Size 5 /Root 1 0 R >>\nstartxref\n340\n%%EOF"
)

# =========================================================================
# Integration Tests: POST /documents/upload
# =========================================================================
def test_upload_document_happy_path(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("sample.pdf", valid_pdf_content, "application/pdf")},
        headers={
            "X-Session-Id": "integration-session-123",
            "Authorization": "Bearer mock-token-for-dev"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "document_id" in data["data"]
    assert data["data"]["filename"] == "sample.pdf"
    assert data["data"]["page_count"] == 1

def test_upload_document_invalid_type(client):
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("hacker.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/octet-stream")},
        headers={
            "X-Session-Id": "integration-session-123"
        }
    )
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "Only valid PDF files are supported" in data["message"]

def test_upload_document_oversized(client):
    # Construct an oversized request header
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("large.pdf", b"%PDF-1.4 mock content", "application/pdf")},
        headers={
            "X-Session-Id": "integration-session-123",
            "Content-Length": str(16 * 1024 * 1024) # 16MB
        }
    )
    assert response.status_code == 413


# =========================================================================
# Integration Tests: POST /chat
# =========================================================================
def test_chat_happy_path(client, db):
    # Seed a valid document in the test database matching default provider model
    from app.services.embedding_service import embedding_service
    active_model = embedding_service.get_embedding_model_info(lang="en")
    
    doc = Document(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        filename="report.pdf",
        page_count=1,
        chroma_collection_id="col_test_doc",
        embedding_model=active_model, # matches local model
        is_deleted=False
    )
    db.add(doc)
    db.commit()

    payload = {
        "documentId": str(doc.id),
        "question": "What is RAG?",
        "requestId": str(uuid.uuid4())
    }
    
    headers = {
        "X-Session-Id": "chat-session-123",
        "Authorization": "Bearer mock-token-for-dev",
        "Content-Type": "application/json"
    }

    # Make request
    response = client.post("/api/v1/chat", json=payload, headers=headers)
    assert response.status_code == 200
    
    # Verify chunked stream contents
    text_chunks = response.text.split("\n")
    assert len(text_chunks) > 0
    # Must contain streamed token or citation payload
    first_chunk = json.loads(text_chunks[0])
    assert "token" in first_chunk or "citations" in first_chunk


# =========================================================================
# Integration Tests: Security Ownership Enforcement (User A vs User B)
# =========================================================================
def test_conversation_ownership_enforcement(client, db):
    # User 1 is '5f2ca46c-4064-44ee-be69-cb261ea57365' (mock-token-for-dev)
    # User 2 is '2f2ca46c-4064-44ee-be69-cb261ea57365' (mock-token:other-user-456)
    
    doc = Document(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        filename="user1_doc.pdf",
        page_count=1,
        is_deleted=False
    )
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        document_id=doc.id,
        title="User 1 Private Conv",
        is_deleted=False
    )
    db.add(doc)
    db.add(conv)
    db.commit()

    headers_user2 = {
        "Authorization": "Bearer mock-token:other-user-456:other@example.com:OtherUser",
        "Content-Type": "application/json"
    }

    # 1. User 2 trying to get User 1's conversation messages must fail with 403 Forbidden
    url_messages = f"/api/v1/conversations/{conv.id}/messages"
    response = client.get(url_messages, headers=headers_user2)
    assert response.status_code == 403
    assert response.json()["success"] is False
    assert "Access to this conversation is forbidden" in response.json()["message"]

    # 2. User 2 trying to PATCH/rename User 1's conversation must fail with 403 Forbidden
    url_rename = f"/api/v1/conversations/{conv.id}"
    response = client.patch(url_rename, json={"title": "Hacked Title"}, headers=headers_user2)
    assert response.status_code == 403

    # 3. User 2 trying to DELETE User 1's conversation must fail with 403 Forbidden
    response = client.delete(url_rename, headers=headers_user2)
    assert response.status_code == 403


# =========================================================================
# Integration Tests: Pagination Behavior
# =========================================================================
def test_conversations_pagination(client, db):
    doc = Document(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        filename="paginated_doc.pdf",
        page_count=1,
        is_deleted=False
    )
    db.add(doc)
    
    # Seed 3 conversations for User 1
    for i in range(3):
        conv = Conversation(
            id=uuid.uuid4(),
            user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
            document_id=doc.id,
            title=f"Paginated Conv {i}",
            is_deleted=False
        )
        db.add(conv)
    db.commit()

    headers_user1 = {
        "Authorization": "Bearer mock-token-for-dev",
        "Content-Type": "application/json"
    }

    # Retrieve page 0, size 2
    response = client.get("/api/v1/conversations?page=0&size=2", headers=headers_user1)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # Should contain exactly 2 conversations
    assert len(data["data"]) == 2
