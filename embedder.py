from openai import OpenAI
from dotenv import load_dotenv
import os
import time
import logging
from typing import List

# Load environment variables from .env file
load_dotenv()   
# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536-dimension vectors

logger = logging.getLogger(__name__)

# ─── Single-chunk embedding (legacy, still used by embed_User_query) ───

def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """Embeds chunks using OpenAI's embedding model (one API call per chunk - legacy)."""
    embeddings = []
    for chunk in chunks:
        response = client.embeddings.create(
            input=chunk,
            model=EMBEDDING_MODEL
        )
        embeddings.append(response.data[0].embedding)

    return embeddings


def embed_User_query(query: str) -> List[float]:
    """Embeds a user query using OpenAI's embedding model."""
    response = client.embeddings.create(
        input=query,
        model=EMBEDDING_MODEL
    )
    return response.data[0].embedding


# ─── Batch embedding (new, 50 chunks per API call → ~10-50x faster) ───

BATCH_SIZE = 50  # OpenAI supports up to 2048 inputs per call, 50 is safe for token limits

def embed_chunks_batch(chunks: List[str], batch_size: int = BATCH_SIZE) -> List[List[float]]:
    """
    Embeds chunks in batches using OpenAI's embedding API.
    Sends up to `batch_size` texts per API call instead of one-at-a-time.
    Includes retry with exponential backoff for rate limits.
    
    Args:
        chunks: List of text chunks to embed
        batch_size: Number of chunks per API call (default 50)
    
    Returns:
        List of embedding vectors in the same order as input chunks
    """
    all_embeddings = []
    total = len(chunks)
    
    for i in range(0, total, batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        # Retry with exponential backoff
        for attempt in range(5):
            try:
                response = client.embeddings.create(
                    input=batch,
                    model=EMBEDDING_MODEL
                )
                # OpenAI returns embeddings in the same order as input
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                logger.info(f"⚡ Batch {batch_num}/{total_batches}: embedded {len(batch)} chunks")
                break
            except Exception as e:
                error_str = str(e).lower()
                if 'rate_limit' in error_str or '429' in error_str:
                    wait_time = (2 ** attempt) * 2  # 2, 4, 8, 16, 32 seconds
                    logger.warning(f"⏳ Rate limited on batch {batch_num}, waiting {wait_time}s (attempt {attempt+1}/5)")
                    time.sleep(wait_time)
                elif attempt < 4:
                    wait_time = (2 ** attempt)
                    logger.warning(f"⚠️ Embedding error on batch {batch_num}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"❌ Embedding failed after 5 attempts on batch {batch_num}: {e}")
                    raise
    
    return all_embeddings
