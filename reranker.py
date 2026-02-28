"""
Cross-Encoder Re-ranker — Phase 1 of RAG Enhancement
=====================================================
Takes merged search results (vector + BM25) and re-scores them using a 
cross-encoder model that evaluates (query, chunk) pairs for relevance.

This dramatically improves precision because:
- Initial retrieval (vector/BM25) is fast but approximate
- Cross-encoder is slow but highly accurate — it reads query + chunk together
- We only re-rank the top candidates, so it stays fast enough

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, ~50ms per pair)
"""

import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# LAZY MODEL LOADING — only load when first used
# ──────────────────────────────────────────────────────────────

_reranker_model = None

def _get_reranker():
    """Lazy-load the cross-encoder model (downloads on first use, ~22MB)."""
    global _reranker_model
    if _reranker_model is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info("⏳ Loading cross-encoder re-ranker model (first time may download)...")
            _reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            logger.info("✅ Re-ranker model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load re-ranker model: {e}")
            _reranker_model = None
    return _reranker_model


# ──────────────────────────────────────────────────────────────
# RE-RANK — core function
# ──────────────────────────────────────────────────────────────

def rerank_chunks(
    query: str,
    chunks: List[Dict],
    top_k: int = 5,
    min_score: float = -10.0
) -> List[Dict]:
    """
    Re-rank search results using a cross-encoder model.
    
    The cross-encoder evaluates each (query, chunk_text) pair and produces
    a relevance score. Results are sorted by this score.
    
    Args:
        query: User's search query
        chunks: List of chunk dicts with at least a 'text' field
        top_k: Number of top results to return
        min_score: Minimum score threshold (cross-encoder scores can be negative)
        
    Returns:
        Re-ranked list of chunk dicts with added 'rerank_score' field
    """
    if not chunks:
        return []

    model = _get_reranker()
    
    if model is None:
        # Fallback: return chunks as-is if model failed to load
        logger.warning("⚠️ Re-ranker unavailable — returning original ranking")
        return chunks[:top_k]

    start_time = time.time()

    try:
        # Build (query, chunk_text) pairs
        pairs = [(query, chunk.get("text", "")) for chunk in chunks]
        
        # Score all pairs
        scores = model.predict(pairs)
        
        # Attach scores to chunks
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            scored_chunk = {**chunk}
            scored_chunk["rerank_score"] = float(score)
            scored_chunks.append(scored_chunk)
        
        # Sort by rerank_score (highest first)
        scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        # Filter by min_score and take top_k
        filtered = [c for c in scored_chunks if c["rerank_score"] >= min_score]
        result = filtered[:top_k]
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if result:
            logger.info(
                f"🎯 Re-ranked {len(chunks)} → {len(result)} chunks in {elapsed_ms:.0f}ms "
                f"(top score: {result[0]['rerank_score']:.3f}, "
                f"bottom score: {result[-1]['rerank_score']:.3f})"
            )
        else:
            logger.info(f"🎯 Re-ranker: no chunks passed score threshold {min_score}")
        
        return result

    except Exception as e:
        logger.error(f"❌ Re-ranking failed: {e} — returning original ranking")
        return chunks[:top_k]


# ──────────────────────────────────────────────────────────────
# WARMUP — pre-load model during startup
# ──────────────────────────────────────────────────────────────

def warmup_reranker():
    """
    Pre-load the re-ranker model so the first user query isn't slow.
    Call this during application startup (lifespan event).
    """
    try:
        model = _get_reranker()
        if model:
            # Run a dummy prediction to fully initialize
            model.predict([("test query", "test document")])
            logger.info("🔥 Re-ranker warmed up and ready")
            return True
    except Exception as e:
        logger.warning(f"⚠️ Re-ranker warmup failed (will retry on first query): {e}")
    return False
