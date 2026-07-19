import logging
import os
import uuid
import pickle
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.exceptions import DocumentNotIndexedException, ExternalServiceException

logger = logging.getLogger("app.services.vector_store")

# Lazy import statement to prevent circular dependencies or PyTorch/Chroma load overhead
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

class VectorStoreService:
    """
    Manages isolated document collection vector storages inside ChromaDB.
    """
    def __init__(self):
        self._client = None
        # In-process LRU cache for loaded BM25 indexes.
        # Structure: { collection_id_str: BM25Okapi }
        # Max size controlled by settings.BM25_CACHE_MAX_SIZE — oldest key evicted when full.
        self._bm25_cache: Dict[str, Any] = {}
        import concurrent.futures
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _get_client(self):
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("chromadb library is not installed in the virtual environment.")
        
        if self._client is None:
            logger.info(f"Initializing persistent ChromaDB client at: '{settings.CHROMA_PERSIST_DIR}'")
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=chromadb.Settings(anonymized_telemetry=False)
            )
        return self._client

    def get_collection_name(self, doc_id: uuid.UUID | str) -> str:
        """
        Generates a deterministic collection name using the MD5 hash of the document ID.
        Avoids file collision across name matches.
        """
        doc_str = str(doc_id)
        return f"col_{hashlib.md5(doc_str.encode('utf-8')).hexdigest()}"

    # -------------------------------------------------------------------------
    # BM25 Persistent Index Helpers
    # -------------------------------------------------------------------------

    def _get_bm25_index_path(self, collection_id: uuid.UUID | str) -> Path:
        """
        Returns the filesystem path for the persisted BM25 index pickle file
        for the given document collection.
        Path: <CHROMA_PERSIST_DIR>/<BM25_INDEX_SUBDIR>/<collection_id>.pkl
        """
        return (
            Path(settings.CHROMA_PERSIST_DIR)
            / settings.BM25_INDEX_SUBDIR
            / f"{collection_id}.pkl"
        )

    def _save_bm25_index(self, collection_id: uuid.UUID | str, bm25_obj: Any) -> None:
        """
        Persists a BM25Okapi object to disk as a pickle file.
        Creates the bm25_indexes/ subfolder if it does not yet exist.
        """
        path = self._get_bm25_index_path(collection_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump(bm25_obj, f)
            logger.info(
                f"BM25 index persisted to disk for collection '{collection_id}': {path}"
            )
        except Exception as e:
            # Non-fatal: log a warning but do not fail document indexing.
            logger.warning(
                f"Failed to persist BM25 index for collection '{collection_id}': {e}. "
                f"Query-time rebuild will be used as fallback."
            )

    def _load_bm25_index_from_disk(self, collection_id: uuid.UUID | str) -> Optional[Any]:
        """
        Loads a persisted BM25Okapi object from disk.
        Returns None if the file does not exist (triggers fallback rebuild).
        """
        path = self._get_bm25_index_path(collection_id)
        if not path.exists():
            return None
        try:
            with open(path, "rb") as f:
                bm25_obj = pickle.load(f)
            logger.info(
                f"BM25 index loaded from disk for collection '{collection_id}'."
            )
            return bm25_obj
        except Exception as e:
            logger.warning(
                f"Failed to load BM25 index from disk for collection '{collection_id}': {e}. "
                f"Will rebuild from ChromaDB."
            )
            return None

    def _get_bm25_index_cached(
        self,
        collection_id: uuid.UUID | str,
        documents: Optional[List[str]] = None
    ) -> Any:
        """
        Returns the BM25Okapi index for a collection, using a 3-level lookup:
          1. In-process LRU dict cache (fastest — avoids disk I/O entirely)
          2. Disk pickle file (fast — persisted at indexing time)
          3. Rebuild from provided documents list (fallback — logs a warning)

        If documents is None and neither cache nor disk has the index,
        raises a RuntimeError because there is nothing to build from.
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            raise RuntimeError("rank-bm25 library is not installed in the virtual environment.")

        cid_str = str(collection_id)

        # Level 1: in-process cache hit
        if cid_str in self._bm25_cache:
            return self._bm25_cache[cid_str]

        # Level 2: disk load
        bm25_obj = self._load_bm25_index_from_disk(collection_id)
        if bm25_obj is not None:
            self._bm25_cache_put(cid_str, bm25_obj)
            return bm25_obj

        # Level 3: rebuild from documents (fallback, logs warning)
        if documents is None:
            raise RuntimeError(
                f"BM25 index for collection '{collection_id}' not found on disk or in cache, "
                f"and no documents were provided for fallback rebuild."
            )
        logger.warning(
            f"BM25 index not found on disk for collection '{collection_id}'. "
            f"Rebuilding in-memory from {len(documents)} chunks — this is the fallback path "
            f"and should not happen in normal operation. Was the document re-indexed without "
            f"going through store_document_chunks()?"
        )
        tokenized_corpus = [doc.lower().split() for doc in documents]
        bm25_obj = BM25Okapi(tokenized_corpus)
        self._bm25_cache_put(cid_str, bm25_obj)
        return bm25_obj

    def _bm25_cache_put(self, cid_str: str, bm25_obj: Any) -> None:
        """
        Inserts a BM25 index into the in-process cache.
        Evicts the oldest entry when BM25_CACHE_MAX_SIZE is exceeded (simple LRU via insertion order).
        """
        if cid_str in self._bm25_cache:
            # Re-insert to refresh order
            del self._bm25_cache[cid_str]
        elif len(self._bm25_cache) >= settings.BM25_CACHE_MAX_SIZE:
            # Evict oldest (first inserted) key
            oldest_key = next(iter(self._bm25_cache))
            del self._bm25_cache[oldest_key]
            logger.info(
                f"BM25 in-process cache full (max {settings.BM25_CACHE_MAX_SIZE}). "
                f"Evicted oldest entry: '{oldest_key}'."
            )
        self._bm25_cache[cid_str] = bm25_obj

# OLD: stored document chunks with only page_number, chunk_index, and source_document_id metadata — replaced below to add was_multi_column and had_tables flags to ChromaDB metadata
#     def store_document_chunks(
#         self,
#         doc_id: uuid.UUID,
#         chunks: List[Dict[str, Any]],
#         embeddings: List[List[float]]
#     ) -> str:
#         """
#         Creates a dedicated collection for a document and adds chunk strings, embeddings, and page metadata.
#         """
#         if not chunks:
#             return ""
#
#         client = self._get_client()
#         collection_name = self.get_collection_name(doc_id)
#         logger.info(f"Storing chunks in ChromaDB collection: '{collection_name}' for doc ID '{doc_id}'")
#
#         try:
#             # Delete collection if it already exists to guarantee a clean override
#             try:
#                 client.delete_collection(name=collection_name)
#             except Exception:
#                 pass
#
#             collection = client.create_collection(
#                 name=collection_name,
#                 metadata={"hnsw:space": "cosine"}
#             )
#
#             ids = []
#             documents = []
#             metadatas = []
#
#             for chunk, emb in zip(chunks, embeddings):
#                 chunk_idx = chunk["chunk_index"]
#                 ids.append(f"{doc_id}_chunk_{chunk_idx}")
#                 documents.append(chunk["text"])
#                 metadatas.append({
#                     "page_number": chunk["page_number"],
#                     "chunk_index": chunk_idx,
#                     "source_document_id": str(doc_id)
#                 })
#
#             collection.add(
#                 ids=ids,
#                 documents=documents,
#                 embeddings=embeddings,
#                 metadatas=metadatas
#             )
#             logger.info(f"Successfully indexed {len(chunks)} chunks in collection: '{collection_name}'")
#             return collection_name
#
#         except Exception as e:
#             logger.error(f"Failed to write chunks to ChromaDB collection '{collection_name}': {e}")
#             raise ExternalServiceException(f"Failed to write vectors to the database: {str(e)}")

    def store_document_chunks(
        self,
        doc_id: uuid.UUID,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]]
    ) -> str:
        """
        Creates a dedicated collection for a document and adds chunk strings, embeddings,
        and page metadata (including columns and tables flags).

        After ChromaDB indexing, also builds and persists the BM25 index to disk
        (under CHROMA_PERSIST_DIR/bm25_indexes/<doc_id>.pkl) so that query_hybrid()
        does not need to rebuild it from scratch on every search call.
        """
        if not chunks:
            return ""

        client = self._get_client()
        collection_name = self.get_collection_name(doc_id)
        chunk_count = len(chunks)

        # Log chunk count at INFO so it's easy to see which documents trigger
        # the large-doc scaling path versus the default path.
        is_large_doc = chunk_count >= settings.LARGE_DOC_CHUNK_THRESHOLD
        scaling_path = "large-doc" if is_large_doc else "default"
        logger.info(
            f"Indexing {chunk_count} chunks for doc '{doc_id}' in ChromaDB collection "
            f"'{collection_name}' — retrieval scaling path: [{scaling_path}] "
            f"(threshold: {settings.LARGE_DOC_CHUNK_THRESHOLD} chunks)."
        )

        try:
            # Delete collection if it already exists to guarantee a clean override
            try:
                client.delete_collection(name=collection_name)
            except Exception:
                pass

            collection = client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            # OLD: ChromaDB stored and indexed only child-chunk-level text and
            # embeddings — replaced/extended below to also store parent chunk text
            # (unembedded, just as retrievable metadata/a separate lookup) alongside
            # child chunk embeddings.
            # Design Decision: We chose to store the full parent chunk text directly as metadata in
            # each child chunk's ChromaDB entry because it is simple, requires no secondary storage
            # file/database setup, and scales natively with ChromaDB.
            ids = []
            documents = []
            metadatas = []

            for chunk, emb in zip(chunks, embeddings):
                chunk_idx = chunk["chunk_index"]
                ids.append(f"{doc_id}_chunk_{chunk_idx}")
                documents.append(chunk["text"])
                
                # OLD: chunk metadata layout without document_id or is_title_page_chunk, kept for reference
                # meta = {
                #     "page_number": chunk["page_number"],
                #     "chunk_index": chunk_idx,
                #     "source_document_id": str(doc_id),
                #     "was_multi_column": chunk.get("was_multi_column", False),
                #     "had_tables": chunk.get("had_tables", False),
                #     "is_table_chunk": chunk.get("is_table_chunk", False)
                # }
                
                meta = {
                    "document_id": str(doc_id),
                    "page_number": chunk["page_number"],
                    "chunk_index": chunk_idx,
                    "source_document_id": str(doc_id),
                    "was_multi_column": chunk.get("was_multi_column", False),
                    "had_tables": chunk.get("had_tables", False),
                    "is_table_chunk": chunk.get("is_table_chunk", False),
                    "is_title_page_chunk": chunk.get("is_title_page_chunk", False)
                }

                
                if "parent_chunk_id" in chunk:
                    meta["parent_chunk_id"] = chunk["parent_chunk_id"]
                if "parent_chunk_text" in chunk:
                    meta["parent_chunk_text"] = chunk["parent_chunk_text"]
                if "parent_page_range" in chunk:
                    meta["parent_page_range"] = chunk["parent_page_range"]
                    
                metadatas.append(meta)

            collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(
                f"Successfully indexed {chunk_count} chunks in ChromaDB collection: '{collection_name}'. "
                f"Building and persisting BM25 index now."
            )

            # Build and persist BM25 index immediately after ChromaDB indexing.
            # This is the ONLY place where the BM25 index should be built from scratch —
            # query_hybrid() will load it from disk/cache rather than rebuilding it.
            try:
                from rank_bm25 import BM25Okapi
                tokenized_corpus = [doc.lower().split() for doc in documents]
                bm25_obj = BM25Okapi(tokenized_corpus)
                self._save_bm25_index(doc_id, bm25_obj)
                # Prime the in-process cache so the first query in this session
                # does not incur a disk read either.
                self._bm25_cache_put(str(doc_id), bm25_obj)
            except Exception as bm25_err:
                # Non-fatal: BM25 persist failure must not block document indexing.
                logger.warning(
                    f"BM25 index build/persist failed for doc '{doc_id}': {bm25_err}. "
                    f"Hybrid search will fall back to query-time rebuild."
                )

            return collection_name

        except Exception as e:
            logger.error(f"Failed to write chunks to ChromaDB collection '{collection_name}': {e}")
            raise ExternalServiceException(f"Failed to write vectors to the database: {str(e)}")


    # OLD: query_similar_chunks did pure vector/cosine similarity search only,
    # no keyword-based matching — replaced below with a hybrid approach
    # combining vector search and BM25, fused via Reciprocal Rank Fusion, for
    # better recall on queries with specific keywords/names/numbers that
    # embeddings alone sometimes miss.
    # def query_similar_chunks(
    #     self,
    #     query_embedding: List[float],
    #     doc_id: uuid.UUID,
    #     top_k: int = 5
    # ) -> List[Dict[str, Any]]:
    #     """
    #     Queries similarity matches on a document collection.
    #     Translates cosine distance back to a standard similarity score.
    #     """
    #     client = self._get_client()
    #     collection_name = self.get_collection_name(doc_id)
    #     try:
    #         collection = client.get_collection(name=collection_name)
    #     except Exception:
    #         raise DocumentNotIndexedException(
    #             f"The vector storage collection for document '{doc_id}' is missing or has been deleted."
    #         )
    #     try:
    #         results = collection.query(
    #             query_embeddings=[query_embedding],
    #             n_results=top_k
    #         )
    #         matched_chunks = []
    #         if not results or not results.get("ids") or len(results["ids"][0]) == 0:
    #             return []
    #         ids = results["ids"][0]
    #         docs = results["documents"][0]
    #         metadatas = results["metadatas"][0]
    #         distances = results["distances"][0] if "distances" in results else [0.0] * len(ids)
    #         for cid, doc, meta, dist in zip(ids, docs, metadatas, distances):
    #             matched_chunks.append({
    #                 "id": cid,
    #                 "text": doc,
    #                 "page_number": meta.get("page_number"),
    #                 "chunk_index": meta.get("chunk_index"),
    #                 "source_document_id": meta.get("source_document_id"),
    #                 "similarity_score": 1.0 - dist
    #             })
    #         return matched_chunks
    #     except Exception as e:
    #         logger.error(f"Failed to query ChromaDB collection '{collection_name}': {e}")
    #         raise ExternalServiceException(f"Failed to query vector database search: {str(e)}")

    def query_similar_chunks(
        self,
        query_embedding: List[float],
        doc_id: uuid.UUID | str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Deprecated: use query_hybrid instead. Legacy compatibility wrapper.
        """
        return self._query_vector_similarity(query_embedding, doc_id, top_k)

    def _query_vector_similarity(
        self,
        query_embedding: List[float],
        doc_id: uuid.UUID | str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Internal helper performing pure vector/cosine similarity search.
        """
        client = self._get_client()
        collection_name = self.get_collection_name(doc_id)

        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            raise DocumentNotIndexedException(
                f"The vector storage collection for document '{doc_id}' is missing or has been deleted."
            )

        try:
            # OLD: collection query without document isolation filter, kept for reference
            # results = collection.query(
            #     query_embeddings=[query_embedding],
            #     n_results=top_k
            # )
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where={"document_id": str(doc_id)}
            )

            matched_chunks = []
            if not results or not results.get("ids") or len(results["ids"][0]) == 0:
                return []

            ids = results["ids"][0]
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0] if "distances" in results else [0.0] * len(ids)

            for cid, doc, meta, dist in zip(ids, docs, metadatas, distances):
                matched_chunks.append({
                    "id": cid,
                    "text": doc,
                    "page_number": meta.get("page_number"),
                    "chunk_index": meta.get("chunk_index"),
                    "source_document_id": meta.get("source_document_id"),
                    "similarity_score": 1.0 - dist,
                    "parent_chunk_id": meta.get("parent_chunk_id"),
                    "parent_chunk_text": meta.get("parent_chunk_text"),
                    "parent_page_range": meta.get("parent_page_range"),
                    "is_title_page_chunk": meta.get("is_title_page_chunk", False)
                })

            return matched_chunks

        except Exception as e:
            logger.error(f"Failed to query ChromaDB collection '{collection_name}': {e}")
            raise ExternalServiceException(f"Failed to query vector database search: {str(e)}")

    def query_hybrid(
        self,
        query_text: str,
        query_embedding: List[float],
        collection_id: uuid.UUID | str,
        vector_top_k: int = 15,
        bm25_top_k: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Runs vector similarity search AND a BM25 keyword search over the same document's chunks,
        then fuses them via weighted Reciprocal Rank Fusion (RRF).

        BM25 index is loaded from the in-process cache or disk (persisted at indexing time by
        store_document_chunks) — it is never rebuilt from scratch on each query call.

        For large documents (chunk count >= settings.LARGE_DOC_CHUNK_THRESHOLD), retrieval
        breadth is automatically scaled up to LARGE_DOC_VECTOR_TOP_K / LARGE_DOC_BM25_TOP_K
        before reranking narrows results back to FINAL_TOP_N, preventing relevant content
        from being buried outside a fixed-size candidate window.
        """
        # 1. Fetch all chunk texts to determine document size for dynamic top-k scaling.
        client = self._get_client()
        collection_name = self.get_collection_name(collection_id)

        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            raise DocumentNotIndexedException(
                f"The vector storage collection for document '{collection_id}' is missing or has been deleted."
            )

        try:
            # OLD: collection get without document isolation filter, kept for reference
            # all_chunks = collection.get()
            all_chunks = collection.get(where={"document_id": str(collection_id)})
        except Exception as e:
            logger.error(
                f"Failed to retrieve chunk list from collection '{collection_name}': {e}"
            )
            raise ExternalServiceException(f"Failed to retrieve chunks for hybrid search: {str(e)}")


        ids = all_chunks.get("ids", [])
        documents = all_chunks.get("documents", [])
        metadatas = all_chunks.get("metadatas", [])

        if not documents:
            # Empty collection — return empty result set.
            return []

        # 2. Dynamic top-k scaling: increase candidate retrieval breadth for large documents.
        chunk_count = len(documents)
        if chunk_count >= settings.LARGE_DOC_CHUNK_THRESHOLD:
            effective_vector_top_k = max(vector_top_k, settings.LARGE_DOC_VECTOR_TOP_K)
            effective_bm25_top_k = max(bm25_top_k, settings.LARGE_DOC_BM25_TOP_K)
            logger.info(
                f"Large document detected for collection '{collection_id}': {chunk_count} chunks "
                f"(threshold: {settings.LARGE_DOC_CHUNK_THRESHOLD}). Scaling retrieval from "
                f"top-{vector_top_k}/{bm25_top_k} → top-{effective_vector_top_k}/{effective_bm25_top_k}."
            )
        else:
            effective_vector_top_k = vector_top_k
            effective_bm25_top_k = bm25_top_k

        # 3. Parallelized Vector and BM25 search
        # OLD: sequential search logic, kept for reference
        # vector_chunks = self._query_vector_similarity(
        #     query_embedding=query_embedding,
        #     doc_id=collection_id,
        #     top_k=effective_vector_top_k
        # )
        # bm25 = self._get_bm25_index_cached(
        #     collection_id=collection_id,
        #     documents=documents
        # )
        # tokenized_query = query_text.lower().split()
        # scores = bm25.get_scores(tokenized_query)

        def run_vector_search():
            return self._query_vector_similarity(
                query_embedding=query_embedding,
                doc_id=collection_id,
                top_k=effective_vector_top_k
            )

        def run_bm25_search():
            bm25 = self._get_bm25_index_cached(
                collection_id=collection_id,
                documents=documents
            )
            tokenized_query = query_text.lower().split()
            return bm25.get_scores(tokenized_query)

        # Submit tasks concurrently to ThreadPoolExecutor
        future_vector = self._executor.submit(run_vector_search)
        future_bm25 = self._executor.submit(run_bm25_search)

        vector_chunks = future_vector.result()
        scores = future_bm25.result()

        scored_docs = []
        for idx, (cid, doc, meta, score) in enumerate(zip(ids, documents, metadatas, scores)):
            scored_docs.append({
                "id": cid,
                "text": doc,
                "page_number": meta.get("page_number"),
                "chunk_index": meta.get("chunk_index"),
                "source_document_id": meta.get("source_document_id"),
                "bm25_score": score,
                "parent_chunk_id": meta.get("parent_chunk_id"),
                "parent_chunk_text": meta.get("parent_chunk_text"),
                "parent_page_range": meta.get("parent_page_range"),
                "is_title_page_chunk": meta.get("is_title_page_chunk", False)
            })

        # Sort BM25 results descending and slice top K
        ranked_bm25 = sorted(scored_docs, key=lambda x: x["bm25_score"], reverse=True)
        ranked_bm25 = ranked_bm25[:effective_bm25_top_k]

        # 5. Reciprocal Rank Fusion (RRF)
        K_RRF = 60
        
        # Maps from chunk ID to 1-based rank
        vector_ranks = {item["id"]: idx + 1 for idx, item in enumerate(vector_chunks)}
        bm25_ranks = {item["id"]: idx + 1 for idx, item in enumerate(ranked_bm25)}

        # All unique chunk IDs across both searches
        all_chunk_ids = set(vector_ranks.keys()).union(bm25_ranks.keys())

        # Map to quickly fetch metadata
        chunk_metadata = {}
        for item in vector_chunks:
            chunk_metadata[item["id"]] = {
                "chunk_text": item["text"],
                "page_number": item["page_number"],
                "chunk_index": item["chunk_index"],
                "parent_chunk_id": item.get("parent_chunk_id"),
                "parent_chunk_text": item.get("parent_chunk_text"),
                "parent_page_range": item.get("parent_page_range"),
                "is_title_page_chunk": item.get("is_title_page_chunk", False)
            }
        for item in ranked_bm25:
            chunk_metadata[item["id"]] = {
                "chunk_text": item["text"],
                "page_number": item["page_number"],
                "chunk_index": item["chunk_index"],
                "parent_chunk_id": item.get("parent_chunk_id"),
                "parent_chunk_text": item.get("parent_chunk_text"),
                "parent_page_range": item.get("parent_page_range"),
                "is_title_page_chunk": item.get("is_title_page_chunk", False)
            }

        fused_results = []
        for cid in all_chunk_ids:
            vector_rank = vector_ranks.get(cid)
            bm25_rank = bm25_ranks.get(cid)

            vector_contrib = 1.0 / (K_RRF + vector_rank) if vector_rank else 0.0
            bm25_contrib = 1.0 / (K_RRF + bm25_rank) if bm25_rank else 0.0

            # Weighted RRF: vector contributes 0.7, BM25 contributes 0.3
            fused_score = 0.7 * vector_contrib + 0.3 * bm25_contrib

            meta = chunk_metadata[cid]
            fused_results.append({
                "id": cid,
                "chunk_text": meta["chunk_text"],
                "text": meta["chunk_text"],  # compatibility fallback
                "page_number": meta["page_number"],
                "chunk_index": meta["chunk_index"],
                "fused_score": fused_score,
                "parent_chunk_id": meta.get("parent_chunk_id"),
                "parent_chunk_text": meta.get("parent_chunk_text"),
                "parent_page_range": meta.get("parent_page_range"),
                "is_title_page_chunk": meta.get("is_title_page_chunk", False)
            })


        # Sort by fused score descending
        fused_results = sorted(fused_results, key=lambda x: x["fused_score"], reverse=True)
        return fused_results

    def delete_document_collection(self, doc_id: uuid.UUID) -> None:
        """
        Hard deletes the corresponding document collection from the vector database.
        Also removes the persisted BM25 index file from disk and evicts the in-process
        cache entry to prevent orphaned data.
        """
        client = self._get_client()
        collection_name = self.get_collection_name(doc_id)
        logger.info(f"Deleting ChromaDB collection: '{collection_name}' for doc ID '{doc_id}'")
        try:
            client.delete_collection(name=collection_name)
        except Exception as e:
            logger.warning(f"ChromaDB collection deletion skipped or failed: {e}")

        # Delete persisted BM25 index file to prevent orphaned index files.
        bm25_path = self._get_bm25_index_path(doc_id)
        if bm25_path.exists():
            try:
                bm25_path.unlink()
                logger.info(
                    f"Deleted persisted BM25 index for doc '{doc_id}': {bm25_path}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to delete BM25 index file for doc '{doc_id}' at '{bm25_path}': {e}"
                )

        # Evict from in-process cache
        cid_str = str(doc_id)
        if cid_str in self._bm25_cache:
            del self._bm25_cache[cid_str]
            logger.info(f"Evicted BM25 in-process cache entry for doc '{doc_id}'.")

# Instantiate singleton vector store service instance
vector_store_service = VectorStoreService()
