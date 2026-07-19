import logging
from typing import List, Dict, Any

logger = logging.getLogger("app.services.reranker")

class RerankerService:
    """
    Reranks candidate document chunks using a CrossEncoder model for higher precision.
    """
    def __init__(self):
        self._model = None

    def _get_model(self):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise RuntimeError("sentence-transformers library is not installed in the virtual environment.")

        if self._model is None:
            model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
            logger.info(f"Loading CrossEncoder model: '{model_name}'")
            self._model = CrossEncoder(model_name)
        return self._model

    def rerank_chunks(self, question: str, candidate_chunks: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Takes candidate chunks, scores (question, chunk_text) pairs with CrossEncoder,
        sorts descending by score, and returns the top_n.
        """
        if not candidate_chunks:
            return []

        model = self._get_model()

        # Prepare inputs: list of [question, chunk_text]
        pairs = []
        for chunk in candidate_chunks:
            # Respect both keys 'chunk_text' and 'text'
            text = chunk.get("chunk_text") or chunk.get("text", "")
            pairs.append([question, text])

        # Score pairs
        scores = model.predict(pairs)

        # Attach scores to candidates
        scored_candidates = []
        for chunk, score in zip(candidate_chunks, scores):
            new_chunk = dict(chunk)
            new_chunk["rerank_score"] = float(score)
            scored_candidates.append(new_chunk)

        # Sort descending by rerank score
        sorted_candidates = sorted(scored_candidates, key=lambda x: x["rerank_score"], reverse=True)

        # Log pre-rerank (fused) and post-rerank (cross-encoder) scores at DEBUG level for top candidates
        logger.debug("Reranking top candidates:")
        for idx, item in enumerate(sorted_candidates[:10]):
            fused_score = item.get("fused_score", 0.0)
            rerank_score = item.get("rerank_score", 0.0)
            text_preview = (item.get("chunk_text") or item.get("text", ""))[:60].replace("\n", " ")
            logger.debug(
                f"Rank {idx+1} | ID: {item.get('id', 'N/A')} | Fused Score: {fused_score:.4f} | "
                f"Rerank Score: {rerank_score:.4f} | Preview: '{text_preview}...'"
            )

        return sorted_candidates[:top_n]

# Instantiate singleton reranker service
reranker_service = RerankerService()
