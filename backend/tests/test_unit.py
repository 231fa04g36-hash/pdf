import pytest
import uuid
from unittest.mock import MagicMock

from app.core.exceptions import (
    InvalidFileTypeException,
    FileTooLargeException,
    CorruptedFileException,
    PasswordProtectedException,
    EmbeddingModelMismatchException,
    ForbiddenException
)
from app.services.chunker_service import chunk_document_pages
from app.services.conversation_service import conversation_service
from app.services.pdf_parser_service import parse_pdf_pages
from app.services.document_service import document_service
from app.models.conversation import Conversation

# =========================================================================
# Unit Tests: Chunker Service
# =========================================================================
def test_chunking_logic():
    # 2 pages of mock text data
    pages = [
        {"page_number": 1, "text": "This is page one text content. " * 30},
        {"page_number": 2, "text": "This is page two text content. " * 20}
    ]
    
    # Run chunker
    chunks = chunk_document_pages(pages, chunk_size=100, chunk_overlap=20)
    
    assert len(chunks) > 0
    # Check that metadata metadata is attached correctly
    first_chunk = chunks[0]
    assert "chunk_index" in first_chunk
    assert "page_number" in first_chunk
    assert "text" in first_chunk
    assert first_chunk["page_number"] == 1
    assert first_chunk["chunk_index"] == 0
    assert "parent_chunk_id" in first_chunk
    assert "parent_chunk_text" in first_chunk
    assert "parent_page_range" in first_chunk
    assert len(first_chunk["parent_chunk_text"]) >= len(first_chunk["text"])


# =========================================================================
# Unit Tests: PDF Parsing & Validation
# =========================================================================
def test_pdf_validation_invalid_type():
    # File upload mock with wrong magic bytes signature
    file_mock = MagicMock()
    file_mock.filename = "hacker.exe"
    file_mock.file.read.return_value = b"MZ\x90\x00\x03\x00\x00\x00"  # PE exe magic bytes
    
    with pytest.raises(InvalidFileTypeException):
        document_service.process_pdf_upload(
            db=MagicMock(),
            file=file_mock,
            content_length=100,
            current_user=None,
            session_id="guest-session-123"
        )

def test_pdf_validation_oversized():
    # File size limit check (content length > 10MB)
    file_mock = MagicMock()
    with pytest.raises(FileTooLargeException):
        document_service.process_pdf_upload(
            db=MagicMock(),
            file=file_mock,
            content_length=11 * 1024 * 1024, # 11MB
            current_user=None,
            session_id="guest-session-123"
        )

def test_pdf_validation_corrupted(monkeypatch):
    # Mock PyMuPDF fitz.open raising an exception representing corrupted file
    import fitz
    def mock_fitz_open(*args, **kwargs):
        raise Exception("Failed to open PDF structure")
    
    monkeypatch.setattr(fitz, "open", mock_fitz_open)
    
    file_mock = MagicMock()
    file_mock.filename = "corrupted.pdf"
    file_mock.file.read.return_value = b"%PDF-1.4 mock corrupted contents"
    
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    try:
        with pytest.raises(CorruptedFileException):
            document_service.process_pdf_upload(
                db=db,
                file=file_mock,
                content_length=100,
                current_user=None,
                session_id="guest-session-123"
            )
    finally:
        db.close()


def test_pdf_validation_password_protected(monkeypatch):
    # Mock PyMuPDF fitz.open returning an encrypted doc
    import fitz
    doc_mock = MagicMock()
    doc_mock.is_encrypted = True
    doc_mock.authenticate.return_value = False # authenticate fails
    
    monkeypatch.setattr(fitz, "open", lambda *args, **kwargs: doc_mock)
    
    with pytest.raises(PasswordProtectedException):
        parse_pdf_pages(b"%PDF-1.4 mock contents")


def test_pdf_parsing_multi_column(monkeypatch):
    # Mock fitz.open to return blocks layout that satisfies the multi-column heuristic
    import fitz
    import pdfplumber
    
    doc_mock = MagicMock()
    page_mock = MagicMock()
    # page width = 600
    page_mock.rect.width = 600
    
    # 4 blocks: 2 on the left (x1 <= 315), 2 on the right (x0 >= 285)
    # block format: (x0, y0, x1, y1, "text", block_no, block_type)
    # block_type = 0 is text block
    def mock_get_text(opt=None):
        if opt == "blocks":
            return [
                (50, 100, 200, 150, "Left column paragraph one", 0, 0),
                (50, 200, 220, 250, "Left column paragraph two", 1, 0),
                (350, 100, 500, 150, "Right column paragraph one", 2, 0),
                (350, 200, 520, 250, "Right column paragraph two", 3, 0)
            ]
        return "Left column paragraph one\nLeft column paragraph two\nRight column paragraph one\nRight column paragraph two"
    page_mock.get_text.side_effect = mock_get_text
    
    doc_mock.__len__.return_value = 1
    doc_mock.__getitem__.return_value = page_mock
    doc_mock.is_encrypted = False
    
    # Mock fitz.open
    monkeypatch.setattr(fitz, "open", lambda *args, **kwargs: doc_mock)
    
    # Mock pdfplumber.open
    plumber_doc_mock = MagicMock()
    plumber_page_mock = MagicMock()
    plumber_page_mock.width = 600
    plumber_page_mock.height = 800
    
    left_crop_mock = MagicMock()
    left_crop_mock.extract_text.return_value = "Left column paragraph one\nLeft column paragraph two"
    
    right_crop_mock = MagicMock()
    right_crop_mock.extract_text.return_value = "Right column paragraph one\nRight column paragraph two"
    
    # pdfplumber page within_bbox crops
    def mock_within_bbox(bbox):
        # bbox is (x0, y0, x1, y1)
        if bbox[2] == 300: # left half
            return left_crop_mock
        return right_crop_mock
        
    plumber_page_mock.within_bbox.side_effect = mock_within_bbox
    plumber_page_mock.extract_tables.return_value = [] # no tables in this test
    
    plumber_doc_mock.pages = [plumber_page_mock]
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: plumber_doc_mock)
    
    # Parse PDF pages
    pages, ocr_triggered = parse_pdf_pages(b"%PDF-1.4 mock contents")
    
    assert len(pages) == 1
    assert pages[0]["was_multi_column"] is True
    assert pages[0]["had_tables"] is False
    assert "Left column" in pages[0]["text"]
    assert "Right column" in pages[0]["text"]


def test_pdf_parsing_with_table(monkeypatch):
    import fitz
    import pdfplumber
    
    doc_mock = MagicMock()
    page_mock = MagicMock()
    page_mock.rect.width = 600
    # No multi-column blocks
    def mock_get_text(opt=None):
        if opt == "blocks":
            return [
                (50, 100, 550, 150, "Some general description text", 0, 0)
            ]
        return "Some general description text"
    page_mock.get_text.side_effect = mock_get_text
    doc_mock.__len__.return_value = 1
    doc_mock.__getitem__.return_value = page_mock
    doc_mock.is_encrypted = False
    
    monkeypatch.setattr(fitz, "open", lambda *args, **kwargs: doc_mock)
    
    plumber_doc_mock = MagicMock()
    plumber_page_mock = MagicMock()
    plumber_page_mock.width = 600
    plumber_page_mock.height = 800
    
    # Return 1 table: 2x2 structure
    plumber_page_mock.extract_tables.return_value = [
        [
            ["Name", "Count"],
            ["App", "10"]
        ]
    ]
    
    plumber_doc_mock.pages = [plumber_page_mock]
    monkeypatch.setattr(pdfplumber, "open", lambda *args, **kwargs: plumber_doc_mock)
    
    # Parse PDF pages
    pages, ocr_triggered = parse_pdf_pages(b"%PDF-1.4 mock contents")
    
    assert len(pages) == 1
    assert pages[0]["was_multi_column"] is False
    assert pages[0]["had_tables"] is True
    # Verify flattened natural language table text is in page's standalone tables list rather than merged text
    assert len(pages[0].get("tables", [])) == 1
    assert "Table 1:" in pages[0]["tables"][0]
    assert "Row 1: Name is App, Count is 10" in pages[0]["tables"][0]

    # Run chunker on the parsed page data
    chunks = chunk_document_pages(pages)
    
    # General text chunk + table chunk = 2 chunks
    assert len(chunks) == 2
    # Verify text chunk
    assert chunks[0]["text"] == "Some general description text"
    assert chunks[0].get("is_table_chunk") is False
    # Verify table chunk
    assert "Table 1:" in chunks[1]["text"]
    assert chunks[1].get("is_table_chunk") is True


# =========================================================================
# Unit Tests: Ownership Verification
# =========================================================================
def test_ownership_verification_allows_owner():
    # Setup mock conversation in DB
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        session_id=None,
        title="Owner's Conversation"
    )
    
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = conv
    
    # Authorized access should pass and return conversation object
    res = conversation_service.verify_conversation_ownership(
        db=db_mock,
        conv_id=conv.id,
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        session_id=None
    )
    assert res == conv

def test_ownership_verification_denies_non_owner():
    # Setup mock conversation in DB
    conv = Conversation(
        id=uuid.uuid4(),
        user_id=uuid.UUID("5f2ca46c-4064-44ee-be69-cb261ea57365"),
        session_id=None,
        title="Owner's Conversation"
    )
    
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = conv
    
    # Non-owner request should fail with ForbiddenException (403)
    with pytest.raises(ForbiddenException):
        conversation_service.verify_conversation_ownership(
            db=db_mock,
            conv_id=conv.id,
            user_id=uuid.UUID("99999999-4064-44ee-be69-cb261ea57365"), # different user ID
            session_id=None
        )


# =========================================================================
# Unit Tests: Embedding Consistency Check
# =========================================================================
def test_embedding_model_consistency_mismatch(db, monkeypatch):
    from app.services.chat_service import chat_service
    from app.models.document import Document
    
    doc = Document(
        id=uuid.uuid4(),
        filename="report.pdf",
        page_count=1,
        embedding_model="text-embedding-3-small", # Document indexed with OpenAI
        is_deleted=False
    )
    db.add(doc)
    db.commit()
    
    # Mock embedding provider to return a different active local model name
    from app.services.embedding_service import embedding_service
    monkeypatch.setattr(embedding_service, "get_embedding_model_info", lambda *args, **kwargs: "all-MiniLM-L6-v2")
    
    with pytest.raises(EmbeddingModelMismatchException):
        # Triggering generate_chat_stream should fail with model mismatch exception
        generator = chat_service.generate_chat_stream(
            db=db,
            document_id=doc.id,
            conversation_id=None,
            question="What is this?",
            request_id=uuid.uuid4(),
            user_id=None,
            session_id="guest-session-123"
        )
        # Consume generator to run the synchronous checks
        next(generator)




# =========================================================================
# Unit Tests: Title Truncation / Auto-titling
# =========================================================================
def test_title_truncation_auto_titling():
    question_long = "This is a very long question query about SaaS layouts and RAG design pipelines"
    question_short = "What is RAG?"
    
    title_long = question_long[:37] + "..." if len(question_long) > 40 else question_long
    title_short = question_short[:37] + "..." if len(question_short) > 40 else question_short
    
    assert len(title_long) <= 40
    assert title_long.endswith("...")
    assert title_short == "What is RAG?"


def test_ollama_provider(monkeypatch):
    from app.services.llm_providers.ollama_provider import OllamaProvider
    from app.services.llm_provider import get_llm_provider
    from app.core.config import settings
    
    # 1. Test factory resolution
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    provider = get_llm_provider()
    assert isinstance(provider, OllamaProvider)
    
    # 2. Test generate_stream output parsing
    class MockResponse:
        def __init__(self):
            self.status_code = 200
        def raise_for_status(self):
            pass
        def iter_lines(self):
            yield b'{"message": {"content": "Hello "}, "done": false}'
            yield b'{"message": {"content": "world!"}, "done": true, "prompt_eval_count": 10, "eval_count": 5}'
            
    class MockContextManager:
        def __enter__(self):
            return MockResponse()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    import httpx
    monkeypatch.setattr(httpx, "stream", lambda *args, **kwargs: MockContextManager())
    
    chunks = list(provider.generate_stream("hello", "sys", 0.0, 10))
    assert len(chunks) == 3
    assert chunks[0] == {"type": "token", "token": "Hello "}
    assert chunks[1] == {"type": "token", "token": "world!"}
    assert chunks[2] == {"type": "usage", "input_tokens": 10, "output_tokens": 5, "cost": 0.0}


def test_rag_caching_and_invalidation(db, monkeypatch):
    from app.services.chat_service import chat_service, rag_response_cache
    from app.models.document import Document
    from app.services.embedding_service import embedding_service
    from app.services.vector_store_service import vector_store_service
    from app.services.document_service import document_service
    import app.services.chat_service
    
    # 1. Setup mock document in DB
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="cached_report.pdf",
        page_count=2,
        embedding_model="all-MiniLM-L6-v2",
        is_deleted=False
    )
    db.add(doc)
    db.commit()
    
    # Clear any previous cached values for this doc
    rag_response_cache.pop(str(doc_id), None)
    
    # 2. Mock embedding, vector, and LLM services
    monkeypatch.setattr(embedding_service, "get_embedding_model_info", lambda *args, **kwargs: "all-MiniLM-L6-v2")
    monkeypatch.setattr(embedding_service, "generate_embeddings", lambda texts, *args, **kwargs: [[0.1] * 384])
    monkeypatch.setattr(embedding_service, "generate_query_embedding", lambda text, *args, **kwargs: [0.1] * 384)
    
    similar_mock = [
        {"id": f"{doc_id}_chunk_0", "text": "This is cached context chunk 1", "page_number": 1, "chunk_index": 0},
        {"id": f"{doc_id}_chunk_1", "text": "This is cached context chunk 2", "page_number": 2, "chunk_index": 1}
    ]
    monkeypatch.setattr(vector_store_service, "query_similar_chunks", lambda *args, **kwargs: similar_mock)
    similar_hybrid_mock = [
        {"chunk_text": "This is cached context chunk 1", "text": "This is cached context chunk 1", "page_number": 1, "chunk_index": 0, "fused_score": 1.0},
        {"chunk_text": "This is cached context chunk 2", "text": "This is cached context chunk 2", "page_number": 2, "chunk_index": 1, "fused_score": 0.9}
    ]
    monkeypatch.setattr(vector_store_service, "query_hybrid", lambda *args, **kwargs: similar_hybrid_mock)
    
    from app.services.reranker_service import reranker_service
    monkeypatch.setattr(reranker_service, "rerank_chunks", lambda question, candidate_chunks, top_n=5: [{**c, "rerank_score": 1.0} for c in candidate_chunks[:top_n]])
    
    # Mock LLM provider to stream tokens
    llm_call_count = 0
    class MockLLMProvider:
        def generate_stream(self, prompt, system_prompt, temperature, max_tokens, *args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            yield {"type": "token", "token": "Cached "}
            yield {"type": "token", "token": "answer"}
            yield {"type": "usage", "input_tokens": 10, "output_tokens": 5, "cost": 0.0}
            
    monkeypatch.setattr(app.services.chat_service, "get_llm_provider", lambda: MockLLMProvider())
    
    # 3. First call: Cache Miss
    req_id_1 = uuid.uuid4()
    generator = chat_service.generate_chat_stream(
        db=db,
        document_id=doc_id,
        conversation_id=None,
        question="What is cache?",
        request_id=req_id_1,
        user_id=None,
        session_id="guest-session-456"
    )
    res_1 = list(generator)
    assert llm_call_count == 1
    
    # Verify cached output is populated
    doc_id_str = str(doc_id)
    assert doc_id_str in rag_response_cache
    assert len(rag_response_cache[doc_id_str]) == 1
    
    # 4. Second call (same question, same doc): Cache Hit
    req_id_2 = uuid.uuid4()
    generator2 = chat_service.generate_chat_stream(
        db=db,
        document_id=doc_id,
        conversation_id=None,
        question="What is cache?",
        request_id=req_id_2,
        user_id=None,
        session_id="guest-session-456"
    )
    res_2 = list(generator2)
    # LLM provider call count should STILL be 1 (because cache was hit!)
    assert llm_call_count == 1
    
    # 5. Invalidation via document soft-delete
    monkeypatch.setattr(vector_store_service, "delete_document_collection", lambda *args, **kwargs: True)
    document_service.delete_document(db, doc_id)
    
    # The cache entries for this doc_id must now be cleared
    assert doc_id_str not in rag_response_cache
    
    # Restore document's is_deleted state so generate_chat_stream can fetch it
    doc.is_deleted = False
    db.commit()
    
    # 6. Third call: Cache Miss (since cache was cleared)
    req_id_3 = uuid.uuid4()
    generator3 = chat_service.generate_chat_stream(
        db=db,
        document_id=doc_id,
        conversation_id=None,
        question="What is cache?",
        request_id=req_id_3,
        user_id=None,
        session_id="guest-session-456"
    )
    res_3 = list(generator3)
    # LLM provider should be called again, so call count becomes 2!
    assert llm_call_count == 2


def test_pdf_parsing_scanned_ocr_multilingual(monkeypatch):
    import fitz
    import pytesseract
    
    doc_mock = MagicMock()
    page_mock = MagicMock()
    # Scanned PDF: page has no text, but has images/drawings
    page_mock.get_text.return_value = ""
    # Add content visuals (images)
    page_mock.get_images.return_value = ["mock_img_ref"]
    page_mock.get_drawings.return_value = []
    page_mock.rect.width = 600
    
    doc_mock.__len__.return_value = 1
    doc_mock.__getitem__.return_value = page_mock
    doc_mock.is_encrypted = False
    
    # Mock PyMuPDF open
    monkeypatch.setattr(fitz, "open", lambda *args, **kwargs: doc_mock)
    
    # Mock pdf2image.convert_from_bytes where it is used
    import app.services.pdf_parser_service
    monkeypatch.setattr(app.services.pdf_parser_service, "convert_from_bytes", lambda *args, **kwargs: ["mock_image_obj"])
    
    # Mock pytesseract.image_to_string to return mock Hindi OCR text
    hindi_text = "यह एक हिंदी दस्तावेज है।" # "This is a Hindi document."
    def mock_image_to_string(image, lang=None):
        assert lang == "eng+hin+spa+fra+deu"
        return hindi_text
    
    monkeypatch.setattr(pytesseract, "image_to_string", mock_image_to_string)
    
    # Run parsing
    pages, ocr_triggered = parse_pdf_pages(b"%PDF-1.4 mock scanned doc")
    
    assert len(pages) == 1
    assert ocr_triggered is True
    assert pages[0]["text"] == hindi_text
    
    # Also verify that langdetect is called and detected correctly on the document upload service
    # Mock database Session and Repository functions
    db_mock = MagicMock()
    file_mock = MagicMock()
    file_mock.filename = "scanned_hindi.pdf"
    file_mock.file.read.return_value = b"%PDF-1.4 mock scanned doc"
    
    # Mock create_document where it is used
    import app.services.document_service
    created_doc = MagicMock()
    created_doc.id = uuid.uuid4()
    def mock_create_document(*args, **kwargs):
        created_doc.detected_language = kwargs.get("detected_language")
        return created_doc
    monkeypatch.setattr(app.services.document_service, "create_document", mock_create_document)
    
    # Mock embedding and vector store
    from app.services.embedding_service import embedding_service
    from app.services.vector_store_service import vector_store_service
    monkeypatch.setattr(embedding_service, "get_embedding_model_info", lambda *args, **kwargs: "all-MiniLM-L6-v2")
    monkeypatch.setattr(embedding_service, "generate_embeddings", lambda texts, *args, **kwargs: [[0.1]*384])
    monkeypatch.setattr(vector_store_service, "store_document_chunks", lambda *args, **kwargs: "col_name")
    
    res = document_service.process_pdf_upload(
        db=db_mock,
        file=file_mock,
        content_length=1000,
        current_user=None,
        session_id="guest-session-123"
    )
    
    # Language should be detected as Hindi ("hi")
    assert created_doc.detected_language == "hi"


def test_embedding_model_granular_mismatch(db, monkeypatch):
    from app.services.chat_service import chat_service
    from app.models.document import Document
    
    # Document indexed with base English model
    doc = Document(
        id=uuid.uuid4(),
        filename="english_base.pdf",
        page_count=1,
        embedding_model="local-english-base",
        detected_language="en",
        is_deleted=False
    )
    db.add(doc)
    db.commit()
    
    # Active model configuration is set to large English model
    from app.services.embedding_service import embedding_service
    # Mock settings / method to return "local-english-large" for English
    monkeypatch.setattr(embedding_service, "get_embedding_model_info", lambda lang=None: "local-english-large")
    
    # Triggering generate_chat_stream should fail with EmbeddingModelMismatchException
    with pytest.raises(EmbeddingModelMismatchException) as exc_info:
        generator = chat_service.generate_chat_stream(
            db=db,
            document_id=doc.id,
            conversation_id=None,
            question="What is this?",
            request_id=uuid.uuid4(),
            user_id=None,
            session_id="guest-session-123"
        )
        next(generator)
    
    assert "Embedding model mismatch" in str(exc_info.value)


def test_query_hybrid_rrf_and_bm25(monkeypatch):
    from app.services.vector_store_service import vector_store_service, VectorStoreService
    
    # Restore the original query_hybrid method to override the autouse mock
    monkeypatch.setattr(vector_store_service, "query_hybrid", lambda *args, **kwargs: VectorStoreService.query_hybrid(vector_store_service, *args, **kwargs))
    
    # Mock ChromaDB client and collection methods
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [["doc1_chunk_1", "doc1_chunk_0"]],
        "documents": [["Chunk one text content", "Chunk zero text content"]],
        "metadatas": [[{"page_number": 1, "chunk_index": 1}, {"page_number": 1, "chunk_index": 0}]],
        "distances": [[0.1, 0.2]]
    }
    mock_collection.get.return_value = {
        "ids": ["doc1_chunk_0", "doc1_chunk_1"],
        "documents": ["Chunk zero text content", "Chunk one text content"],
        "metadatas": [{"page_number": 1, "chunk_index": 0}, {"page_number": 1, "chunk_index": 1}]
    }
    
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    
    monkeypatch.setattr(vector_store_service, "_get_client", lambda: mock_client)
    
    # Query with query_text that matches chunk_zero more (BM25)
    query_text = "zero"
    query_emb = [0.1] * 384
    
    results = vector_store_service.query_hybrid(
        query_text=query_text,
        query_embedding=query_emb,
        collection_id=uuid.uuid4(),
        vector_top_k=2,
        bm25_top_k=2
    )
    
    # Check that both chunks are returned and RRF has run
    assert len(results) == 2
    # Verify shape of the results
    assert "chunk_text" in results[0]
    assert "fused_score" in results[0]
    assert "page_number" in results[0]
    assert "chunk_index" in results[0]


def test_rerank_chunks_sorting(monkeypatch):
    from app.services.reranker_service import reranker_service, RerankerService
    
    # Restore the original rerank_chunks method to override the autouse mock
    monkeypatch.setattr(reranker_service, "rerank_chunks", lambda *args, **kwargs: RerankerService.rerank_chunks(reranker_service, *args, **kwargs))
    
    # Mock CrossEncoder class and its predict method
    mock_model = MagicMock()
    # Let's say model.predict returns scores: 0.1 for first chunk, 0.9 for second chunk
    mock_model.predict.return_value = [0.1, 0.9]
    
    # Bypass loading CrossEncoder by returning our mock_model
    monkeypatch.setattr(reranker_service, "_get_model", lambda: mock_model)
    
    # Candidates
    candidates = [
        {"chunk_text": "Chunk one", "text": "Chunk one", "fused_score": 0.5},
        {"chunk_text": "Chunk two", "text": "Chunk two", "fused_score": 0.4}
    ]
    
    results = reranker_service.rerank_chunks(
        question="test question",
        candidate_chunks=candidates,
        top_n=2
    )
    
    # Verify that predict was called with the correct pairs
    mock_model.predict.assert_called_once_with([
        ["test question", "Chunk one"],
        ["test question", "Chunk two"]
    ])
    
    # Verify that results are sorted by rerank_score descending (so Chunk two should be first with score 0.9)
    assert len(results) == 2
    assert results[0]["chunk_text"] == "Chunk two"
    assert results[0]["rerank_score"] == 0.9
    assert results[1]["chunk_text"] == "Chunk one"
    assert results[1]["rerank_score"] == 0.1


def test_rerank_confidence_threshold_trips(db, monkeypatch):
    from app.services.chat_service import chat_service
    from app.models.document import Document
    import app.services.chat_service
    from app.services.embedding_service import embedding_service
    from app.services.vector_store_service import vector_store_service
    
    # 1. Setup mock document in DB
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        filename="test_confidence.pdf",
        page_count=1,
        embedding_model="all-MiniLM-L6-v2",
        is_deleted=False
    )
    db.add(doc)
    db.commit()
    
    # 2. Mock embedding, vector store, and reranker services
    monkeypatch.setattr(embedding_service, "get_embedding_model_info", lambda *args, **kwargs: "all-MiniLM-L6-v2")
    monkeypatch.setattr(embedding_service, "generate_query_embedding", lambda *args, **kwargs: [0.1] * 384)
    
    similar_hybrid_mock = [
        {"chunk_text": "Chunk text", "text": "Chunk text", "page_number": 1, "chunk_index": 0, "fused_score": 1.0}
    ]
    monkeypatch.setattr(vector_store_service, "query_hybrid", lambda *args, **kwargs: similar_hybrid_mock)
    
    # Reranker returns chunks with score below configured threshold
    from app.services.reranker_service import reranker_service
    from app.core.config import settings
    monkeypatch.setattr(
        reranker_service, 
        "rerank_chunks", 
        lambda question, candidate_chunks, top_n=5: [{**c, "rerank_score": settings.MIN_RERANK_CONFIDENCE - 5.0} for c in candidate_chunks[:top_n]]
    )
    
    # Mock LLM provider to verify it is NOT called
    llm_call_count = 0
    class MockLLMProvider:
        def generate_stream(self, prompt, system_prompt, temperature, max_tokens, *args, **kwargs):
            nonlocal llm_call_count
            llm_call_count += 1
            yield {"type": "token", "token": "Should not happen"}
            
    monkeypatch.setattr(app.services.chat_service, "get_llm_provider", lambda: MockLLMProvider())
    
    # Call chat stream
    generator = chat_service.generate_chat_stream(
        db=db,
        document_id=doc_id,
        conversation_id=None,
        question="Where is the gold?",
        request_id=uuid.uuid4(),
        user_id=None,
        session_id="guest-session-789"
    )
    
    response_chunks = list(generator)
    
    # Assert LLM was never invoked
    assert llm_call_count == 0
    
    # Parse output tokens to check if the fallback was streamed
    import json
    tokens = []
    citations_packet = None
    for chunk_str in response_chunks:
        data = json.loads(chunk_str)
        if "token" in data:
            tokens.append(data["token"])
        elif "citations" in data:
            citations_packet = data
            
    full_response = "".join(tokens).strip()
    assert "I could not find relevant information in the document to answer this question." in full_response
    assert citations_packet is not None
    assert citations_packet["citations"] == []


def test_ollama_runtime_connection_failure(monkeypatch):
    import httpx
    from app.services.llm_providers.ollama_provider import OllamaProvider
    from app.core.exceptions import OllamaUnavailableException

    # Mock httpx.stream to raise a ConnectError
    def mock_httpx_stream(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "stream", mock_httpx_stream)

    provider = OllamaProvider()
    
    with pytest.raises(OllamaUnavailableException) as excinfo:
        list(provider.generate_stream(
            prompt="Hello",
            system_prompt="Be concise",
            temperature=0.0,
            max_tokens=100
        ))

    assert excinfo.value.status_code == 503
    assert "The local AI model (Ollama) is not running" in excinfo.value.message


def test_chat_service_ollama_unavailable_stream_chunk(monkeypatch):
    import uuid
    import json
    from unittest.mock import MagicMock
    from app.models.document import Document
    from app.services.chat_service import chat_service
    from app.services.vector_store_service import vector_store_service
    from app.core.config import settings
    
    doc_id = uuid.uuid4()
    mock_doc = Document(
        id=doc_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
        filename="test_ollama_err.pdf",
        page_count=1,
        chroma_collection_id="col_test_ollama_err",
        embedding_model="local-english-base",
        is_deleted=False
    )
    
    from app.models.message import Message

    def mock_query(model):
        query_mock = MagicMock()
        if model == Document:
            query_mock.filter.return_value.first.return_value = mock_doc
        elif model == Message:
            query_mock.filter.return_value.first.return_value = None
        return query_mock

    mock_db = MagicMock()
    mock_db.query = mock_query

    # Mock settings
    monkeypatch.setattr(settings, "LLM_PROVIDER", "ollama")
    # Make sure we pass the rerank confidence threshold check
    similar_hybrid_mock = [
        {"chunk_text": "Chunk text", "text": "Chunk text", "page_number": 1, "chunk_index": 0, "fused_score": 1.0}
    ]
    monkeypatch.setattr(vector_store_service, "query_hybrid", lambda *args, **kwargs: similar_hybrid_mock)
    
    from app.services.reranker_service import reranker_service
    monkeypatch.setattr(
        reranker_service, 
        "rerank_chunks", 
        lambda question, candidate_chunks, top_n=5: [{**c, "rerank_score": 1.0} for c in candidate_chunks[:top_n]]
    )

    # Mock OllamaProvider to raise ConnectError
    import httpx
    def mock_httpx_stream(*args, **kwargs):
        raise httpx.ConnectError("Ollama offline")
    monkeypatch.setattr(httpx, "stream", mock_httpx_stream)

    # Call chat stream
    generator = chat_service.generate_chat_stream(
        db=mock_db,
        document_id=doc_id,
        conversation_id=None,
        question="What is the pricing?",
        request_id=uuid.uuid4(),
        user_id=None,
        session_id="guest-session-789"
    )
    
    response_chunks = list(generator)
    
    error_packet = None
    for chunk_str in response_chunks:
        data = json.loads(chunk_str)
        if "error" in data:
            error_packet = data
            break
            
    assert error_packet is not None
    assert "The local AI model (Ollama) is not running" in error_packet["error"]




# =========================================================================
# Unit Tests: Header/Footer Repeating-Line Stripping (pdf_parser_service)
# =========================================================================
from app.services.pdf_parser_service import strip_repeating_header_footer_lines


def test_header_footer_stripping_removes_boilerplate():
    """
    Synthetic 5-page document where every page has the same header ("Confidential")
    and footer ("Page N") at its top/bottom margins.
    Both lines must be stripped from all pages; mid-page content must remain intact.

    Page structure (margin_lines=2):
      [TOP MARGIN]    Line 1: "Confidential"            ← boilerplate header
                      Line 2: "Section heading"          ← non-repeating, in margin zone BUT
                                                           not boilerplate because it differs per page
      [MID CONTENT]   Lines 3-6: unique content per page ← safely outside margin zone
      [BOTTOM MARGIN] Line N-1: "Summary line"           ← non-repeating, in margin zone
                      Line N: "Page N"                   ← boilerplate footer (digit-normalized)
    """
    pages = [
        {
            "page_number": i,
            "text": (
                f"Confidential\n"
                f"Section {i}: Introduction\n"
                f"This paragraph discusses topic A in detail for page {i}.\n"
                f"The analysis presented here is unique to section {i}.\n"
                f"Further discussion of subtopic {i}a follows below.\n"
                f"Additional notes for page {i} appear in this line.\n"
                f"End of main body for section {i}.\n"
                f"Page {i}"
            ),
            "char_count": 0,
        }
        for i in range(1, 6)  # 5 pages
    ]

    result = strip_repeating_header_footer_lines(pages, threshold=0.60, margin_lines=2)

    for page in result:
        # Header boilerplate stripped
        assert "Confidential" not in page["text"], (
            f"'Confidential' header should have been stripped from page {page['page_number']}"
        )
        # Footer boilerplate stripped (page number varies but normalizes to same pattern)
        assert not any(
            line.strip().lower().startswith("page")
            for line in page["text"].splitlines()
        ), f"'Page N' footer should have been stripped from page {page['page_number']}"
        # Real mid-page content preserved (unique per page, falls outside margin zone)
        pn = page['page_number']
        assert f"This paragraph discusses topic A in detail for page {pn}." in page["text"], (
            f"Mid-page content should be preserved on page {pn}"
        )
        assert f"The analysis presented here is unique to section {pn}." in page["text"], (
            f"Mid-page content should be preserved on page {pn}"
        )


def test_header_footer_stripping_preserves_mid_page_repeating_content():
    """
    A recurring important term in the MIDDLE of the page should never be stripped,
    even if it appears on every page — only margin lines are candidates.
    """
    pages = [
        {
            "page_number": i,
            "text": f"Confidential\nThis document discusses RAG.\nRAG is important.\nConfidential",
            "char_count": 0,
        }
        for i in range(1, 5)  # 4 pages
    ]

    result = strip_repeating_header_footer_lines(pages, threshold=0.60, margin_lines=1)

    for page in result:
        # Mid-page "RAG is important." must still be present
        assert "RAG is important." in page["text"]
        # "This document discusses RAG." is a second line, not in margin-1 → kept
        assert "This document discusses RAG." in page["text"]


def test_header_footer_stripping_noop_for_single_page():
    """
    Single-page documents cannot have repeating headers/footers across pages.
    The function must return the data unchanged without errors.
    """
    pages = [
        {
            "page_number": 1,
            "text": "Confidential\nSome content.\nPage 1",
            "char_count": 0,
        }
    ]

    result = strip_repeating_header_footer_lines(pages, threshold=0.60, margin_lines=2)

    # Nothing should be stripped \u2014 no cross-page comparison possible
    assert "Confidential" in result[0]["text"]
    assert "Page 1" in result[0]["text"]


def test_header_footer_stripping_handles_changing_page_numbers():
    """
    'Page 1', 'Page 2', 'Page 3' all normalize to the same boilerplate pattern
    (digits are stripped before comparison). All three should be detected and removed.

    Page structure (margin_lines=2):
      [TOP MARGIN]    Line 1: "My Report Title"   ← repeating boilerplate header
                      Line 2: "Subtitle here"      ← non-repeating section title
      [MID CONTENT]   Lines 3-5: unique content    ← safely outside margin zone
      [BOTTOM MARGIN] Line 6: "Footnote text"      ← non-repeating
                      Line 7: "Page N"             ← repeating footer (digit-normalized match)
    """
    pages = [
        {
            "page_number": i,
            "text": (
                f"My Report Title\n"
                f"Chapter {i}: Overview\n"
                f"Content of page {i} goes here in the main body text.\n"
                f"Additional unique details for chapter {i} are described here.\n"
                f"This line also contains unique information for section {i}.\n"
                f"Closing remark for chapter {i}.\n"
                f"Page {i}"
            ),
            "char_count": 0,
        }
        for i in range(1, 4)  # 3 pages
    ]

    result = strip_repeating_header_footer_lines(pages, threshold=0.60, margin_lines=2)

    for page in result:
        # "My Report Title" header stripped
        assert "My Report Title" not in page["text"]
        # "Page N" footer stripped despite changing number
        assert not any(
            line.strip().lower().startswith("page")
            for line in page["text"].splitlines()
        )
        # Core mid-page content preserved (unique per page, outside margin zone)
        pn = page['page_number']
        assert f"Content of page {pn} goes here in the main body text." in page["text"], (
            f"Mid-page content should be preserved on page {pn}"
        )


def test_header_footer_stripping_below_threshold_not_stripped():
    """
    A line that appears in the margin on only 1 out of 5 pages (20%, below 60% threshold)
    must NOT be stripped.
    """
    pages = [
        {
            "page_number": 1,
            "text": "UNIQUE_HEADER_ONLY_PAGE_ONE\nContent on page 1.\nCommon Footer",
            "char_count": 0,
        },
        *[
            {
                "page_number": i,
                "text": f"Normal Header\nContent on page {i}.\nCommon Footer",
                "char_count": 0,
            }
            for i in range(2, 6)
        ],
    ]

    result = strip_repeating_header_footer_lines(pages, threshold=0.60, margin_lines=1)

    # UNIQUE_HEADER_ONLY_PAGE_ONE appears on 1/5 pages (20%) — below threshold, must survive
    assert "UNIQUE_HEADER_ONLY_PAGE_ONE" in result[0]["text"]
    # Common Footer appears on 5/5 pages (100%) — above threshold, must be stripped
    for page in result:
        assert "Common Footer" not in page["text"]


# =========================================================================
# Unit Tests: BM25 Persistent Index (vector_store_service)
# =========================================================================

def test_bm25_index_persisted_on_store(monkeypatch, tmp_path):
    """
    store_document_chunks() must build and persist a BM25 pickle file to disk
    immediately after ChromaDB indexing — not defer it to query time.
    """
    from app.services.vector_store_service import VectorStoreService
    from app.core.config import settings

    svc = VectorStoreService()

    # Override BM25 index directory to a temporary path
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BM25_INDEX_SUBDIR", "bm25_indexes")

    # Mock ChromaDB client so no real DB is touched
    mock_collection = MagicMock()
    mock_client = MagicMock()
    mock_client.create_collection.return_value = mock_collection
    monkeypatch.setattr(svc, "_get_client", lambda: mock_client)

    doc_id = uuid.uuid4()
    chunks = [
        {"chunk_index": 0, "page_number": 1, "text": "Alpha content chunk here"},
        {"chunk_index": 1, "page_number": 1, "text": "Beta content chunk here"},
    ]
    embeddings = [[0.1] * 10, [0.2] * 10]

    svc.store_document_chunks(doc_id, chunks, embeddings)

    # Verify the BM25 pickle file was written to disk
    expected_path = tmp_path / "bm25_indexes" / f"{doc_id}.pkl"
    assert expected_path.exists(), (
        f"BM25 pickle file should have been created at {expected_path} after store_document_chunks()"
    )

    # Verify the file is a valid pickle of a BM25Okapi object
    import pickle
    from rank_bm25 import BM25Okapi
    with open(expected_path, "rb") as f:
        loaded = pickle.load(f)
    assert isinstance(loaded, BM25Okapi), "Persisted file should be a BM25Okapi instance"


def test_bm25_index_loaded_from_cache_on_second_query(monkeypatch, tmp_path):
    """
    The second call to query_hybrid() for the same document must use the in-process
    cache — _load_bm25_index_from_disk() should NOT be called a second time.
    """
    from app.services.vector_store_service import VectorStoreService
    from app.core.config import settings

    svc = VectorStoreService()

    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BM25_INDEX_SUBDIR", "bm25_indexes")
    monkeypatch.setattr(settings, "LARGE_DOC_CHUNK_THRESHOLD", 500)

    # Build and persist a real BM25 index first (simulates prior store_document_chunks call)
    from rank_bm25 import BM25Okapi
    import pickle
    doc_id = uuid.uuid4()
    docs = ["alpha content", "beta content"]
    bm25_obj = BM25Okapi([d.lower().split() for d in docs])
    index_dir = tmp_path / "bm25_indexes"
    index_dir.mkdir(parents=True)
    with open(index_dir / f"{doc_id}.pkl", "wb") as f:
        pickle.dump(bm25_obj, f)

    # Mock ChromaDB collection.get() to return the same docs
    mock_collection = MagicMock()
    mock_collection.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]]
    }
    mock_collection.get.return_value = {
        "ids": [f"{doc_id}_chunk_0", f"{doc_id}_chunk_1"],
        "documents": docs,
        "metadatas": [{"page_number": 1, "chunk_index": 0}, {"page_number": 1, "chunk_index": 1}]
    }
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(svc, "_get_client", lambda: mock_client)

    # Spy on disk load to count how many times it's called
    disk_load_calls = []
    original_load = svc._load_bm25_index_from_disk
    def spy_load(cid):
        disk_load_calls.append(cid)
        return original_load(cid)
    monkeypatch.setattr(svc, "_load_bm25_index_from_disk", spy_load)

    query_emb = [0.1] * 10

    # First call: cache miss → disk load
    svc.query_hybrid(query_text="alpha", query_embedding=query_emb, collection_id=doc_id)
    assert len(disk_load_calls) == 1, "First query should load from disk exactly once"

    # Second call: cache hit → disk load must NOT happen again
    svc.query_hybrid(query_text="beta", query_embedding=query_emb, collection_id=doc_id)
    assert len(disk_load_calls) == 1, (
        "Second query should use in-process cache — disk load must not be called again"
    )


def test_bm25_index_deleted_on_document_deletion(monkeypatch, tmp_path):
    """
    delete_document_collection() must delete the persisted BM25 pickle file from disk
    AND evict the in-process cache entry — no orphaned index files should remain.
    """
    from app.services.vector_store_service import VectorStoreService
    from app.core.config import settings
    from rank_bm25 import BM25Okapi
    import pickle

    svc = VectorStoreService()
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BM25_INDEX_SUBDIR", "bm25_indexes")

    doc_id = uuid.uuid4()

    # Create a fake BM25 pickle file
    index_dir = tmp_path / "bm25_indexes"
    index_dir.mkdir(parents=True)
    pkl_path = index_dir / f"{doc_id}.pkl"
    bm25_obj = BM25Okapi([["sample", "chunk"]])
    with open(pkl_path, "wb") as f:
        pickle.dump(bm25_obj, f)

    # Also prime the in-process cache
    svc._bm25_cache[str(doc_id)] = bm25_obj

    # Mock ChromaDB client
    mock_client = MagicMock()
    monkeypatch.setattr(svc, "_get_client", lambda: mock_client)

    # Delete the document
    svc.delete_document_collection(doc_id)

    # Verify: BM25 file gone from disk
    assert not pkl_path.exists(), (
        "BM25 pickle file should have been deleted from disk after document deletion"
    )
    # Verify: cache entry evicted
    assert str(doc_id) not in svc._bm25_cache, (
        "BM25 in-process cache entry should have been evicted after document deletion"
    )


def test_dynamic_topk_scaling_large_doc(monkeypatch, tmp_path):
    """
    When a document's chunk count >= LARGE_DOC_CHUNK_THRESHOLD, query_hybrid() must
    use LARGE_DOC_VECTOR_TOP_K and LARGE_DOC_BM25_TOP_K instead of the caller-supplied
    default values, ensuring large documents have wider retrieval breadth.
    """
    from app.services.vector_store_service import VectorStoreService
    from app.core.config import settings
    from rank_bm25 import BM25Okapi
    import pickle

    svc = VectorStoreService()
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "BM25_INDEX_SUBDIR", "bm25_indexes")
    monkeypatch.setattr(settings, "LARGE_DOC_CHUNK_THRESHOLD", 5)   # low threshold for test
    monkeypatch.setattr(settings, "LARGE_DOC_VECTOR_TOP_K", 20)
    monkeypatch.setattr(settings, "LARGE_DOC_BM25_TOP_K", 20)

    doc_id = uuid.uuid4()

    # Synthetic "large document": 6 chunks (>= threshold of 5)
    large_docs = [f"chunk content number {i} with unique tokens" for i in range(6)]
    large_metadatas = [{"page_number": 1, "chunk_index": i} for i in range(6)]
    large_ids = [f"{doc_id}_chunk_{i}" for i in range(6)]

    # Persist a BM25 index for this doc
    index_dir = tmp_path / "bm25_indexes"
    index_dir.mkdir(parents=True)
    bm25_obj = BM25Okapi([d.lower().split() for d in large_docs])
    with open(index_dir / f"{doc_id}.pkl", "wb") as f:
        pickle.dump(bm25_obj, f)

    # Track how many results vector search is asked for
    vector_top_k_used = []
    original_vector = svc._query_vector_similarity
    def spy_vector(query_embedding, doc_id, top_k):
        vector_top_k_used.append(top_k)
        # Return empty list — we only care about top_k value here
        return []
    monkeypatch.setattr(svc, "_query_vector_similarity", spy_vector)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "ids": large_ids,
        "documents": large_docs,
        "metadatas": large_metadatas
    }
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    monkeypatch.setattr(svc, "_get_client", lambda: mock_client)

    # Call with default top_k=15 (below the scaled value of 20)
    svc.query_hybrid(
        query_text="chunk content",
        query_embedding=[0.1] * 10,
        collection_id=doc_id,
        vector_top_k=15,
        bm25_top_k=15
    )

    # The effective vector_top_k should have been scaled up to LARGE_DOC_VECTOR_TOP_K (20)
    assert len(vector_top_k_used) == 1
    assert vector_top_k_used[0] == 20, (
        f"Expected large-doc scaled top_k=20, but _query_vector_similarity was called with top_k={vector_top_k_used[0]}"
    )


def test_query_rewriting_with_pronouns(monkeypatch):
    """
    Verifies that rewrite_query_with_context resolves references in the question
    based on the conversation history when pronouns exist, and does NOT trigger LLM
    or rewrite when no pronouns exist.
    """
    from app.services.chat_service import chat_service
    from app.models.message import Message

    # 1. First scenario: No pronoun in follow-up question
    history_no_pronoun = [
        Message(role="user", content="How many layers does the encoder have?"),
        Message(role="assistant", content="It has 6 layers.")
    ]
    # No LLM provider should be instantiated since pronoun pre-check skips it
    provider_instantiated = False
    def mock_get_provider_fail():
        nonlocal provider_instantiated
        provider_instantiated = True
        raise RuntimeError("LLM provider should not be called!")
    
    monkeypatch.setattr("app.services.chat_service.get_llm_provider", mock_get_provider_fail)
    
    q_no_pronoun = "Why is the encoder fast?"
    res_no_pronoun = chat_service.rewrite_query_with_context(q_no_pronoun, history_no_pronoun)
    
    assert res_no_pronoun == q_no_pronoun
    assert not provider_instantiated

    # 2. Second scenario: Pronoun present, expects rewrite
    history_with_pronoun = [
        Message(role="user", content="How many layers does the encoder have?"),
        Message(role="assistant", content="The encoder has 6 layers.")
    ]
    
    class MockLLMProvider:
        def generate_stream(self, prompt, system_prompt, temperature, max_tokens, *args, **kwargs):
            assert "How many layers does the encoder have?" in prompt
            assert "Why does it need that many?" in prompt
            assert temperature == 0.0
            assert max_tokens == 50
            yield {"type": "token", "token": "Why does the encoder need 6 layers?"}

    monkeypatch.setattr("app.services.chat_service.get_llm_provider", lambda: MockLLMProvider())

    q_with_pronoun = "Why does it need that many?"
    res_with_pronoun = chat_service.rewrite_query_with_context(q_with_pronoun, history_with_pronoun)

    assert res_with_pronoun == "Why does the encoder need 6 layers?"


def test_chunk_quality_filtering(monkeypatch):
    """
    Verifies that is_low_quality_chunk correctly filters chunks based on length,
    density, and document centroid outlier checks.
    """
    from app.services.embedding_service import is_low_quality_chunk
    from app.core.config import settings

    # Reset/override configurations to deterministic values for test
    monkeypatch.setattr(settings, "MIN_CHUNK_CHAR_LENGTH", 20)
    monkeypatch.setattr(settings, "MIN_ALPHA_DENSITY", 0.25)
    monkeypatch.setattr(settings, "OUTLIER_SIMILARITY_THRESHOLD", 0.40)
    monkeypatch.setattr(settings, "STRICT_OUTLIER_FILTERING", True)

    # 1. Step 1: Reject chunk below MIN_CHUNK_CHAR_LENGTH (20 chars)
    short_chunk = "Page 7"
    assert is_low_quality_chunk(short_chunk) is True

    # 2. Step 2: Reject chunk with low alphabetic density (ratio < 0.25)
    garbage_dashes = "-------------------------"  # 25 characters, 0 letters
    assert is_low_quality_chunk(garbage_dashes) is True

    # 3. Step 3: Outlier check (similarity < 0.40)
    # Cosine similarity between [1, 0] and [0, 1] is 0.0 (below 0.40 threshold)
    outlier_chunk = "Semantic outlier prose text here"
    assert is_low_quality_chunk(
        outlier_chunk,
        embedding=[1.0, 0.0],
        centroid=[0.0, 1.0],
        is_table_chunk=False
    ) is True

    # 4. Outlier check should NOT apply to table chunks (is_table_chunk=True)
    table_chunk = "Table row Count: 10, Name: App"
    assert is_low_quality_chunk(
        table_chunk,
        embedding=[1.0, 0.0],
        centroid=[0.0, 1.0],
        is_table_chunk=True
    ) is False

    # 5. Valid chunk should pass all checks
    valid_chunk = "This is a perfectly valid sentence with plenty of text characters."
    assert is_low_quality_chunk(
        valid_chunk,
        embedding=[1.0, 0.0],
        centroid=[1.0, 0.0],
        is_table_chunk=False
    ) is False


def test_query_expansion_paraphrasing_and_rrf_merging(monkeypatch):
    """
    Verifies that expand_query yields alternative phrasings, and query retrieval uses
    both the original and paraphrases, merging them correctly with deduplication.
    """
    from app.services.chat_service import chat_service
    from app.core.config import settings

    # Reset/override configurations to deterministic values for test
    monkeypatch.setattr(settings, "ENABLE_QUERY_EXPANSION", True)
    monkeypatch.setattr(settings, "LARGE_DOC_CHUNK_THRESHOLD", 5) # low threshold for test

    # Mock the LLM provider to return fixed paraphrases for our query
    class MockLLMProvider:
        def generate_stream(self, prompt, system_prompt, temperature, max_tokens, *args, **kwargs):
            assert "paraphrased versions" in prompt or "alternative phrasings" in prompt
            assert temperature == 0.0
            assert max_tokens == 80
            yield {"type": "token", "token": "First alternative question?\nSecond alternative phrasing?"}

    monkeypatch.setattr("app.services.chat_service.get_llm_provider", lambda: MockLLMProvider())

    # Call expand_query and verify the parsing & cleaning logic
    paraphrases = chat_service.expand_query("Original question text?")
    assert len(paraphrases) == 2
    assert paraphrases[0] == "First alternative question?"
    assert paraphrases[1] == "Second alternative phrasing?"

    # Verify that query expansion gets correctly skipped when chunk count < threshold
    # We will mock the ChromaDB collection count to return 3 chunks (< 5 threshold)
    mock_collection = MagicMock()
    mock_collection.count.return_value = 3
    mock_client = MagicMock()
    mock_client.get_collection.return_value = mock_collection
    
    from app.services.vector_store_service import vector_store_service
    monkeypatch.setattr(vector_store_service, "_get_client", lambda: mock_client)

    # Spy on expand_query call to ensure it's bypassed
    expand_called = False
    original_expand = chat_service.expand_query
    def spy_expand(question):
        nonlocal expand_called
        expand_called = True
        return original_expand(question)
    monkeypatch.setattr(chat_service, "expand_query", spy_expand)

    # Mock Document and Conversation objects
    mock_doc = MagicMock()
    mock_doc.id = uuid.uuid4()
    mock_doc.detected_language = "en"
    mock_doc.embedding_model = "local-english-base"

    from app.models.document import Document
    from app.models.conversation import Conversation
    from app.models.message import Message

    def mock_query(model):
        query_mock = MagicMock()
        if model == Document:
            query_mock.filter.return_value.first.return_value = mock_doc
        elif model == Conversation:
            # Avoid querying Conversation database table
            query_mock.filter.return_value.first.return_value = None
        elif model == Message:
            # Return None for idempotency check, and empty list for history
            query_mock.filter.return_value.first.return_value = None
            query_mock.filter.return_value.order_by.return_value.all.return_value = []
        return query_mock

    mock_db = MagicMock()
    mock_db.query = mock_query

    # Mock generate_query_embedding and query_hybrid
    monkeypatch.setattr("app.services.embedding_service.embedding_service.generate_query_embedding", lambda *args, **kwargs: [0.1] * 10)
    
    # Spy on query_hybrid calls
    hybrid_queries_called = []
    def mock_query_hybrid(query_text, query_embedding, collection_id, vector_top_k, bm25_top_k):
        hybrid_queries_called.append(query_text)
        # Return a sample chunk with a fake fused_score
        return [
            {
                "id": "chunk_1",
                "text": "sample text",
                "fused_score": 0.5,
                "page_number": 1,
                "chunk_index": 0
            }
        ]
    monkeypatch.setattr(vector_store_service, "query_hybrid", mock_query_hybrid)

    # 1. Trigger stream generator setup with chunk count < threshold -> NO expansion
    # Call generate_chat_stream to trigger the candidate retrieval logic
    list(chat_service.generate_chat_stream(
        db=mock_db,
        document_id=mock_doc.id,
        conversation_id=None,
        question="Original question?",
        request_id=uuid.uuid4(),
        user_id=None,
        session_id="test_session"
    ))

    assert not expand_called
    assert len(hybrid_queries_called) == 1
    assert hybrid_queries_called[0] == "Original question?"

    # 2. Trigger stream generator setup with chunk count >= threshold -> EXPANSION
    # Reset spies
    expand_called = False
    hybrid_queries_called = []
    mock_collection.count.return_value = 10 # >= 5 threshold

    # Mock rerank to avoid failures down the line
    monkeypatch.setattr("app.services.reranker_service.reranker_service.rerank_chunks", lambda *args, **kwargs: [])

    list(chat_service.generate_chat_stream(
        db=mock_db,
        document_id=mock_doc.id,
        conversation_id=None,
        question="Original question?",
        request_id=uuid.uuid4(),
        user_id=None,
        session_id="test_session"
    ))

    assert expand_called
    # Should have called query_hybrid for original query + 2 paraphrases = 3 queries
    assert len(hybrid_queries_called) == 3
    assert "Original question?" in hybrid_queries_called
    assert "First alternative question?" in hybrid_queries_called
    assert "Second alternative phrasing?" in hybrid_queries_called


def test_first_page_metadata_extraction():
    from app.services.pdf_parser_service import extract_document_metadata
    
    mock_page = MagicMock()
    # Mock PyMuPDF page.get_text("dict") output structure
    mock_page.get_text.return_value = {
        "blocks": [
            {
                "type": 0,
                "bbox": (50, 50, 200, 70),
                "lines": [
                    {
                        "spans": [{"size": 9.0, "text": "arXiv:1234.5678"}]
                    }
                ]
            },
            {
                "type": 0,
                "bbox": (50, 100, 500, 150),
                "lines": [
                    {
                        "spans": [{"size": 24.0, "text": "Synthetic Test Title"}]
                    }
                ]
            },
            {
                "type": 0,
                "bbox": (50, 170, 500, 190),
                "lines": [
                    {
                        "spans": [{"size": 11.0, "text": "Author One* and Author Two"}]
                    }
                ]
            },
            {
                "type": 0,
                "bbox": (50, 200, 500, 220),
                "lines": [
                    {
                        "spans": [{"size": 10.0, "text": "Google Research"}]
                    }
                ]
            },
            {
                "type": 0,
                "bbox": (50, 250, 500, 270),
                "lines": [
                    {
                        "spans": [{"size": 12.0, "text": "ABSTRACT"}]
                    }
                ]
            },
            {
                "type": 0,
                "bbox": (50, 290, 500, 390),
                "lines": [
                    {
                        "spans": [{"size": 10.0, "text": "This is standard paper body text detailing findings."}]
                    }
                ]
            }
        ]
    }

    title, authors = extract_document_metadata(mock_page)
    
    assert title == "Synthetic Test Title"
    assert "Author One* and Author Two" in authors
    assert "Google Research" in authors
    assert "ABSTRACT" not in authors
    assert "findings" not in authors


def test_metadata_question_detector():
    from app.services.chat_service import detect_metadata_question
    
    # Author query patterns
    assert detect_metadata_question("who wrote this paper?") == "authors"
    assert detect_metadata_question("Who are the authors of this paper?") == "authors"
    assert detect_metadata_question("Tell me the author names") == "authors"
    assert detect_metadata_question("who wrote this") == "authors"
    
    # Title query patterns
    assert detect_metadata_question("what is the title of the paper?") == "title"
    assert detect_metadata_question("what is the paper called?") == "title"
    assert detect_metadata_question("what is the name of this paper?") == "title"
    assert detect_metadata_question("paper title") == "title"
    
    # Non-matching patterns
    assert detect_metadata_question("what is the abstract about?") is None
    assert detect_metadata_question("what is the main idea?") is None
    assert detect_metadata_question("who is mentioned on page 4?") is None




