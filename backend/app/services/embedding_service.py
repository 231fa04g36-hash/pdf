import hashlib
import json
import os
import logging
from typing import List
from app.core.config import settings
from app.core.exceptions import ExternalServiceException

logger = logging.getLogger("app.services.embedding")

# Lazy import statement wrappers to handle local environments without full ML package imports on startup
try:
    from openai import OpenAI
    from sentence_transformers import SentenceTransformer
    HAS_ML_DEPENDENCIES = True
except ImportError:
    HAS_ML_DEPENDENCIES = False

class DevEmbeddingCache:
    """
    Local JSON file cache used during development only to save API token costs and speed up iterations.
    Disabled in production.
    """
    def __init__(self):
        # Cache file resides in the backend workspace scratch directory
        self.cache_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "scratch", 
            "embedding_cache.json"
        )
        self.cache = {}
        if settings.ENVIRONMENT == "development":
            try:
                os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
                if os.path.exists(self.cache_file):
                    with open(self.cache_file, "r", encoding="utf-8") as f:
                        self.cache = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load development embedding cache file: {e}")

    def get(self, text: str, model_name: str) -> List[float] | None:
        if settings.ENVIRONMENT != "development":
            return None
        key = self._make_key(text, model_name)
        return self.cache.get(key)

    def set(self, text: str, model_name: str, embedding: List[float]) -> None:
        if settings.ENVIRONMENT != "development":
            return
        key = self._make_key(text, model_name)
        self.cache[key] = embedding
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not save development embedding cache file: {e}")

    def _make_key(self, text: str, model_name: str) -> str:
        raw_val = f"{model_name}:{text}"
        return hashlib.md5(raw_val.encode("utf-8")).hexdigest()


class EmbeddingService:
    """
    Generates text chunk embeddings using OpenAI API or sentence-transformers fallback.
    """
    def __init__(self):
        self._local_models = {}
        self._cache = DevEmbeddingCache()

        # Startup resource check for large embedding tier on CPU-only hardware
        if settings.EMBEDDING_PROVIDER == "local" and getattr(settings, "EMBEDDING_MODEL_TIER", "base").lower() == "large":
            # Code comment: Startup check to warn about CPU indexing slowness for 'large' tier.
            # This is a one-time cost per document upload, so slowness here does NOT affect chat response speed.
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning(
                        "WARNING: EMBEDDING_MODEL_TIER is set to 'large', but no GPU is detected (torch.cuda.is_available() == False). "
                        "The 'bge-large' model will run meaningfully slower on CPU-only hardware. If indexing feels too slow, "
                        "please switch EMBEDDING_MODEL_TIER to 'base' in core/config.py. "
                        "Note: This is a one-time indexing cost per document upload, so this slowness does NOT affect chat query response speed."
                    )
            except ImportError:
                logger.warning(
                    "WARNING: EMBEDDING_MODEL_TIER is set to 'large', but torch is not installed. "
                    "If a GPU is not available, 'bge-large' will run meaningfully slower on CPU-only hardware. "
                    "This is a one-time indexing cost per document upload and does NOT affect chat query response speed."
                )

    # OLD: local embedding used a fixed MiniLM-based model (English) or 
    # multilingual-MiniLM (non-English), no accuracy/size tiering. Replaced 
    # below with a configurable base/large tier on top of the existing 
    # language branch from Prompt E.
    # def old_select_local_model(lang: str | None = None) -> str:
    #     if lang and lang != "en":
    #         return "paraphrase-multilingual-MiniLM-L12-v2"
    #     return "all-MiniLM-L6-v2"

    def get_embedding_model_info(self, lang: str | None = None) -> str:
        """
        Retrieves the name of the active model that will be used based on settings provider, key availability, language, and tier settings.
        """
        if settings.EMBEDDING_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            return settings.OPENAI_EMBEDDING_MODEL
        
        # Local provider
        lang_code = lang if lang is not None else "en"
        if lang_code != "en":
            # Non-English + any tier: keep the existing multilingual model from
            # Prompt E unchanged (paraphrase-multilingual-MiniLM-L12-v2) — the
            # bge-large upgrade is English-only for now.
            return "local-multilingual"
        
        # English path
        tier = getattr(settings, "EMBEDDING_MODEL_TIER", "base").lower()
        if tier == "large":
            return "local-english-large"
        else:
            return "local-english-base"

    def _resolve_hf_model_id(self, model_name: str) -> str:
        """
        Resolves the internal model name/column representation to a Hugging Face model ID.
        """
        if model_name == "local-english-base":
            return "BAAI/bge-base-en-v1.5"
        elif model_name == "local-english-large":
            return "BAAI/bge-large-en-v1.5"
        elif model_name == "local-multilingual":
            return "paraphrase-multilingual-MiniLM-L12-v2"
        else:
            # Fallback to the settings configuration model name if name is unrecognized
            return settings.EMBEDDING_MODEL_NAME

    def _get_local_model(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError("sentence-transformers library is not installed in the virtual environment.")

        hf_model_id = self._resolve_hf_model_id(model_name)
        if hf_model_id not in self._local_models:
            logger.info(f"Loading local sentence-transformers model: '{hf_model_id}'")
            self._local_models[hf_model_id] = SentenceTransformer(hf_model_id)
        return self._local_models[hf_model_id]

    # OLD: the local sentence-transformers model loaded lazily on the first 
    # actual embedding call, causing the first upload or query after server 
    # start to be noticeably slower. Replaced below with eager pre-loading at 
    # startup.
    # def get_local_embedding_model(self, model_name: str):
    #     pass
    def pre_load_local_model(self) -> None:
        """
        Eagerly pre-loads the configured sentence-transformers model(s) into memory at application startup.
        """
        if settings.EMBEDDING_PROVIDER == "openai":
            logger.info("Skipping local embedding pre-warming because EMBEDDING_PROVIDER='openai'.")
            return

        model_name = self.get_embedding_model_info(lang="en")
        logger.info(f"Eagerly pre-warming configured local embedding model: '{model_name}'...")
        try:
            self._get_local_model(model_name)
            logger.info("Local embedding model pre-warming completed successfully.")
        except Exception as e:
            logger.error(f"Failed to pre-warm local embedding model: {e}")

    def generate_embeddings(self, texts: List[str], lang: str | None = None) -> List[List[float]]:
        if not texts:
            return []

        # Determine target model depending on provider configuration
        model_name = self.get_embedding_model_info(lang=lang)
        logger.info(f"Generating embeddings for {len(texts)} chunks using: '{model_name}'")

        embeddings = [None] * len(texts)
        missing_indices = []
        missing_texts = []

        # 1. Resolve from local dev cache
        for i, text in enumerate(texts):
            cached = self._cache.get(text, model_name)
            if cached is not None:
                embeddings[i] = cached
            else:
                missing_indices.append(i)
                missing_texts.append(text)

        if not missing_texts:
            return embeddings

        # 2. Call embedding provider for uncached texts
        generated_embeddings = []
        if settings.EMBEDDING_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                try:
                    from openai import OpenAI
                except ImportError:
                    raise RuntimeError("openai SDK is not installed in the virtual environment.")

                # Instantiate client with a strict 10 second timeout constraint
                client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=10.0)
                logger.info(f"Requesting OpenAI Embeddings from model '{model_name}' with 10s timeout...")
                response = client.embeddings.create(
                    input=missing_texts,
                    model=model_name
                )
                generated_embeddings = [data.embedding for data in response.data]
            except Exception as openai_err:
                logger.warning(
                    f"OpenAI embedding generation failed/timed out: {openai_err}. "
                    f"Falling back to local sentence-transformers model."
                )
                # Fallback to local sentence-transformers model
                model_name = self.get_embedding_model_info(lang=lang)
                local_model = self._get_local_model(model_name)
                encoded_np = local_model.encode(missing_texts)
                generated_embeddings = [vector.tolist() for vector in encoded_np]
        else:
            try:
                local_model = self._get_local_model(model_name)
                encoded_np = local_model.encode(missing_texts)
                generated_embeddings = [vector.tolist() for vector in encoded_np]
            except Exception as local_err:
                raise ExternalServiceException(
                    f"Failed to generate local sentence-transformers embeddings: {str(local_err)}"
                )

        # 3. Populate missing slices and update cache
        for idx, text, emb in zip(missing_indices, missing_texts, generated_embeddings):
            embeddings[idx] = emb
            self._cache.set(text, model_name, emb)

        return embeddings

    def generate_query_embedding(self, text: str, lang: str | None = None) -> List[float]:
        """
        Generates embedding for a single text query (e.g. user question).
        Uses single-item encoding rather than batching.
        """
        model_name = self.get_embedding_model_info(lang=lang)
        # 1. Resolve from local dev cache
        cached = self._cache.get(text, model_name)
        if cached is not None:
            return cached

        # 2. Call embedding provider
        if settings.EMBEDDING_PROVIDER == "openai" and settings.OPENAI_API_KEY:
            try:
                try:
                    from openai import OpenAI
                except ImportError:
                    raise RuntimeError("openai SDK is not installed in the virtual environment.")

                client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=10.0)
                response = client.embeddings.create(
                    input=[text],
                    model=model_name
                )
                embedding = response.data[0].embedding
                self._cache.set(text, model_name, embedding)
                return embedding
            except Exception as openai_err:
                logger.warning(
                    f"OpenAI query embedding generation failed/timed out: {openai_err}. "
                    f"Falling back to local sentence-transformers model."
                )
                model_name = self.get_embedding_model_info(lang=lang)

        try:
            local_model = self._get_local_model(model_name)
            # Pass a single string to encode() for single-item embedding
            encoded = local_model.encode(text)
            embedding = encoded.tolist()
            self._cache.set(text, model_name, embedding)
            return embedding
        except Exception as local_err:
            raise ExternalServiceException(
                f"Failed to generate query embedding: {str(local_err)}"
            )

# Instantiate singleton embedding service instance
embedding_service = EmbeddingService()


# OLD: is_low_quality_chunk without is_title_page_chunk support and bypassing, kept for reference
# def is_low_quality_chunk(
#     chunk_text: str,
#     embedding: List[float] = None,
#     centroid: List[float] = None,
#     is_table_chunk: bool = False
# ) -> bool:
#     """
#     Checks if a text chunk is low quality based on text length, alphabetical density,
#     and semantic similarity to the document centroid.
# 
#     Steps:
#       1. Reject chunks below MIN_CHUNK_CHAR_LENGTH.
#       2. Reject chunks with alphabetic density below MIN_ALPHA_DENSITY.
#       3. Flag/reject chunks with similarity to document centroid below OUTLIER_SIMILARITY_THRESHOLD.
#          (bypassed if is_table_chunk=True)
#     """
#     # 1. Text-length check
#     if len(chunk_text) < settings.MIN_CHUNK_CHAR_LENGTH:
#         return True
# 
#     # 2. Low-information-density check
#     import re
#     alpha_chars = re.findall(r'[a-zA-Z\u00c0-\u017f\u0400-\u04ff\u0900-\u097f]', chunk_text)
#     ratio = len(alpha_chars) / len(chunk_text) if chunk_text else 0.0
#     if ratio < settings.MIN_ALPHA_DENSITY:
#         return True
# 
#     # 3. Embedding-based outlier check
#     if not is_table_chunk and embedding is not None and centroid is not None:
#         import math
#         dot_product = sum(a * b for a, b in zip(embedding, centroid))
#         magnitude1 = math.sqrt(sum(a * a for a in embedding))
#         magnitude2 = math.sqrt(sum(b * b for b in centroid))
#         sim = dot_product / (magnitude1 * magnitude2) if magnitude1 and magnitude2 else 0.0
# 
#         if sim < settings.OUTLIER_SIMILARITY_THRESHOLD:
#             logger.warning(
#                 f"Embedding outlier detected (similarity {sim:.4f} < threshold {settings.OUTLIER_SIMILARITY_THRESHOLD}): "
#                 f"{repr(chunk_text[:100])}..."
#             )
#             if settings.STRICT_OUTLIER_FILTERING:
#                 return True
# 
#     return False

def is_low_quality_chunk(
    chunk_text: str,
    embedding: List[float] = None,
    centroid: List[float] = None,
    is_table_chunk: bool = False,
    is_title_page_chunk: bool = False
) -> bool:
    """
    Checks if a text chunk is low quality based on text length, alphabetical density,
    and semantic similarity to the document centroid.

    Bypasses all checks for table chunks and title page chunks.
    """
    if is_table_chunk or is_title_page_chunk:
        return False

    # 1. Text-length check
    if len(chunk_text) < settings.MIN_CHUNK_CHAR_LENGTH:
        return True

    # 2. Low-information-density check
    import re
    alpha_chars = re.findall(r'[a-zA-Z\u00c0-\u017f\u0400-\u04ff\u0900-\u097f]', chunk_text)
    ratio = len(alpha_chars) / len(chunk_text) if chunk_text else 0.0
    if ratio < settings.MIN_ALPHA_DENSITY:
        return True

    # 3. Embedding-based outlier check
    if embedding is not None and centroid is not None:
        import math
        dot_product = sum(a * b for a, b in zip(embedding, centroid))
        magnitude1 = math.sqrt(sum(a * a for a in embedding))
        magnitude2 = math.sqrt(sum(b * b for b in centroid))
        sim = dot_product / (magnitude1 * magnitude2) if magnitude1 and magnitude2 else 0.0

        if sim < settings.OUTLIER_SIMILARITY_THRESHOLD:
            logger.warning(
                f"Embedding outlier detected (similarity {sim:.4f} < threshold {settings.OUTLIER_SIMILARITY_THRESHOLD}): "
                f"{repr(chunk_text[:100])}..."
            )
            if settings.STRICT_OUTLIER_FILTERING:
                return True

    return False

