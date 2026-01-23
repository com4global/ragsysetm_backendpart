from pinecone import Pinecone
import os
from dotenv import load_dotenv
from typing import List
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize Pinecone client
pinecone_client = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pinecone_client.Index(index_name)


def store_in_pinecone(chunks: List[str], embeddings: List[List[float]], namespace: str = ""):
    vectors_to_upsert = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_data = {
            "id": f"chunk_{i}",
            "values": embedding,
            "metadata": {
                "text": chunk,
                "chunk_index": i
            }
        }
        vectors_to_upsert.append(vector_data)
    
    # Upsert vectors in batches (Pinecone recommends batch size of 100)
    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i:i + batch_size]
        index.upsert(vectors=batch, namespace=namespace)


def search_in_pinecone(query_vector: List[float], top_k: int = 4, namespace: str = ""):
    """
    Search for vectors in Pinecone across all namespaces
    If specific namespace is provided, search only in that namespace
    Otherwise, search across all documents (all namespaces)
    
    IMPORTANT: Searches each namespace separately and aggregates results by score
    """
    if namespace:
        # Search in specific namespace
        print(f"🔍 Searching in namespace: '{namespace}'")
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            namespace=namespace
        )
        matched_chunks = []
        for i, match in enumerate(results.matches, 1):
            chunk_text = match.metadata.get("text", "")
            score = match.score
            print(f"  Match {i}: score={score:.4f}, text_len={len(chunk_text)}")
            matched_chunks.append(chunk_text)
        return matched_chunks
    else:
        # Search across ALL namespaces by querying each one separately
        print(f"🔍 Searching across ALL namespaces...")
        all_matches = []
        
        # Get list of all namespaces in index
        index_stats = index.describe_index_stats()
        namespaces = list(index_stats.namespaces.keys()) if hasattr(index_stats, 'namespaces') else ['__default__']
        
        print(f"   Namespaces to search: {namespaces}")
        
        # Search each namespace
        for ns in namespaces:
            try:
                results = index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    namespace=ns
                )
                print(f"   Namespace '{ns}': {len(results.matches)} matches")
                for match in results.matches:
                    # Store match with namespace info
                    match.namespace = ns
                    all_matches.append(match)
            except Exception as e:
                print(f"   Error searching namespace '{ns}': {e}")
        
        # Sort all matches by score (highest first) and take top_k
        all_matches.sort(key=lambda x: x.score, reverse=True)
        top_matches = all_matches[:top_k]
        
        print(f"Found {len(top_matches)} matches for the query (aggregated from all namespaces).")
        
        # Extract text chunks
        matched_chunks = []
        for i, match in enumerate(top_matches, 1):
            chunk_text = match.metadata.get("text", "")
            score = match.score
            ns_info = getattr(match, 'namespace', 'unknown')
            print(f"  Match {i}: score={score:.4f}, namespace='{ns_info}', text_len={len(chunk_text)}")
            matched_chunks.append(chunk_text)
        
        return matched_chunks
