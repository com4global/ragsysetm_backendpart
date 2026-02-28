"""
BM25 Keyword Search Engine — Phase 1 of RAG Enhancement
========================================================
Provides BM25 (Best Matching 25) keyword search alongside Pinecone vector search.
BM25 excels at exact term/phrase matching while vector search handles semantic meaning.
Together they form a hybrid search that dramatically improves retrieval precision.

Architecture:
- On document ingestion: chunks are stored in Supabase `bm25_chunks` table
- On query: BM25 scores are computed against the user's stored chunks
- Results are merged with Pinecone vector results before re-ranking
"""

import logging
import os
import hashlib
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi
import re

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# TOKENIZER — simple whitespace + punctuation tokenization
# ──────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove stopwords."""
    # Lowercase and split on non-word characters
    tokens = re.findall(r'\b\w+\b', text.lower())
    # Remove very short tokens (1 char) but keep numbers
    tokens = [t for t in tokens if len(t) > 1 or t.isdigit()]
    return tokens


# ──────────────────────────────────────────────────────────────
# STORE CHUNKS — called during document ingestion
# ──────────────────────────────────────────────────────────────

def store_bm25_chunks(
    chunks: List[str],
    metadata_list: List[Dict],
    user_id: str,
    doc_name: str
) -> int:
    """
    Store chunk texts + metadata in Supabase for BM25 search.
    Called during document processing (dataprocessor.py).
    
    Args:
        chunks: List of chunk text strings
        metadata_list: List of metadata dicts (page, doc_name, path, etc.)
        user_id: User ID for isolation
        doc_name: Document name
        
    Returns:
        Number of chunks stored
    """
    try:
        from database import supabase
        if not supabase:
            logger.warning("⚠️ Supabase not available — skipping BM25 chunk storage")
            return 0

        records = []
        for text, meta in zip(chunks, metadata_list):
            records.append({
                "user_id": user_id,
                "doc_name": doc_name,
                "chunk_text": text,
                "page": str(meta.get("page", "N/A")),
                "path": meta.get("path", ""),
                "metadata": {
                    k: v for k, v in meta.items() 
                    if k not in ("text", "user_id")
                }
            })

        # Batch insert (100 at a time to avoid payload limits)
        stored = 0
        BATCH = 100
        for i in range(0, len(records), BATCH):
            batch = records[i:i + BATCH]
            try:
                supabase.table("bm25_chunks").insert(batch).execute()
                stored += len(batch)
            except Exception as e:
                logger.warning(f"⚠️ BM25 chunk batch {i//BATCH + 1} failed: {e}")
                # Try one-by-one as fallback
                for rec in batch:
                    try:
                        supabase.table("bm25_chunks").insert(rec).execute()
                        stored += 1
                    except Exception:
                        pass

        logger.info(f"📝 Stored {stored}/{len(records)} BM25 chunks for '{doc_name}'")
        return stored

    except Exception as e:
        logger.warning(f"⚠️ BM25 chunk storage failed (non-critical): {e}")
        return 0


def delete_bm25_chunks(user_id: str, doc_name: str) -> int:
    """Delete all BM25 chunks for a specific document."""
    try:
        from database import supabase
        if not supabase:
            return 0
        result = supabase.table("bm25_chunks") \
            .delete() \
            .eq("user_id", user_id) \
            .eq("doc_name", doc_name) \
            .execute()
        count = len(result.data) if result.data else 0
        logger.info(f"🗑️ Deleted {count} BM25 chunks for '{doc_name}'")
        return count
    except Exception as e:
        logger.warning(f"⚠️ BM25 chunk deletion failed: {e}")
        return 0


# ──────────────────────────────────────────────────────────────
# BM25 SEARCH — called during query time
# ──────────────────────────────────────────────────────────────

def bm25_search(
    query: str,
    user_id: str,
    top_k: int = 10
) -> List[Dict]:
    """
    Perform BM25 keyword search over a user's stored chunks.
    
    Args:
        query: User's search query
        user_id: User ID for isolation
        top_k: Number of results to return
        
    Returns:
        List of dicts: [{text, score, page, doc_name, path, source: "bm25"}, ...]
    """
    try:
        from database import supabase
        if not supabase:
            logger.warning("⚠️ Supabase not available — skipping BM25 search")
            return []

        # Fetch all user's chunks from Supabase
        result = supabase.table("bm25_chunks") \
            .select("chunk_text, page, doc_name, path") \
            .eq("user_id", user_id) \
            .execute()

        chunks_data = result.data or []

        if not chunks_data:
            logger.info("📭 No BM25 chunks found for this user — skipping keyword search")
            return []

        # Build BM25 index in-memory
        corpus_texts = [r["chunk_text"] for r in chunks_data]
        tokenized_corpus = [_tokenize(text) for text in corpus_texts]
        
        # Handle edge case: all empty after tokenization
        if not any(tokenized_corpus):
            return []

        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = _tokenize(query)
        
        if not tokenized_query:
            return []

        # Score all chunks
        scores = bm25.get_scores(tokenized_query)

        # Get top results with positive scores
        scored_indices = [
            (i, float(scores[i])) 
            for i in range(len(scores)) 
            if scores[i] > 0
        ]
        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_results = scored_indices[:top_k]

        results = []
        for idx, score in top_results:
            row = chunks_data[idx]
            results.append({
                "text": row["chunk_text"],
                "score": score,
                "page": row.get("page", "N/A"),
                "doc_name": row.get("doc_name", "Unknown"),
                "path": row.get("path", ""),
                "source": "bm25"  # Identify as BM25 result
            })

        logger.info(f"🔤 BM25 found {len(results)} keyword matches (top score: {results[0]['score']:.2f})" if results else "🔤 BM25: no keyword matches")
        return results

    except Exception as e:
        logger.warning(f"⚠️ BM25 search failed (falling back to vector-only): {e}")
        return []


# ──────────────────────────────────────────────────────────────
# MERGE — combine vector + BM25 results
# ──────────────────────────────────────────────────────────────

def merge_search_results(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    top_k: int = 10
) -> List[Dict]:
    """
    Merge and deduplicate vector search + BM25 results using Reciprocal Rank Fusion (RRF).
    
    RRF Score = sum(1 / (k + rank)) across all result lists where chunk appears.
    This is the industry standard for merging ranked result lists.
    
    Args:
        vector_results: Results from Pinecone vector search
        bm25_results: Results from BM25 keyword search
        top_k: Number of merged results to return
        
    Returns:
        Merged, deduplicated, sorted list of results
    """
    K = 60  # RRF constant (standard value)
    
    # Build a merged dict keyed by chunk text (first 200 chars for dedup)
    merged = {}
    
    def _chunk_key(text: str) -> str:
        """Create a dedup key from chunk text."""
        return text[:200].strip().lower()
    
    # Score vector results
    for rank, result in enumerate(vector_results):
        key = _chunk_key(result.get("text", ""))
        if key not in merged:
            merged[key] = {
                **result,
                "rrf_score": 0.0,
                "sources": []
            }
        merged[key]["rrf_score"] += 1.0 / (K + rank + 1)
        merged[key]["sources"].append("vector")
    
    # Score BM25 results
    for rank, result in enumerate(bm25_results):
        key = _chunk_key(result.get("text", ""))
        if key not in merged:
            merged[key] = {
                **result,
                "rrf_score": 0.0,
                "sources": []
            }
        merged[key]["rrf_score"] += 1.0 / (K + rank + 1)
        if "bm25" not in merged[key]["sources"]:
            merged[key]["sources"].append("bm25")
    
    # Sort by RRF score
    sorted_results = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)
    
    # Clean up and return top_k
    final = []
    for r in sorted_results[:top_k]:
        final.append({
            "text": r.get("text", ""),
            "score": r.get("score", 0),
            "rrf_score": r.get("rrf_score", 0),
            "page": r.get("page", "N/A"),
            "doc_name": r.get("doc_name", "Unknown"),
            "path": r.get("path", ""),
            "namespace": r.get("namespace", ""),
            "matched_by": r.get("sources", [])
        })
    
    both_count = sum(1 for r in final if len(r.get("matched_by", [])) > 1)
    logger.info(f"🔀 Merged: {len(vector_results)} vector + {len(bm25_results)} BM25 → {len(final)} unique ({both_count} matched by both)")
    
    return final
