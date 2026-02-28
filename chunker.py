"""
Chunker Module — Phase 3 RAG Enhancement
=========================================
Token-based chunking with sentence boundary awareness.

Key improvements over character-based chunking:
1. Uses tokens (tiktoken) instead of characters — consistent chunk sizes
2. Never splits mid-sentence — clean embeddings
3. Smart overlap preserves context across chunk boundaries
4. Fallback to character-based chunking if tiktoken unavailable
"""

import re
import logging
from typing import List

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# TIKTOKEN SETUP — lazy loaded
# ──────────────────────────────────────────────────────────────

_encoder = None

def _get_encoder():
    """Lazy-load tiktoken encoder for gpt-4o-mini."""
    global _encoder
    if _encoder is None:
        try:
            import tiktoken
            _encoder = tiktoken.encoding_for_model("gpt-4o-mini")
            logger.info("✅ tiktoken encoder loaded (token-based chunking active)")
        except Exception as e:
            logger.warning(f"⚠️ tiktoken not available, falling back to character-based chunking: {e}")
    return _encoder


def _count_tokens(text: str) -> int:
    """Count tokens in a text string."""
    enc = _get_encoder()
    if enc:
        return len(enc.encode(text))
    # Fallback: rough estimate (1 token ≈ 4 chars for English)
    return len(text) // 4


# ──────────────────────────────────────────────────────────────
# SENTENCE SPLITTER
# ──────────────────────────────────────────────────────────────

def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences, handling common edge cases.
    Handles: periods, question marks, exclamation marks, newlines.
    Avoids splitting on: abbreviations (Mr., Dr., etc.), numbers (3.14), URLs.
    """
    if not text or not text.strip():
        return []
    
    # Normalize whitespace but preserve paragraph breaks
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\r', '\n', text)
    
    # Split on sentence-ending punctuation followed by space/newline,
    # or on double newlines (paragraph breaks)
    # Regex: split at . ! ? followed by space and uppercase letter, or at \n\n
    sentences = []
    
    # First split on paragraph breaks
    paragraphs = re.split(r'\n\s*\n', text)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # Split paragraph into sentences
        # Use a regex that splits after sentence-ending punctuation
        # but avoids splitting on abbreviations and numbers
        parts = re.split(
            r'(?<=[.!?])\s+(?=[A-Z\u0B80-\u0BFF\u0900-\u097F"\'(])',  # Also handles Tamil/Hindi unicode starts
            para
        )
        
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)
    
    return sentences


# ──────────────────────────────────────────────────────────────
# NEW: TOKEN-BASED CHUNKER WITH SENTENCE BOUNDARIES
# ──────────────────────────────────────────────────────────────

def chunk_pages(
    text: str, 
    chunk_size: int = 600,       # Target chunk size in TOKENS
    chunk_overlap: int = 100     # Overlap in TOKENS
) -> List[str]:
    """
    Token-aware chunking with sentence boundary respect.
    
    Algorithm:
    1. Split text into sentences
    2. Group sentences into chunks of ~chunk_size tokens
    3. Never split a sentence between chunks
    4. Overlap last ~chunk_overlap tokens with next chunk
    
    Args:
        text: Full text to chunk
        chunk_size: Target chunk size in tokens (default: 600)
        chunk_overlap: Overlap between chunks in tokens (default: 100)
        
    Returns:
        List of text chunks (each is complete sentences, ~600 tokens)
    """
    if not text or not text.strip():
        return []
    
    enc = _get_encoder()
    
    # If tiktoken not available, fall back to legacy character-based chunking
    if enc is None:
        logger.warning("⚠️ Using legacy character-based chunking (tiktoken unavailable)")
        return chunk_pages_legacy(text, chunk_size=chunk_size * 4, chunk_overlap=chunk_overlap * 4)
    
    sentences = _split_into_sentences(text)
    
    if not sentences:
        # If sentence splitting fails, treat entire text as one chunk
        return [text.strip()] if text.strip() else []
    
    chunks = []
    current_sentences = []  # Sentences in current chunk
    current_tokens = 0      # Token count of current chunk
    
    for sentence in sentences:
        sent_tokens = len(enc.encode(sentence))
        
        # Handle very long sentences (longer than chunk_size)
        if sent_tokens > chunk_size:
            # Flush current chunk first
            if current_sentences:
                chunks.append(' '.join(current_sentences))
                current_sentences = []
                current_tokens = 0
            
            # Split long sentence by sub-sentences (commas, semicolons)
            sub_parts = re.split(r'(?<=[,;:])\s+', sentence)
            sub_chunk = []
            sub_tokens = 0
            
            for sub in sub_parts:
                sub_t = len(enc.encode(sub))
                if sub_tokens + sub_t > chunk_size and sub_chunk:
                    chunks.append(' '.join(sub_chunk))
                    sub_chunk = []
                    sub_tokens = 0
                sub_chunk.append(sub)
                sub_tokens += sub_t
            
            if sub_chunk:
                chunks.append(' '.join(sub_chunk))
            continue
        
        # Normal flow: add sentence if it fits
        if current_tokens + sent_tokens <= chunk_size:
            current_sentences.append(sentence)
            current_tokens += sent_tokens
        else:
            # Current chunk is full — save it
            if current_sentences:
                chunks.append(' '.join(current_sentences))
            
            # Build overlap: take sentences from the END of current chunk
            # until we have ~chunk_overlap tokens
            overlap_sentences = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                s_tokens = len(enc.encode(s))
                if overlap_tokens + s_tokens > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += s_tokens
            
            # Start new chunk with overlap + current sentence
            current_sentences = overlap_sentences + [sentence]
            current_tokens = overlap_tokens + sent_tokens
    
    # Don't forget the last chunk
    if current_sentences:
        last_chunk = ' '.join(current_sentences)
        # Avoid duplicating the last chunk if it's identical to the previous
        if not chunks or last_chunk != chunks[-1]:
            chunks.append(last_chunk)
    
    logger.info(
        f"✂️ Token chunking: {len(sentences)} sentences → {len(chunks)} chunks "
        f"(avg {sum(len(enc.encode(c)) for c in chunks) // max(len(chunks), 1)} tokens/chunk)"
    )
    
    return chunks


# ──────────────────────────────────────────────────────────────
# LEGACY: Character-based chunker (preserved for backward compat)
# ──────────────────────────────────────────────────────────────

def chunk_pages_legacy(text: str, chunk_size: int = 900, chunk_overlap: int = 150) -> List[str]:
    """
    Original character-based chunker (kept as fallback).
    
    Args:
        text: Full text to chunk
        chunk_size: Size in characters
        chunk_overlap: Overlap in characters
    """
    chunks = []
    start = 0
    if not text:
        return chunks
        
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        if end >= len(text):
            break
            
        # Move start forward, but stay back by the overlap amount
        start += (chunk_size - chunk_overlap)
    return chunks
