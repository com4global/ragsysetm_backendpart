"""
Vector Store Module (Pinecone)
Handles:
- Storing embeddings with page-level metadata
- Searching across single or multiple namespaces
- Returning chunks WITH proof (page, document, path)
"""

from pinecone import Pinecone
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path
import os

# --------------------------------------------------
# ENV SETUP
# --------------------------------------------------

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
    raise RuntimeError("Pinecone API key or index name not set")

# --------------------------------------------------
# CLIENT INIT
# --------------------------------------------------

pinecone = Pinecone(api_key=PINECONE_API_KEY)
index = pinecone.Index(PINECONE_INDEX_NAME)


# --------------------------------------------------
# UPSERT
# --------------------------------------------------


def store_in_pinecone(
    embedded_chunks: List[Dict],
    namespace: str
):
    """
    Store embeddings in Pinecone with metadata
    embedded_chunks = [
        {
            "embedding": [...],
            "metadata": {
                "text": "...",
                "page": "...",
                "doc_name": "...",
                "path": "..."
            }
        }
    ]
    """




   
    if not embedded_chunks:
        raise ValueError("No embedded chunks provided")

    vectors = []

    for i, item in enumerate(embedded_chunks):
        meta = item["metadata"]

        vector_id = f"{meta['doc_name']}::{meta['page']}::{i}"

        vectors.append({
            "id": vector_id,
            "values": item["embedding"],
            "metadata": meta
        })

    # Batch upsert
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        index.upsert(
            vectors=batch,
            namespace=namespace
        )

    print(f"✅ Upserted {len(vectors)} vectors into namespace '{namespace}'")

# --------------------------------------------------
# SEARCH
# --------------------------------------------------

#def search_in_pinecone(query_vector: List[float], top_k: int = 5, namespace: str | None = None) -> List[Dict]:
def search_in_pinecone(query_vector: List[float], top_k: int = 5, namespace: str | None = None) -> List[Dict]:
    results = []
    # If namespace is provided, wrap it in a list to use the same logic
    namespaces_to_search = [namespace] if namespace else list(index.describe_index_stats().namespaces.keys())

    for ns in namespaces_to_search:
        res = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            namespace=ns
        )
        
        for match in res.matches:
            results.append({
                "text": match.metadata.get("text", ""),
                "score": match.score,
                "page": match.metadata.get("page", "N/A"),
                "doc_name": match.metadata.get("doc_name", "Unknown"),
                "path": match.metadata.get("path", "Unknown"),
                "namespace": ns
            })

    # Sort all results from all namespaces by score
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

# def search_in_pinecone(
#     query_vector: List[float],
#     top_k: int = 5,
#     namespace: str | None = None
# ) -> List[Dict]:
#     """
#     Search Pinecone and return chunks WITH proof

#     Returns:
#     [
#         {
#             "text": "...",
#             "score": 0.89,
#             "page": "Page 2",
#             "doc_name": "HRPolicy.pdf",
#             "path": "/resources/HRPolicy.pdf",
#             "namespace": "pdf"
#         }
#     ]
#     """

#     results = []

#     # ---------- SINGLE NAMESPACE ----------
#     if namespace:
#         print(f"🔍 Searching namespace: {namespace}")

#         res = index.query(
#             vector=query_vector,
#             top_k=top_k,
#             include_metadata=True,
#             namespace=namespace
#         )
#     for match in res.matches:
#         print("DEBUG MATCH ID:", match.id)
#         print("DEBUG METADATA:", match.metadata)
#         print("DEBUG PAGE:", match.metadata.get("page"))
#         print("DEBUG DOC:", match.metadata.get("doc_name"))
#         print("DEBUG PATH:", match.metadata.get("path"))
#         print("-" * 40)
#         for match in res.matches:
#             results.append({
#                 "text": match.metadata.get("text", ""),
#                 "score": match.score,
#                 "page": match.metadata.get("page"),
#                 "doc_name": match.metadata.get("doc_name"),
#                 "path": match.metadata.get("path"),
#                 "namespace": namespace
#             })

#         return results

#     # ---------- ALL NAMESPACES ----------
#     print("🔍 Searching across ALL namespaces")

#     stats = index.describe_index_stats()
    
#     print("AVAILABLE NAMESPACES:", stats.namespaces)
#     namespaces = list(stats.namespaces.keys())

#     for ns in namespaces:
#         try:
#             res = index.query(
#                 vector=query_vector,
#                 top_k=top_k,
#                 include_metadata=True,
#                 namespace=ns
#             )

#             for match in res.matches:
#                 results.append({
#                     "text": match.metadata.get("text", ""),
#                     "score": match.score,
#                     "page": match.metadata.get("page"),
#                     "doc_name": match.metadata.get("doc_name"),
#                     "path": match.metadata.get("path"),
#                     "namespace": ns
#                 })

#         except Exception as e:
#             print(f"⚠️ Failed searching namespace '{ns}': {e}")

#     # Sort by relevance
#     results.sort(key=lambda x: x["score"], reverse=True)

#     final_results = results[:top_k]

#     print(f"✅ Retrieved {len(final_results)} results")

#     return final_results
