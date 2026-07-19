import uuid
import logging
import re
import os
from sqlalchemy.orm import Session
from fastapi import UploadFile
from app.models import User
from app.core.config import settings
# OLD: imports without VectorStoreContaminationException, kept for reference
# from app.core.exceptions import InvalidFileTypeException, FileTooLargeException, CorruptedFileException
from app.core.exceptions import (
    InvalidFileTypeException,
    FileTooLargeException,
    CorruptedFileException,
    VectorStoreContaminationException
)

from app.services.pdf_parser_service import parse_pdf_pages
from app.services.chunker_service import chunk_document_pages
from app.services.embedding_service import embedding_service
from app.services.vector_store_service import vector_store_service
from app.repositories import create_document, soft_delete_document

logger = logging.getLogger("app.services.document")

# 10MB limit
MAX_FILE_SIZE = 10 * 1024 * 1024

def sanitize_filename(filename: str) -> str:
    """
    Sanitize the user-supplied filename.
    Strips path separators and replaces special characters with underscores.
    """
    # Remove directory path parts if present
    base = os.path.basename(filename)
    # Allow only letters, numbers, dot, dash, and underscore
    sanitized = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return sanitized[:255]

class DocumentService:
    """
    Handles PDF validation, text parsing/extraction, and DB storage.
    """
    def process_pdf_upload(
        self,
        db: Session,
        file: UploadFile,
        content_length: int | None,
        current_user: User | None,
        session_id: str | None
    ) -> dict:
        # 1. Verify file size using HTTP Content-Length header if available
        if content_length is not None and content_length > MAX_FILE_SIZE:
            raise FileTooLargeException(
                f"File size exceeds maximum limit of 10MB (Header check: {content_length} bytes)."
            )

        # 2. Read file bytes and verify actual size in memory
        try:
            file_bytes = file.file.read()
        except Exception as read_err:
            raise CorruptedFileException(f"Failed to read uploaded file: {str(read_err)}")

        actual_size = len(file_bytes)
        if actual_size == 0:
            raise CorruptedFileException("Uploaded file is empty (0 bytes).")
        if actual_size > MAX_FILE_SIZE:
            raise FileTooLargeException(
                f"File size exceeds maximum limit of 10MB (Actual check: {actual_size} bytes)."
            )

        # 3. Verify magic bytes (%PDF- signature) to ensure it is a valid PDF
        if len(file_bytes) < 4 or file_bytes[:4] != b"%PDF":
            raise InvalidFileTypeException("Invalid file format signature. Only valid PDF files are supported.")

        # 4. Sanitize file name
        filename_raw = file.filename or "uploaded_document.pdf"
        sanitized_name = sanitize_filename(filename_raw)

        # 5. Extract text page-by-page (PyMuPDF + Tesseract fallback)
        try:
            pages_data, ocr_triggered = parse_pdf_pages(file_bytes)
        except Exception as parse_err:
            # Propagate custom exception classes raised by the parser
            if hasattr(parse_err, "status_code"):
                raise parse_err
            raise CorruptedFileException(f"Could not parse PDF document structure: {str(parse_err)}")

        # 6. Chunk text page-by-page
        chunks = chunk_document_pages(pages_data)

        # 8. Detect document language using langdetect (runs after parsing/OCR text is extracted)
        full_text = "\n".join([page["text"] for page in pages_data])
        detected_lang = None
        if full_text.strip():
            try:
                import langdetect
                detected_lang = langdetect.detect(full_text)
                logger.info(f"Detected document language: '{detected_lang}'")
            except Exception as lang_err:
                logger.warning(f"Language detection failed: {lang_err}. Defaulting to 'en'.")
                detected_lang = "en"
        else:
            detected_lang = "en"

        # 7. Generate embeddings (using primary model or fallback sentence-transformers) with quality filtering
        # Apply cheap text-based filters before embedding generation (length and information density)
        pre_filtered_chunks = []
        dropped_length = 0
        dropped_density = 0

        from app.services.embedding_service import is_low_quality_chunk

        # OLD: cheap text-based filters loop without title page chunk bypass, kept for reference
        # for c in chunks:
        #     text = c["text"]
        #     if len(text) < settings.MIN_CHUNK_CHAR_LENGTH:
        #         dropped_length += 1
        #         continue
        #     import re
        #     alpha_chars = re.findall(r'[a-zA-Z\u00c0-\u017f\u0400-\u04ff\u0900-\u097f]', text)
        #     ratio = len(alpha_chars) / len(text) if text else 0.0
        #     if ratio < settings.MIN_ALPHA_DENSITY:
        #         dropped_density += 1
        #         continue
        #     pre_filtered_chunks.append(c)

        for c in chunks:
            text = c["text"]
            is_table = c.get("is_table_chunk", False)
            is_title = c.get("is_title_page_chunk", False)
            
            # Exempt special chunks from cheap filters
            if is_table or is_title:
                pre_filtered_chunks.append(c)
                continue

            # 1. Length check
            if len(text) < settings.MIN_CHUNK_CHAR_LENGTH:
                dropped_length += 1
                continue
            # 2. Information density check (ratio of alphabetic characters to total length)
            import re
            alpha_chars = re.findall(r'[a-zA-Z\u00c0-\u017f\u0400-\u04ff\u0900-\u097f]', text)
            ratio = len(alpha_chars) / len(text) if text else 0.0
            if ratio < settings.MIN_ALPHA_DENSITY:
                dropped_density += 1
                continue
            
            pre_filtered_chunks.append(c)

        if dropped_length > 0 or dropped_density > 0:
            logger.info(
                f"Filtered out low-quality chunks for document: dropped {dropped_length} chunks due to length "
                f"(< {settings.MIN_CHUNK_CHAR_LENGTH} chars), dropped {dropped_density} chunks due to low alphabetic "
                f"density (< {settings.MIN_ALPHA_DENSITY})."
            )

        # Generate embeddings for the text-filtered chunks
        active_model = embedding_service.get_embedding_model_info(lang=detected_lang)
        chunk_texts = [c["text"] for c in pre_filtered_chunks]
        raw_embeddings = embedding_service.generate_embeddings(chunk_texts, lang=detected_lang)

        # Compute centroid embedding to perform semantic outlier checks
        centroid = None
        if raw_embeddings:
            num_dimensions = len(raw_embeddings[0])
            num_embeddings = len(raw_embeddings)
            centroid = [0.0] * num_dimensions
            for emb in raw_embeddings:
                for d in range(num_dimensions):
                    centroid[d] += emb[d]
            for d in range(num_dimensions):
                centroid[d] /= num_embeddings

        # Apply embedding-based outlier check
        final_chunks = []
        final_embeddings = []
        dropped_outliers = 0

        # OLD: outlier checks without is_title_page_chunk skip, kept for reference
        # for c, emb in zip(pre_filtered_chunks, raw_embeddings):
        #     is_table = c.get("is_table_chunk", False)
        #     if is_low_quality_chunk(c["text"], embedding=emb, centroid=centroid, is_table_chunk=is_table):
        #         dropped_outliers += 1
        #         continue
        #     final_chunks.append(c)
        #     final_embeddings.append(emb)

        for c, emb in zip(pre_filtered_chunks, raw_embeddings):
            is_table = c.get("is_table_chunk", False)
            is_title = c.get("is_title_page_chunk", False)
            if is_low_quality_chunk(c["text"], embedding=emb, centroid=centroid, is_table_chunk=is_table, is_title_page_chunk=is_title):
                dropped_outliers += 1
                continue
            final_chunks.append(c)
            final_embeddings.append(emb)

        if dropped_outliers > 0:
            logger.info(f"Filtered out {dropped_outliers} outlier chunks under STRICT_OUTLIER_FILTERING.")

        # Reassign to the filtered lists so they are stored and returned correctly
        chunks = final_chunks
        embeddings = final_embeddings

        # 9. Write database row via repository layer (initially without chroma_collection_id)
        user_id = current_user.id if current_user else None
        doc_session_id = session_id if current_user is None else None

        # OLD: created document without passing language detection/title/authors parameters — replaced below
        # doc_record = create_document(
        #     db=db,
        #     filename=sanitized_name,
        #     page_count=len(pages_data),
        #     ocr_triggered=ocr_triggered,
        #     chroma_collection_id=None,
        #     user_id=user_id,
        #     session_id=doc_session_id,
        #     embedding_model=active_model,
        #     detected_language=detected_lang
        # )

        extracted_title = pages_data[0].get("extracted_title") if pages_data else None
        extracted_authors = pages_data[0].get("extracted_authors") if pages_data else None

        doc_record = create_document(
            db=db,
            filename=sanitized_name,
            page_count=len(pages_data),
            ocr_triggered=ocr_triggered,
            chroma_collection_id=None,
            user_id=user_id,
            session_id=doc_session_id,
            embedding_model=active_model,
            detected_language=detected_lang,
            extracted_title=extracted_title,
            extracted_authors=extracted_authors
        )

        # 10. Generate deterministic collection name from created document ID
        chroma_collection_id = vector_store_service.get_collection_name(doc_record.id)
        doc_record.chroma_collection_id = chroma_collection_id
        db.commit()
        db.refresh(doc_record)

        # Save original PDF file to disk
        try:
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            file_path = os.path.join(uploads_dir, f"{doc_record.id}.pdf")
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            logger.info(f"Saved original PDF file to disk at: {file_path}")
        except Exception as save_err:
            logger.error(f"Failed to save original PDF file to disk: {save_err}")
            raise CorruptedFileException(f"Failed to save document file on server: {str(save_err)}")

        # 11. Index chunks and embeddings in ChromaDB
        vector_store_service.store_document_chunks(doc_record.id, chunks, embeddings)

        # Sanity assertion check: immediately query its own collection and verify document_id metadata
        client = vector_store_service._get_client()
        coll_name = vector_store_service.get_collection_name(doc_record.id)
        try:
            collection = client.get_collection(name=coll_name)
            # Fetch all items in the collection
            all_indexed_data = collection.get()
            indexed_metadatas = all_indexed_data.get("metadatas", [])
            for meta in indexed_metadatas:
                chunk_doc_id = meta.get("document_id")
                if chunk_doc_id != str(doc_record.id):
                    logger.error(
                        f"Vector Store Contamination Detected! Expected document_id '{doc_record.id}', "
                        f"but found chunk metadata document_id '{chunk_doc_id}' in collection '{coll_name}'. "
                        f"Full metadata: {meta}"
                    )
                    raise VectorStoreContaminationException(
                        f"Contamination verification failed: chunk with document_id '{chunk_doc_id}' "
                        f"found in collection for document '{doc_record.id}'"
                    )
            logger.info(
                f"Contamination check passed: verified {len(indexed_metadatas)} chunks in collection '{coll_name}' "
                f"strictly belong to document '{doc_record.id}'."
            )
        except Exception as err:
            if isinstance(err, VectorStoreContaminationException):
                raise err
            logger.warning(f"Could not perform contamination isolation verification check: {err}")

        logger.info(f"Processed document upload successfully. Document ID: {doc_record.id}")

        # Return exact snake_case values as expected by the frontend's mock endpoints
        return {
            "document_id": doc_record.id,
            "filename": doc_record.filename,
            "page_count": doc_record.page_count,
            "ocr_triggered": doc_record.ocr_triggered
        }

    # OLD: soft deletes PostgreSQL document and hard deletes vector storage only — replaced below to also invalidate cached RAG responses
    # def delete_document(self, db: Session, doc_id: uuid.UUID) -> bool:
    #     """
    #     Soft deletes the document in PostgreSQL database and hard deletes
    #     the vector index collection in ChromaDB.
    #     """
    #     # 1. Soft delete database row
    #     success = soft_delete_document(db, doc_id)
    #     if not success:
    #         return False
    # 
    #     # 2. Hard delete vector collection in ChromaDB
    #     vector_store_service.delete_document_collection(doc_id)
    #     return True

    def delete_document(self, db: Session, doc_id: uuid.UUID) -> bool:
        """
        Soft deletes the document in PostgreSQL database, hard deletes the vector collection in ChromaDB,
        and invalidates cached RAG responses for this document.
        """
        # 1. Soft delete database row
        success = soft_delete_document(db, doc_id)
        if not success:
            return False

        # 2. Hard delete vector collection in ChromaDB
        vector_store_service.delete_document_collection(doc_id)

        # 3. Clear RAG response cache for this document
        try:
            from app.services.chat_service import rag_response_cache
            doc_id_str = str(doc_id)
            if doc_id_str in rag_response_cache:
                rag_response_cache.pop(doc_id_str, None)
                logger.info(f"Cleared RAG response cache for document '{doc_id}'")
        except Exception as cache_err:
            logger.warning(f"Could not clear RAG response cache for document '{doc_id}': {cache_err}")

        # 4. Delete the physical PDF file if it exists
        try:
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
            file_path = os.path.join(uploads_dir, f"{doc_id}.pdf")
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted physical PDF file for document '{doc_id}'")
        except Exception as file_err:
            logger.warning(f"Could not delete physical PDF file for document '{doc_id}': {file_err}")

        return True

# Instantiate singleton service instance
document_service = DocumentService()
