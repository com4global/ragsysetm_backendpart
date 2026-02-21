"""
Vector Store Module (Pinecone) with User Isolation
Handles:
- Storing embeddings with page-level metadata in user-specific namespaces
- Searching across single or multiple user namespaces
- Returning chunks WITH proof (page, document, path)
"""

from pinecone import Pinecone
from typing import List, Dict, Optional
from dotenv import load_dotenv
from pathlib import Path
import os
import hashlib

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
# NAMESPACE HELPERS
# --------------------------------------------------

def get_user_namespaces(user_id: str) -> List[str]:
    """
    Get all possible namespaces for a user across different file types
    
    Args:
        user_id: User ID
        
    Returns:
        List of namespace strings
    """
    user_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
    
    # Common file types
    file_types = ["pdf", "xlsx", "xls", "csv", "txt", "docx", "doc", "xml"]
    
    return [f"{ft}-user-{user_hash}" for ft in file_types]


# --------------------------------------------------
# UPSERT
# --------------------------------------------------

def store_in_pinecone(
    embedded_chunks: List[Dict],
    namespace: str
):
    """
    Store embeddings in Pinecone with metadata in specified namespace
    
    Args:
        embedded_chunks: List of dictionaries with structure:
            {
                "embedding": [...],
                "metadata": {
                    "text": "...",
                    "page": "...",
                    "doc_name": "...",
                    "path": "...",
                    "user_id": "..."  (optional but recommended)
                }
            }
        namespace: Namespace to store vectors (should be user-specific)
    """
    if not embedded_chunks:
        raise ValueError("No embedded chunks provided")

    vectors = []

    for i, item in enumerate(embedded_chunks):
        meta = item["metadata"]

        # Create unique vector ID
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
# SEARCH WITH USER ISOLATION
# --------------------------------------------------

def search_in_pinecone(
    query_vector: List[float],
    top_k: int = 5,
    namespace: Optional[str] = None,
    user_id: Optional[str] = None
) -> List[Dict]:
    """
    Search Pinecone and return chunks WITH proof
    
    Args:
        query_vector: Embedded query vector
        top_k: Number of results to return
        namespace: Specific namespace to search (optional)
        user_id: User ID for user-specific search (optional)
    
    Returns:
        List of dictionaries:
        [
            {
                "text": "...",
                "score": 0.89,
                "page": "Page 2",
                "doc_name": "HRPolicy.pdf",
                "path": "/resources/HRPolicy.pdf",
                "namespace": "pdf-user-a1b2c3d4"
            }
        ]
    """
    results = []
    
    # Determine which namespaces to search
    if namespace:
        # Search specific namespace
        namespaces_to_search = [namespace]
        print(f"🔍 Searching specific namespace: {namespace}")
    elif user_id:
        # Search all user's namespaces
        namespaces_to_search = get_user_namespaces(user_id)
        print(f"🔍 Searching user namespaces for user: {user_id}")
    else:
        # Legacy mode: search all namespaces
        try:
            stats = index.describe_index_stats()
            namespaces_to_search = list(stats.namespaces.keys())
            print(f"🔍 Searching ALL namespaces (legacy mode)")
        except:
            print("⚠️ Could not retrieve namespaces, searching default")
            namespaces_to_search = [""]

    # Search each namespace
    for ns in namespaces_to_search:
        try:
            res = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                namespace=ns
            )
            
            for match in res.matches:
                # Extract metadata
                metadata = match.metadata
                
                # Additional user_id filter if provided
                if user_id and metadata.get("user_id") != user_id:
                    continue
                
                results.append({
                    "text": metadata.get("text", ""),
                    "score": match.score,
                    "page": metadata.get("page", "N/A"),
                    "doc_name": metadata.get("doc_name", "Unknown"),
                    "path": metadata.get("path", "Unknown"),
                    "namespace": ns
                })
        
        except Exception as e:
            # Namespace might not exist yet
            print(f"⚠️ Could not search namespace '{ns}': {e}")
            continue

    # Sort all results by score
    results.sort(key=lambda x: x["score"], reverse=True)
    
    # Return top_k results
    final_results = results[:top_k]
    
    print(f"✅ Retrieved {len(final_results)} results")
    
    return final_results


# --------------------------------------------------
# USER-SPECIFIC SEARCH (CONVENIENCE FUNCTION)
# --------------------------------------------------

def search_user_documents(
    query_vector: List[float],
    user_id: str,
    top_k: int = 5
) -> List[Dict]:
    """
    Convenience function to search only a specific user's documents
    
    Args:
        query_vector: Embedded query vector
        user_id: User ID to search for
        top_k: Number of results
        
    Returns:
        List of search results from user's documents only
    """
    return search_in_pinecone(
        query_vector=query_vector,
        top_k=top_k,
        user_id=user_id
    )


# --------------------------------------------------
# DOC-NAME SEARCH (for classroom / assigned documents)
# --------------------------------------------------

def search_by_doc_name(
    query_vector: List[float],
    doc_name: str,
    top_k: int = 10
) -> List[Dict]:
    """
    Search across ALL namespaces but filter by doc_name metadata.
    Used when a student wants to study a teacher-assigned document that
    lives in a different user's namespace.

    Args:
        query_vector: Embedded query vector
        doc_name: Exact document name to filter on (e.g. "chapter1.pdf")
        top_k: Number of results

    Returns:
        List of matching chunks with text, score, page, doc_name, path
    """
    results = []

    try:
        stats = index.describe_index_stats()
        namespaces_to_search = list(stats.namespaces.keys())
        print(f"🔍 Searching ALL namespaces for doc_name='{doc_name}'")
    except Exception:
        print("⚠️ Could not list namespaces, falling back to empty namespace")
        namespaces_to_search = [""]

    for ns in namespaces_to_search:
        try:
            res = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter={"doc_name": {"$eq": doc_name}},
                namespace=ns
            )
            for match in res.matches:
                metadata = match.metadata
                results.append({
                    "text": metadata.get("text", ""),
                    "score": match.score,
                    "page": metadata.get("page", "N/A"),
                    "doc_name": metadata.get("doc_name", doc_name),
                    "path": metadata.get("path", "Unknown"),
                    "namespace": ns
                })
        except Exception as e:
            print(f"⚠️ Could not search namespace '{ns}' for doc_name: {e}")
            continue

    results.sort(key=lambda x: x["score"], reverse=True)
    final_results = results[:top_k]
    print(f"✅ search_by_doc_name returned {len(final_results)} results for '{doc_name}'")
    return final_results


# --------------------------------------------------
# NAMESPACE MANAGEMENT
# --------------------------------------------------

def get_namespace_stats(namespace: str) -> Dict:
    """
    Get statistics for a specific namespace
    
    Args:
        namespace: Namespace to check
        
    Returns:
        Dictionary with namespace statistics
    """
    try:
        stats = index.describe_index_stats()
        
        if namespace in stats.namespaces:
            ns_stats = stats.namespaces[namespace]
            return {
                "namespace": namespace,
                "vector_count": ns_stats.vector_count,
                "exists": True
            }
        else:
            return {
                "namespace": namespace,
                "vector_count": 0,
                "exists": False
            }
    except Exception as e:
        print(f"Error getting namespace stats: {e}")
        return {
            "namespace": namespace,
            "error": str(e)
        }


def delete_namespace(namespace: str):
    """
    Delete all vectors in a namespace
    WARNING: This is permanent!
    
    Args:
        namespace: Namespace to delete
    """
    try:
        index.delete(delete_all=True, namespace=namespace)
        print(f"🗑️ Deleted all vectors in namespace '{namespace}'")
    except Exception as e:
        print(f"❌ Error deleting namespace: {e}")
        raise


# Default embedding dimension (OpenAI text-embedding-3-small)
DEFAULT_EMBEDDING_DIM = 1536


def delete_vectors_by_doc_name(filename: str, namespace: Optional[str] = None) -> int:
    """
    Delete all vectors for a given document (by doc_name metadata).
    Used for "Remove from DB" and for full file delete.
    
    Args:
        filename: doc_name (file name) to remove from vector DB
        namespace: If provided, only search this namespace. Otherwise infer from file extension.
    
    Returns:
        Number of vectors deleted.
    """
    from pathlib import Path
    if namespace is None:
        namespace = Path(filename).suffix.lower().lstrip(".") or "txt"
    try:
        stats = index.describe_index_stats()
        dim = stats.dimension
    except Exception:
        dim = DEFAULT_EMBEDDING_DIM
    dummy_vector = [0.0] * dim
    ids_to_delete = []
    top_k = 10000
    while True:
        res = index.query(
            vector=dummy_vector,
            top_k=top_k,
            include_metadata=False,
            filter={"doc_name": {"$eq": filename}},
            namespace=namespace,
        )
        matches = res.matches or []
        if not matches:
            break
        ids_to_delete.extend([m.id for m in matches])
        if len(matches) < top_k:
            break
    if not ids_to_delete:
        print(f"📭 No vectors found for doc_name='{filename}' in namespace '{namespace}'")
        return 0
    for i in range(0, len(ids_to_delete), 1000):
        batch = ids_to_delete[i : i + 1000]
        index.delete(ids=batch, namespace=namespace)
    print(f"🗑️ Deleted {len(ids_to_delete)} vectors for '{filename}' from namespace '{namespace}'")
    return len(ids_to_delete)


def list_all_namespaces() -> List[str]:
    """
    List all namespaces in the index
    
    Returns:
        List of namespace names
    """
    try:
        stats = index.describe_index_stats()
        return list(stats.namespaces.keys())
    except Exception as e:
        print(f"Error listing namespaces: {e}")
        return []



# """
# Vector Store Module (Pinecone)
# Handles:
# - Storing embeddings with page-level metadata
# - Searching across single or multiple namespaces
# - Returning chunks WITH proof (page, document, path)
# """

# from pinecone import Pinecone
# from typing import List, Dict
# from dotenv import load_dotenv
# from pathlib import Path
# import os

# # --------------------------------------------------
# # ENV SETUP
# # --------------------------------------------------

# env_path = Path(__file__).resolve().parent / ".env"
# load_dotenv(dotenv_path=env_path)

# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

# if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
#     raise RuntimeError("Pinecone API key or index name not set")

# # --------------------------------------------------
# # CLIENT INIT
# # --------------------------------------------------

# pinecone = Pinecone(api_key=PINECONE_API_KEY)
# index = pinecone.Index(PINECONE_INDEX_NAME)


# # --------------------------------------------------
# # UPSERT
# # --------------------------------------------------


# def store_in_pinecone(
#     embedded_chunks: List[Dict],
#     namespace: str
# ):
#     """
#     Store embeddings in Pinecone with metadata
#     embedded_chunks = [
#         {
#             "embedding": [...],
#             "metadata": {
#                 "text": "...",
#                 "page": "...",
#                 "doc_name": "...",
#                 "path": "..."
#             }
#         }
#     ]
#     """




   
#     if not embedded_chunks:
#         raise ValueError("No embedded chunks provided")

#     vectors = []

#     for i, item in enumerate(embedded_chunks):
#         meta = item["metadata"]

#         vector_id = f"{meta['doc_name']}::{meta['page']}::{i}"

#         vectors.append({
#             "id": vector_id,
#             "values": item["embedding"],
#             "metadata": meta
#         })

#     # Batch upsert
#     batch_size = 100
#     for i in range(0, len(vectors), batch_size):
#         batch = vectors[i:i + batch_size]
#         index.upsert(
#             vectors=batch,
#             namespace=namespace
#         )

#     print(f"✅ Upserted {len(vectors)} vectors into namespace '{namespace}'")

# # --------------------------------------------------
# # SEARCH
# # --------------------------------------------------

# #def search_in_pinecone(query_vector: List[float], top_k: int = 5, namespace: str | None = None) -> List[Dict]:
# def search_in_pinecone(query_vector: List[float], top_k: int = 5, namespace: str | None = None) -> List[Dict]:
#     results = []
#     # If namespace is provided, wrap it in a list to use the same logic
#     namespaces_to_search = [namespace] if namespace else list(index.describe_index_stats().namespaces.keys())

#     for ns in namespaces_to_search:
#         res = index.query(
#             vector=query_vector,
#             top_k=top_k,
#             include_metadata=True,
#             namespace=ns
#         )
        
#         for match in res.matches:
#             results.append({
#                 "text": match.metadata.get("text", ""),
#                 "score": match.score,
#                 "page": match.metadata.get("page", "N/A"),
#                 "doc_name": match.metadata.get("doc_name", "Unknown"),
#                 "path": match.metadata.get("path", "Unknown"),
#                 "namespace": ns
#             })

#     # Sort all results from all namespaces by score
#     results.sort(key=lambda x: x["score"], reverse=True)
#     return results[:top_k]

# # def search_in_pinecone(
# #     query_vector: List[float],
# #     top_k: int = 5,
# #     namespace: str | None = None
# # ) -> List[Dict]:
# #     """
# #     Search Pinecone and return chunks WITH proof

# #     Returns:
# #     [
# #         {
# #             "text": "...",
# #             "score": 0.89,
# #             "page": "Page 2",
# #             "doc_name": "HRPolicy.pdf",
# #             "path": "/resources/HRPolicy.pdf",
# #             "namespace": "pdf"
# #         }
# #     ]
# #     """

# #     results = []

# #     # ---------- SINGLE NAMESPACE ----------
# #     if namespace:
# #         print(f"🔍 Searching namespace: {namespace}")

# #         res = index.query(
# #             vector=query_vector,
# #             top_k=top_k,
# #             include_metadata=True,
# #             namespace=namespace
# #         )
# #     for match in res.matches:
# #         print("DEBUG MATCH ID:", match.id)
# #         print("DEBUG METADATA:", match.metadata)
# #         print("DEBUG PAGE:", match.metadata.get("page"))
# #         print("DEBUG DOC:", match.metadata.get("doc_name"))
# #         print("DEBUG PATH:", match.metadata.get("path"))
# #         print("-" * 40)
# #         for match in res.matches:
# #             results.append({
# #                 "text": match.metadata.get("text", ""),
# #                 "score": match.score,
# #                 "page": match.metadata.get("page"),
# #                 "doc_name": match.metadata.get("doc_name"),
# #                 "path": match.metadata.get("path"),
# #                 "namespace": namespace
# #             })

# #         return results

# #     # ---------- ALL NAMESPACES ----------
# #     print("🔍 Searching across ALL namespaces")

# #     stats = index.describe_index_stats()
    
# #     print("AVAILABLE NAMESPACES:", stats.namespaces)
# #     namespaces = list(stats.namespaces.keys())

# #     for ns in namespaces:
# #         try:
# #             res = index.query(
# #                 vector=query_vector,
# #                 top_k=top_k,
# #                 include_metadata=True,
# #                 namespace=ns
# #             )

# #             for match in res.matches:
# #                 results.append({
# #                     "text": match.metadata.get("text", ""),
# #                     "score": match.score,
# #                     "page": match.metadata.get("page"),
# #                     "doc_name": match.metadata.get("doc_name"),
# #                     "path": match.metadata.get("path"),
# #                     "namespace": ns
# #                 })

# #         except Exception as e:
# #             print(f"⚠️ Failed searching namespace '{ns}': {e}")

# #     # Sort by relevance
# #     results.sort(key=lambda x: x["score"], reverse=True)

# #     final_results = results[:top_k]

# #     print(f"✅ Retrieved {len(final_results)} results")

# #     return final_results
