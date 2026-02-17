"""
Query Processor with User Isolation
Processes user queries with proper data isolation
"""

from embedder import embed_User_query
from vectorstore import search_in_pinecone, search_user_documents
from llm import query_llm_with_context 
from typing import Dict, Optional


def process_user_query(query: str, user_id: Optional[str] = None, language: str = "en") -> Dict:
    """
    Process user query with optional user-specific context
    
    Args:
        query: The user's question
        user_id: Optional user ID for data isolation
        
    Returns:
        Dictionary with answer and sources:
        {
            "answer": "The work timing is 9 AM to 5 PM...",
            "sources": [
                {
                    "doc_name": "HRPolicy.pdf",
                    "path": "/resources/user-123/HRPolicy.pdf",
                    "page": "Page 3"
                }
            ]
        }
    """
    # 1. Embed the user question
    print(f"🔍 Processing query: {query}")
    if user_id:
        print(f"👤 User ID: {user_id}")
    
    query_vector = embed_User_query(query)
    
    # 2. Search Pinecone with user context
    if user_id:
        # User-specific search (isolated data)
        matches = search_user_documents(
            query_vector=query_vector,
            user_id=user_id,
            top_k=5
        )
    else:
        # Legacy mode: search all namespaces (no isolation)
        matches = search_in_pinecone(
            query_vector=query_vector,
            top_k=5
        )
    
    print(f"📄 Found {len(matches)} relevant matches")
    
    # 3. Build context and sources
    context = ""
    sources = [] 
    
    for m in matches:
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
        # Include the Doc Name and Page so the LLM can 'see' the proof
        context += f"Document: {m.get('doc_name')} | Page: {m.get('page')} | Path: {m.get('path')}\nContent: {m.get('text')}\n---\n"

    # 4. Get answer from LLM
    if not context:
        no_docs_msg = (
            "தொடர்புடைய ஆவணங்களை என்னால் கண்டுபிடிக்க முடியவில்லை. தேவையான கோப்புகளை பதிவேற்றியுள்ளீர்கள் என்பதை உறுதிப்படுத்தவும்."
            if language == "ta" else
            "I couldn't find any relevant documents to answer this question. Please make sure you've uploaded the necessary files."
        )
        return {
            "answer": no_docs_msg,
            "sources": []
        }

    answer = query_llm_with_context(query, context, language=language)
    
    result = {
        "answer": answer,
        "sources": sources
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