import os
import sys
import uuid

# Add parent directory of scripts/ (which is backend/) to python path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models import User, Document, Conversation, Message

def seed() -> None:
    db = SessionLocal()
    try:
        # Clear existing data to make seeding idempotent
        print("Clearing existing database records for fresh seed...")
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.query(Document).delete()
        db.query(User).delete()
        db.commit()

        print("Seeding database...")
        # 1. Create a registered developer user
        user = User(
            id=uuid.uuid4(),
            firebase_uid="firebase-test-user-123",
            email="developer@pdfchatbot.com",
            display_name="Dev User"
        )
        db.add(user)
        db.commit()

        # 2. Create document for registered user
        doc1 = Document(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="financial_report_2026.pdf",
            page_count=24,
            ocr_triggered=False,
            chroma_collection_id="col_financial_2026"
        )
        db.add(doc1)

        # 3. Create document for anonymous user (session tracking)
        doc2 = Document(
            id=uuid.uuid4(),
            user_id=None,
            session_id="anon-session-abc-456",
            filename="user_manual_ocr.pdf",
            page_count=8,
            ocr_triggered=True,
            chroma_collection_id="col_manual_ocr"
        )
        db.add(doc2)
        db.commit()

        # 4. Create conversations
        conv1 = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            document_id=doc1.id,
            title="Q4 Financial Performance"
        )
        db.add(conv1)

        conv2 = Conversation(
            id=uuid.uuid4(),
            user_id=None,
            session_id="anon-session-abc-456",
            document_id=doc2.id,
            title="OCR Scan Query Verification"
        )
        db.add(conv2)
        db.commit()

        # 5. Create messages with source citations
        m1 = Message(
            id=uuid.uuid4(),
            conversation_id=conv1.id,
            role="user",
            content="What was the net revenue in Q4 2025?"
        )
        m2 = Message(
            id=uuid.uuid4(),
            conversation_id=conv1.id,
            role="assistant",
            content="According to the report, the net revenue in Q4 2025 was $12.4 million.",
            source_citations=[{"page": 4, "snippet": "Net revenue for Q4 2025 increased by 8% to $12.4M."}]
        )
        m3 = Message(
            id=uuid.uuid4(),
            conversation_id=conv2.id,
            role="user",
            content="Did the manual mention setup steps?"
        )
        m4 = Message(
            id=uuid.uuid4(),
            conversation_id=conv2.id,
            role="assistant",
            content="Yes, page 2 contains a checklist detailing basic hardware layout and cables.",
            source_citations=[{"page": 2, "snippet": "Hardware checklist: 1. Plug ethernet cable, 2. Power on..."}]
        )

        db.add_all([m1, m2, m3, m4])
        db.commit()

        print("Database successfully seeded with dev data! 🍰")

    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
