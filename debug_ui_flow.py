import sys
from pathlib import Path
import time

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_step(step_num, title):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}STEP {step_num}: {title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

# ============================================================
# STEP 1: FRONTEND - Simulate UI Input
# ============================================================

def debug_step_1_ui_input():
    print_step(1, "Frontend - User types query in UI")
    
    user_query = "What is the revenue in 2021?"
    
    print(f"📝 User input: '{user_query}'")
    print(f"📍 Frontend file: frontend/src/ChatInterface.js")
    print(f"📍 Function: handleSendMessage()")
    print(f"📍 HTTP Method: POST")
    print(f"📍 Endpoint: http://localhost:8000/chat")
    
    payload = {
        "query": user_query
    }
    print(f"\n📦 Payload being sent:")
    print(f"   {payload}")
    
    print_success(f"Frontend will send POST request with query: '{user_query}'")
    
    return user_query

# ============================================================
# STEP 2: BACKEND - Receive Query
# ============================================================

def debug_step_2_backend_receive(user_query):
    print_step(2, "Backend - main.py receives query")
    
    print(f"📍 Endpoint: POST /chat")
    print(f"📍 Handler: chat(request: QueryRequest)")
    print(f"📍 File: main.py (lines 34-39)")
    
    print(f"\n📥 Received QueryRequest:")
    print(f"   query: '{user_query}'")
    
    print_success("Backend received query, now calling process_user_query()")
    return user_query

# ============================================================
# STEP 3: QueryProcessor - Embed Query
# ============================================================

def debug_step_3_embed_query(user_query):
    print_step(3, "QueryProcessor - Embed user query")
    
    print(f"📍 File: QueryProcessor.py")
    print(f"📍 Function: process_user_query(query)")
    print(f"📍 Step 1/3: Query embedding")
    
    try:
        from embedder import embed_User_query
        
        print(f"   Query: '{user_query}'")
        query_vector = embed_User_query(user_query)
        
        print_success("Query embedded successfully")
        print(f"   Vector dimensions: {len(query_vector)}")
        print(f"   Vector type: {type(query_vector)}")
        print(f"   Sample values (first 5): {query_vector[:5]}")
        
        return query_vector
    
    except Exception as e:
        print_error(f"Failed to embed query: {str(e)}")
        print_warning("Possible causes:")
        print("   - OpenAI API key not set in .env")
        print("   - No internet connection")
        print("   - Rate limited by OpenAI")
        return None

# ============================================================
# STEP 4: Vector Search - Find Relevant Chunks
# ============================================================

def debug_step_4_search_vectors(query_vector, user_query):
    print_step(4, "Vector Store - Search for relevant chunks")
    
    print(f"📍 File: vectorstore.py")
    print(f"📍 Function: search_in_pinecone(query_vector)")
    print(f"📍 Step 2/3: Vector similarity search")
    
    if query_vector is None:
        print_error("Cannot search: Query vector is None")
        return None
    
    try:
        from vectorstore import search_in_pinecone
        
        print(f"   Query vector dimensions: {len(query_vector)}")
        print(f"   Searching for top 4 matches...")
        
        results = search_in_pinecone(query_vector, top_k=4, namespace="")
        
        # vectorstore.py returns a LIST of strings, not a Pinecone result object
        matched_chunks = results if results else []
        
        if matched_chunks:
            print_success(f"Found {len(matched_chunks)} matching chunks")
            print(f"\n📋 Retrieved Chunks:")
            
            for i, chunk_text in enumerate(matched_chunks, 1):
                preview = chunk_text[:100] + "..." if len(chunk_text) > 100 else chunk_text
                
                print(f"\n   MATCH {i}:")
                print(f"   Text: {preview}")
                
        else:
            print_warning("No matches found in vector store")
            print_warning("Possible causes:")
            print("   - Query keywords not in documents")
            print("   - Vector store is empty")
            print("   - Pinecone connection failed")
        
        return matched_chunks
    
    except Exception as e:
        print_error(f"Failed to search vectors: {str(e)}")
        print_warning("Possible causes:")
        print("   - Pinecone API key not set")
        print("   - Index name incorrect")
        print("   - Vector dimensions mismatch")
        import traceback
        traceback.print_exc()
        return None

# ============================================================
# STEP 5: LLM - Generate Response
# ============================================================

def debug_step_5_llm_response(user_query, matched_chunks):
    print_step(5, "LLM - Generate response with context")
    
    print(f"📍 File: llm.py")
    print(f"📍 Function: query_llm_with_context(query, context)")
    print(f"📍 Step 3/3: LLM response generation")
    
    if matched_chunks is None:
        print_error("Cannot generate response: No matched chunks")
        return None
    
    if not matched_chunks:
        print_warning("No chunks to send to LLM")
        print_info("LLM will likely return: 'I cannot find information to answer this question'")
    
    try:
        from llm import query_llm_with_context
        
        # Format context
        context = "\n\n".join(matched_chunks) if matched_chunks else "No context available"
        
        print(f"   Query: '{user_query}'")
        print(f"   Context chunks: {len(matched_chunks)}")
        print(f"   Context length: {len(context)} characters")
        print(f"   LLM Model: gpt-3.5-turbo")
        print(f"   Temperature: 0.4")
        
        print(f"\n   Sending to OpenAI API...")
        start_time = time.time()
        
        response = query_llm_with_context(user_query, context)
        
        elapsed_time = time.time() - start_time
        
        print_success(f"Response generated in {elapsed_time:.2f} seconds")
        print(f"\n📝 LLM Response:")
        print(f"   {response}")
        
        return response
    
    except Exception as e:
        print_error(f"Failed to generate LLM response: {str(e)}")
        print_warning("Possible causes:")
        print("   - OpenAI API key not set")
        print("   - Rate limited by OpenAI")
        print("   - Model gpt-3.5-turbo not available")
        print("   - No internet connection")
        return None

# ============================================================
# STEP 6: Backend - Return Response
# ============================================================

def debug_step_6_backend_response(user_query, response):
    print_step(6, "Backend - Return response to frontend")
    
    print(f"📍 File: main.py")
    print(f"📍 Endpoint: POST /chat")
    print(f"📍 Return type: QueryResponse")
    
    if response is None:
        print_error("Response is None - error occurred")
        return None
    
    response_payload = {
        "response": response,
        "query": user_query
    }
    
    print(f"\n📤 Response payload:")
    print(f"   {{")
    print(f"     'response': '{response}'")
    print(f"     'query': '{user_query}'")
    print(f"   }}")
    
    print_success("Response sent to frontend")
    return response_payload

# ============================================================
# STEP 7: Frontend - Display Response
# ============================================================

def debug_step_7_frontend_display(response_payload):
    print_step(7, "Frontend - Display response in chat")
    
    print(f"📍 File: frontend/src/ChatInterface.js")
    print(f"📍 Function: handleSendMessage() catch block")
    
    if response_payload is None:
        print_error("No response to display")
        return
    
    print(f"📥 Frontend received:")
    print(f"   Response: {response_payload['response']}")
    
    print(f"\n💬 User will see:")
    print(f"   {response_payload['response']}")
    
    print_success("Message displayed in chat interface")

# ============================================================
# STEP 8: Full Flow Summary
# ============================================================

def debug_step_8_summary(user_query, response):
    print_step(8, "Complete Flow Summary")
    
    print(f"\n{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{YELLOW}FLOW TRACE{RESET}")
    print(f"{YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    
    print(f"\n1️⃣  User types in UI:")
    print(f"    '{user_query}'")
    
    print(f"\n2️⃣  Frontend sends POST to:")
    print(f"    http://localhost:8000/chat")
    
    print(f"\n3️⃣  Backend processes in QueryProcessor.py:")
    print(f"    ├─ Embeds query (embedder.py)")
    print(f"    ├─ Searches Pinecone (vectorstore.py)")
    print(f"    └─ Calls OpenAI LLM (llm.py)")
    
    print(f"\n4️⃣  LLM Response:")
    print(f"    '{response}'")
    
    print(f"\n5️⃣  Frontend displays response in chat")
    
    if response:
        print_success(f"✅ COMPLETE FLOW SUCCESSFUL!")
    else:
        print_error(f"❌ FLOW FAILED - See errors above")

# ============================================================
# MAIN DEBUGGING FUNCTION
# ============================================================

def run_ui_flow_debug():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{'     '*14}UI-TO-LLM COMPLETE FLOW DEBUGGING{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    # Run all steps
    user_query = debug_step_1_ui_input()
    debug_step_2_backend_receive(user_query)
    query_vector = debug_step_3_embed_query(user_query)
    matched_chunks = debug_step_4_search_vectors(query_vector, user_query)
    response = debug_step_5_llm_response(user_query, matched_chunks)
    response_payload = debug_step_6_backend_response(user_query, response)
    debug_step_7_frontend_display(response_payload)
    debug_step_8_summary(user_query, response)

if __name__ == "__main__":
    run_ui_flow_debug()
