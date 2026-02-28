"""
Query Processor with User Isolation + Hybrid Search + Re-ranking
================================================================
Phase 1 RAG Enhancement: 
  1. Vector search (Pinecone) — semantic similarity
  2. BM25 search (keyword matching) — exact term/phrase matching  
  3. Reciprocal Rank Fusion (RRF) — merge results
  4. Cross-encoder re-ranking — precision scoring
"""

from embedder import embed_User_query
from vectorstore import search_in_pinecone, search_user_documents
from llm import query_llm_with_context 
from typing import Dict, Optional
import logging
import time

logger = logging.getLogger(__name__)

# Safely import hybrid search modules (graceful fallback if not available)
try:
    from bm25_search import bm25_search, merge_search_results
    BM25_AVAILABLE = True
    logger.info("✅ BM25 hybrid search module loaded")
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("⚠️ BM25 module not available — using vector-only search")

try:
    from reranker import rerank_chunks
    RERANKER_AVAILABLE = True
    logger.info("✅ Cross-encoder re-ranker module loaded")
except ImportError:
    RERANKER_AVAILABLE = False
    logger.warning("⚠️ Re-ranker module not available — using original ranking")

try:
    from rag_monitor import QueryTrace
    MONITOR_AVAILABLE = True
except ImportError:
    MONITOR_AVAILABLE = False


def process_user_query(query: str, user_id: Optional[str] = None, language: str = "en") -> Dict:
    """
    Process user query with hybrid search (Vector + BM25) and cross-encoder re-ranking.
    
    Pipeline:
        1. Embed query → Pinecone vector search (semantic)
        2. BM25 keyword search (exact term matching) 
        3. Reciprocal Rank Fusion to merge results
        4. Cross-encoder re-ranker for precision
        5. Build context → LLM generates answer
    
    Graceful degradation:
        - If BM25 fails → vector-only search  
        - If re-ranker fails → use merged/vector ranking as-is
    """
    start_time = time.time()
    
    # Initialize monitoring trace (Phase 4)
    trace = None
    if MONITOR_AVAILABLE and user_id:
        try:
            trace = QueryTrace(user_id, query)
        except Exception:
            pass
    
    # 1. Embed the user question
    logger.info(f"🔍 Processing query: {query[:100]}...")
    if user_id:
        logger.info(f"👤 User ID: {user_id}")
    
    query_vector = embed_User_query(query)
    embed_time = time.time()
    
    # 2. VECTOR SEARCH (Pinecone — semantic similarity)
    # Retrieve more candidates (top_k=10) to give re-ranker better options
    if user_id:
        vector_results = search_user_documents(
            query_vector=query_vector,
            user_id=user_id,
            top_k=10
        )
    else:
        vector_results = search_in_pinecone(
            query_vector=query_vector,
            top_k=10
        )
    
    # Tag vector results with source
    for r in vector_results:
        r["source"] = "vector"
    
    vector_time = time.time()
    logger.info(f"📄 Vector search: {len(vector_results)} results ({(vector_time - embed_time)*1000:.0f}ms)")
    
    # 3. BM25 KEYWORD SEARCH (if available and user_id provided)
    bm25_results = []
    if BM25_AVAILABLE and user_id:
        try:
            bm25_results = bm25_search(
                query=query,
                user_id=user_id,
                top_k=10
            )
            logger.info(f"🔤 BM25 search: {len(bm25_results)} results")
        except Exception as e:
            logger.warning(f"⚠️ BM25 search failed (using vector-only): {e}")
    
    bm25_time = time.time()
    
    # 4. MERGE RESULTS (Reciprocal Rank Fusion)
    if bm25_results:
        merged_results = merge_search_results(vector_results, bm25_results, top_k=10)
    else:
        merged_results = vector_results
    
    merge_time = time.time()
    
    # 5. RE-RANK with cross-encoder (if available)
    if RERANKER_AVAILABLE and merged_results:
        try:
            final_results = rerank_chunks(
                query=query,
                chunks=merged_results,
                top_k=5
            )
        except Exception as e:
            logger.warning(f"⚠️ Re-ranking failed (using merged ranking): {e}")
            final_results = merged_results[:5]
    else:
        final_results = merged_results[:5]
    
    rerank_time = time.time()
    
    # 6. Build context and sources for LLM
    context = ""
    sources = [] 
    
    for m in final_results:
        # Build sources for the frontend 'Proof'
        if m.get('doc_name') and m.get('doc_name') != 'Unknown':
            source_entry = {
                "doc_name": m.get('doc_name'),
                "path": m.get('path'),
                "page": m.get('page')
            }
            
            # Avoid duplicate sources
            if source_entry not in sources:
                sources.append(source_entry)
        
        # Build the context for the LLM
        # Include match info for debugging
        match_info = ""
        if m.get("matched_by"):
            match_info = f" | Matched by: {', '.join(m['matched_by'])}"
        elif m.get("source"):
            match_info = f" | Matched by: {m['source']}"
        
        context += f"Document: {m.get('doc_name')} | Page: {m.get('page')} | Path: {m.get('path')}{match_info}\nContent: {m.get('text')}\n---\n"

    # 7. Get answer from LLM
    if not context:
        # No documents found — fall back to LLM's general knowledge
        logger.info("ℹ️ No relevant documents found — falling back to LLM general knowledge")
        answer = query_llm_with_context(query, "(No documents uploaded yet. Answer purely from your general knowledge.)", language=language)
        return {
            "answer": answer,
            "sources": [],
            "citation_coverage": 0.0,
            "is_grounded": False
        }

    answer = query_llm_with_context(query, context, language=language)
    
    total_time = time.time() - start_time
    
    # 8. CITATION COVERAGE SCORING (Phase 2 Enhancement)
    citation_info = {"citation_coverage": 0.0, "is_grounded": False, "citations_found": [], "has_general_knowledge": True}
    try:
        from llm import compute_citation_coverage
        citation_info = compute_citation_coverage(answer, sources)
        logger.info(
            f"📊 Citation coverage: {citation_info['citation_coverage']*100:.0f}% | "
            f"Grounded: {citation_info['is_grounded']} | "
            f"Citations: {citation_info['citations_found']}"
        )
    except Exception as e:
        logger.warning(f"⚠️ Citation scoring failed (non-critical): {e}")
    
    # Log performance breakdown
    logger.info(
        f"⏱️ Query pipeline: embed={int((embed_time-start_time)*1000)}ms, "
        f"vector={int((vector_time-embed_time)*1000)}ms, "
        f"bm25={int((bm25_time-vector_time)*1000)}ms, "
        f"merge={int((merge_time-bm25_time)*1000)}ms, "
        f"rerank={int((rerank_time-merge_time)*1000)}ms, "
        f"llm={int((total_time-(rerank_time-start_time))*1000)}ms, "
        f"total={int(total_time*1000)}ms"
    )
    
    # 9. SAVE MONITORING TRACE (Phase 4 — fire-and-forget)
    if trace:
        try:
            trace.record_stage("embed", latency_ms=(embed_time - start_time) * 1000)
            trace.record_stage("vector_search", latency_ms=(vector_time - embed_time) * 1000, extra={"results": len(vector_results)})
            trace.record_stage("bm25_search", latency_ms=(bm25_time - vector_time) * 1000, extra={"results": len(bm25_results)})
            trace.record_stage("merge", latency_ms=(merge_time - bm25_time) * 1000)
            trace.record_stage("rerank", latency_ms=(rerank_time - merge_time) * 1000, extra={"results": len(final_results)})
            trace.record_stage("llm", latency_ms=(total_time - (rerank_time - start_time)) * 1000)
            trace.finalize(
                answer=answer,
                sources=sources,
                citation_coverage=citation_info.get("citation_coverage", 0.0),
                is_grounded=citation_info.get("is_grounded", False),
                chunks_retrieved=len(final_results),
                bm25_used=bool(bm25_results),
                reranker_used=RERANKER_AVAILABLE
            )
            trace.save()
        except Exception as e:
            logger.warning(f"⚠️ Monitoring trace save failed (non-critical): {e}")
    
    result = {
        "answer": answer,
        "sources": sources,
        "citation_coverage": citation_info.get("citation_coverage", 0.0),
        "is_grounded": citation_info.get("is_grounded", False),
        "context_chunks": [m.get("text", "") for m in final_results],  # For faithfulness monitoring
        "response_time_ms": total_time * 1000,
    }
    
    if user_id:
        result["user_id"] = user_id
    
    return result


def verify_user_access(user_id: str, doc_name: str) -> bool:
    """
    Verify if a user has access to a specific document
    
    Args:
        user_id: User ID
        doc_name: Document name to check
        
    Returns:
        Boolean indicating if user has access
    """
    try:
        # Do a simple search in user's namespace for this document
        dummy_query = embed_User_query("test")
        
        matches = search_user_documents(
            query_vector=dummy_query,
            user_id=user_id,
            top_k=1
        )
        
        # Check if any match is from the requested document
        for match in matches:
            if match.get('doc_name') == doc_name:
                return True
        
        return False
    
    except Exception as e:
        print(f"Error verifying access: {e}")
        return False


def get_user_document_summary(user_id: str) -> Dict:
    """
    Get a summary of all documents accessible to a user
    Note: This is a lightweight check, not a full document list
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary with summary information
    """
    try:
        # Do a broad search to see what documents exist
        dummy_query = embed_User_query("summary")
        
        matches = search_user_documents(
            query_vector=dummy_query,
            user_id=user_id,
            top_k=20  # Get more to see variety
        )
        
        # Collect unique document names
        unique_docs = set()
        namespaces = set()
        
        for match in matches:
            doc_name = match.get('doc_name')
            namespace = match.get('namespace')
            
            if doc_name and doc_name != 'Unknown':
                unique_docs.add(doc_name)
            
            if namespace:
                namespaces.add(namespace)
        
        return {
            "user_id": user_id,
            "unique_documents": list(unique_docs),
            "document_count": len(unique_docs),
            "namespaces": list(namespaces)
        }
    
    except Exception as e:
        print(f"Error getting document summary: {e}")
        return {
            "user_id": user_id,
            "error": str(e)
        }


# --------------------------------------------------
# LEGACY SUPPORT
# --------------------------------------------------

def process_query_legacy(query: str, mode: str = "single_pdf") -> Dict:
    """
    Legacy function for backward compatibility
    Uses old namespace-based approach without user isolation
    
    Args:
        query: User's question
        mode: Search mode (not used anymore)
        
    Returns:
        Dictionary with answer and sources
    """
    print("⚠️ Using legacy mode (no user isolation)")
    return process_user_query(query, user_id=None)


# --------------------------------------------------
# TESTING
# --------------------------------------------------

if __name__ == "__main__":
    # Test with user isolation
    print("\n" + "=" * 70)
    print("Testing with User Isolation")
    print("=" * 70)
    
    test_user_id = "test-user-123"
    test_query = "What is the work timing?"
    
    res = process_user_query(test_query, user_id=test_user_id)
    
    print(f"\n🤖 AI Answer: {res['answer']}")
    print(f"\n📚 Sources ({len(res['sources'])}):")
    for source in res['sources']:
        print(f"  - {source['doc_name']} (Page: {source['page']})")
    
    # Test without user isolation (legacy)
    print("\n" + "=" * 70)
    print("Testing Legacy Mode (No User Isolation)")
    print("=" * 70)
    
    res_legacy = process_user_query(test_query, user_id=None)
    print(f"\n🤖 AI Answer: {res_legacy['answer']}")
# from embedder import embed_User_query
# from vectorstore import search_in_pinecone
# from llm import query_llm_with_context 

# def process_user_query(query: str):
#     # 1. Embed the user question
#     query_vector = embed_User_query(query)
    
#     # 2. Search Pinecone 
#     # To search BOTH YouTube and HR PDFs, do not filter by a single namespace 
#     # or pass a list if your search_in_pinecone supports it.
#     matches = search_in_pinecone(query_vector) 

#     context = ""
#     sources = [] 
    
#     for m in matches:
#         # Extract metadata from Pinecone match
#         #doc_name = m.metadata.get('doc_name', 'Unknown')
#         #page = m.metadata.get('page', 'N/A')
#         #path = m.metadata.get('path', 'No Link')
#         #text = m.metadata.get('text', '')

#         # Build sources for the frontend 'Proof'
#         if m.get('doc_name') and m.get('doc_name') != 'Unknown':
#             sources.append({
#             "doc_name": m.get('doc_name'),
#             "path": m.get('path'),
#             "page": m.get('page')
#             })
        
#         # Build the context for the LLM
#         # We include the Doc Name and Page so the LLM can 'see' the proof
#         context += f"Document: {m.get('doc_name')} | Page: {m.get('page')} | Path: {m.get('path')}\nContent: {m.get('text')}\n---\n"

#     # 3. Get answer from LLM
#     if not context:
#         return {"answer": "I couldn't find any relevant documents to answer this.", "sources": []}

#     answer = query_llm_with_context(query, context)
    
#     return {"answer": answer, "sources": sources}

# if __name__ == "__main__":
#     # Now this will work for both "HR timing" and "YouTube house breaking"
#     res = process_user_query("What is the work timing?")
#     print(f"AI: {res['answer']}")





# from embedder import embed_User_query
#from vectorstore import search_in_pinecone
# # Import your specific YouTube function
# from llm import ask_llm 

# def process_user_query(query: str, mode="single_pdf"):
#     query_vector = embed_User_query(query)
#     namespace = "pdf" if mode == "single_pdf" else "sharepoint"
#     matches = search_in_pinecone(query_vector, namespace=namespace)

#     context = ""
#     sources = [] 
    
#     for m in matches:
#         sources.append({
#             "doc_name": m.get('doc_name', 'Source'),
#             "Path": m.get('path', ''),
#             "page": m.get('page', 'N/A')
#         })
#         # We treat the text from Pinecone as the "Transcript" chunks
#         context += f"{m.get('text')}\n"

#     # CALLING YOUR YOUTUBE FUNCTION:
#     # We pass 'context' (the chunks) as the 'transcript' argument
#     answer = ask_llm(transcript=context, question=query)
    
#     return {"answer": answer, "sources": sources}


 #for testing youtube transcript function specifically
# from embedder import embed_User_query
# from vectorstore import search_in_pinecone
# # # Import the specific function we just added to llm.py
# from llm import query_llm_with_context 

# def process_user_query(query: str, mode="single_pdf"):
#     query_vector = embed_User_query(query)
#     #namespace = "txt" if mode == "single_pdf" else "sharepoint"
#     #matches = search_in_pinecone(query_vector, namespace=namespace)
#     matches = search_in_pinecone(query_vector)

#     context = ""
#     sources = [] 
    
#     for m in matches:
#         # Collecting metadata for the frontend
#         sources.append({
#             "doc_name": m.get('doc_name', 'Unknown Document'),
#             "path": m.get('path', ''),
#             "page": str(m.get('page', 'N/A'))
#         })
        
#         # Building the text context for the LLM
#         context += f"Document: {m.get('doc_name')}\nPage: {m.get('page')}\nContent:\n{m.get('text')}\n---\n"

#     # CALLING THE LLM: 
#     # This now matches the function name in llm.py
#     answer = query_llm_with_context(query, context)
    
#     return {"answer": answer, "sources": sources}

# if __name__ == "__main__":
#     # Test call
#     res = process_user_query("When I broke my own house?")
#     print(f"AI Answer: {res['answer']}")

# from embedder import embed_User_query
# from vectorstore import search_in_pinecone
# from llm import query_llm_with_context
# def process_user_query(query: str, mode="single_pdf"):
#     query_vector = embed_User_query(query)
#     namespace = "pdf" if mode == "single_pdf" else "sharepoint"
#     matches = search_in_pinecone(query_vector, namespace=namespace)

#     context = ""
#     sources = [] # Create a list for the frontend
#     for m in matches:
#         sources.append({
#             "doc_name": m['doc_name'],
#             "Path": m['path'],
#             "page": m['page']
#         })
#         context += f"Document: {m['doc_name']}\npath: {m['path']}\nPage: {m['page']}\nContent:\n{m['text']}\n---\n"

#     answer = query_llm_with_context(query, context)
    
#     # Return both the answer AND the source list
#     return {"answer": answer, "sources": sources}
# def process_user_query(query: str, mode="single_pdf"):
#     query_vector = embed_User_query(query)
#     namespace = "pdf" if mode == "single_pdf" else "sharepoint"
#     matches = search_in_pinecone(query_vector)
#     print(f"🔍 Found {len(matches)} relevant chunks in namespace '{namespace}'",matches)

#     context = ""
#     for m in matches:
#         context += f"""
# Document: {m['doc_name']}
# Page: {m['page']}
# Path: {m['path']}
# Content:
# {m['text']}
# ---
# """

#     return query_llm_with_context(query, context)




# if __name__ == "__main__":
#     user_query = "What is the work timing policy?"
#     process_user_query(user_query)