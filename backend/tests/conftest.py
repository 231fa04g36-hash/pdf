import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.services.vector_store_service import vector_store_service
import app.core.firebase as firebase_module

# In-memory SQLite database setup for integration tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    # Seed default test users
    from app.models.user import User
    db = TestingSessionLocal()
    user1 = User(
        id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        firebase_uid="firebase-test-user-123",
        email="developer@pdfchatbot.com",
        display_name="Dev User"
    )
    user2 = User(
        id=uuid.UUID("2f2ca46c-4064-44ee-be69-cb261ea57365"),
        firebase_uid="other-user-456",
        email="other@example.com",
        display_name="Other User"
    )
    db.add(user1)
    db.add(user2)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(autouse=True)
def override_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture(autouse=True)
def mock_external_deps(monkeypatch):
    # Mock Firebase Token Verification
    def mock_verify_firebase_token(token: str) -> dict:
        if token == "mock-token-for-dev":
            return {
                "uid": "firebase-test-user-123",
                "email": "developer@pdfchatbot.com",
                "name": "Dev User"
            }
        elif token.startswith("mock-token:"):
            parts = token.split(":")
            uid = parts[1] if len(parts) > 1 else "mock-uid"
            email = parts[2] if len(parts) > 2 else "mock@example.com"
            name = parts[3] if len(parts) > 3 else "Mock User"
            return {"uid": uid, "email": email, "name": name}
        raise ValueError("Invalid token")
    
    monkeypatch.setattr(firebase_module, "verify_firebase_token", mock_verify_firebase_token)
    
    import app.dependencies.auth as auth_dep
    monkeypatch.setattr(auth_dep, "verify_firebase_token", mock_verify_firebase_token)

    import app.services.auth_service as auth_svc
    monkeypatch.setattr(auth_svc, "verify_firebase_token", mock_verify_firebase_token)


    # Mock ChromaDB vector store methods
    monkeypatch.setattr(vector_store_service, "store_document_chunks", lambda doc_id, chunks, embeddings: None)
    monkeypatch.setattr(vector_store_service, "delete_document_collection", lambda doc_id: None)
    monkeypatch.setattr(vector_store_service, "query_similar_chunks", lambda query_embedding, doc_id, top_k=5: [
        {"page_number": 1, "text": "Hello, PDF parsing!"}
    ])
    monkeypatch.setattr(vector_store_service, "query_hybrid", lambda *args, **kwargs: [
        {"chunk_text": "Hello, PDF parsing!", "text": "Hello, PDF parsing!", "page_number": 1, "chunk_index": 0, "fused_score": 1.0}
    ])
    # OLD: only mocked reranker_service, kept for reference
    # from app.services.reranker_service import reranker_service
    # monkeypatch.setattr(reranker_service, "rerank_chunks", lambda question, candidate_chunks, top_n=5: [{**c, "rerank_score": 1.0} for c in candidate_chunks[:top_n]])

    from app.services.reranker_service import reranker_service
    monkeypatch.setattr(reranker_service, "rerank_chunks", lambda question, candidate_chunks, top_n=5: [{**c, "rerank_score": 1.0} for c in candidate_chunks[:top_n]])

    # Mock get_llm_provider to prevent real LLM/Ollama network calls during integration tests
    from app.services.llm_providers.ollama_provider import OllamaProvider
    
    class MockLLMProvider:
        def generate_stream(self, prompt, system_prompt, temperature, max_tokens, *args, **kwargs):
            yield {"type": "token", "token": "Based on the context, this is a mock answer. "}
            yield {"type": "usage", "input_tokens": 10, "output_tokens": 5, "cost": 0.0}

    def mock_get_llm_provider():
        import inspect
        stack = inspect.stack()
        for frame in stack:
            if "ollama" in frame.function.lower():
                return OllamaProvider()
        return MockLLMProvider()

    import app.services.chat_service as chat_svc_mod
    monkeypatch.setattr(chat_svc_mod, "get_llm_provider", mock_get_llm_provider)



@pytest.fixture
def client():
    return TestClient(app)
