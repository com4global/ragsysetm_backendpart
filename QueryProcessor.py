
from embedder import embed_User_query
from vectorstore import search_in_pinecone
from llm import query_llm_with_context 

def process_user_query(query: str):
    # 1. Embed the user question
    query_vector = embed_User_query(query)
    
    # 2. Search Pinecone 
    # To search BOTH YouTube and HR PDFs, do not filter by a single namespace 
    # or pass a list if your search_in_pinecone supports it.
    matches = search_in_pinecone(query_vector) 

    context = ""
    sources = [] 
    
    for m in matches:
        # Extract metadata from Pinecone match
        #doc_name = m.metadata.get('doc_name', 'Unknown')
        #page = m.metadata.get('page', 'N/A')
        #path = m.metadata.get('path', 'No Link')
        #text = m.metadata.get('text', '')

        # Build sources for the frontend 'Proof'
        if m.get('doc_name') and m.get('doc_name') != 'Unknown':
            sources.append({
            "doc_name": m.get('doc_name'),
            "path": m.get('path'),
            "page": m.get('page')
            })
        
        # Build the context for the LLM
        # We include the Doc Name and Page so the LLM can 'see' the proof
        context += f"Document: {m.get('doc_name')} | Page: {m.get('page')} | Path: {m.get('path')}\nContent: {m.get('text')}\n---\n"

    # 3. Get answer from LLM
    if not context:
        return {"answer": "I couldn't find any relevant documents to answer this.", "sources": []}

    answer = query_llm_with_context(query, context)
    
    return {"answer": answer, "sources": sources}

if __name__ == "__main__":
    # Now this will work for both "HR timing" and "YouTube house breaking"
    res = process_user_query("What is the work timing?")
    print(f"AI: {res['answer']}")





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