# 🔍 UI-to-LLM Complete Flow Debugging Guide

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER TYPES IN UI                             │
│              "What is the revenue in 2021?"                     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  ChatInterface.js (Frontend)                                    │
│  - handleSendMessage() triggered                                │
│  - axios.post('http://localhost:8000/chat', {query: ...})      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  main.py - @app.post("/chat")                                   │
│  - Receives QueryRequest(query="What is the revenue...")        │
│  - Calls: process_user_query(request.query)                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  QueryProcessor.py - process_user_query()                       │
│                                                                  │
│  STEP 1: Embed query                                            │
│  ├─ embed_User_query(query)                                    │
│  └─ Returns: query_vector (1536-dim)                           │
│                                                                  │
│  STEP 2: Search vector DB                                      │
│  ├─ search_in_pinecone(query_vector)                           │
│  └─ Returns: matched_chunks (top 4)                            │
│                                                                  │
│  STEP 3: Generate LLM response                                  │
│  ├─ query_llm_with_context(query, matched_chunks)              │
│  └─ Returns: generated_response                                │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  main.py - /chat endpoint returns                               │
│  {                                                               │
│    "response": "The revenue in 2021 was €95,476 million.",     │
│    "query": "What is the revenue in 2021?"                     │
│  }                                                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  ChatInterface.js (Frontend)                                    │
│  - Receives response                                            │
│  - Displays message: "The revenue in 2021 was €95,476 million" │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Step-by-Step Debugging Script

Create a file `debug_ui_flow.py` to trace the entire flow:

```python
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
        
        matched_chunks = []
        if results and results.matches:
            print_success(f"Found {len(results.matches)} matching chunks")
            print(f"\n📋 Retrieved Chunks:")
            
            for i, match in enumerate(results.matches, 1):
                chunk_text = match.metadata.get('text', '')[:100] + "..."
                similarity_score = match.score
                
                print(f"\n   MATCH {i}:")
                print(f"   Score: {similarity_score:.4f}")
                print(f"   Text: {chunk_text}")
                
                matched_chunks.append(match.metadata.get('text', ''))
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
    print(f"    ├─ Embeds query")
    print(f"    ├─ Searches Pinecone")
    print(f"    └─ Calls OpenAI LLM")
    
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
```

---

## 🧪 How to Run This Debug Script

### Run the complete debugging flow:
```bash
python debug_ui_flow.py
```

This will:
1. ✅ Simulate user input
2. ✅ Embed the query
3. ✅ Search the vector store
4. ✅ Generate LLM response
5. ✅ Show complete flow with timing

---

## 🔧 Debugging Each Component Independently

### Debug Frontend (UI sending query correctly):
```bash
# Check browser console for errors
# In browser DevTools (F12):
# 1. Go to Network tab
# 2. Type query in chat
# 3. Look for POST request to http://localhost:8000/chat
# 4. Check Response tab to see what backend returned
```

### Debug Backend Receiving Query:
```python
# Edit main.py @app.post("/chat") section
# Add logging

@app.post("/chat")
def chat(request: QueryRequest):
    print(f"🔵 Backend received query: {request.query}")
    print(f"🔵 Query type: {type(request.query)}")
    print(f"🔵 Query length: {len(request.query)}")
    
    try:
        response = process_user_query(request.query)
        print(f"🔵 Generated response: {response}")
        return QueryResponse(response=response, query=request.query)
    except Exception as e:
        print(f"🔴 ERROR: {str(e)}")
        return {"error": str(e)}
```

### Debug Query Embedding:
```python
# Edit QueryProcessor.py
from embedder import embed_User_query

def process_user_query(query: str):
    print(f"\n📍 START PROCESSING QUERY: '{query}'")
    
    # Step 1: Embed
    print(f"   Step 1: Embedding query...")
    query_vector = embed_User_query(query)
    print(f"   ✅ Vector created: {len(query_vector)} dimensions")
    
    # Step 2: Search
    print(f"   Step 2: Searching vector store...")
    matched_chunks = search_in_pinecone(query_vector)
    print(f"   ✅ Found {len(matched_chunks)} chunks")
    
    # Step 3: LLM
    print(f"   Step 3: Calling LLM...")
    generated_response = query_llm_with_context(query, matched_chunks)
    print(f"   ✅ Response generated: {generated_response[:100]}...")
    
    print(f"📍 FINISHED PROCESSING\n")
    
    return generated_response
```

### Debug Vector Search:
```python
# Edit vectorstore.py search_in_pinecone function

def search_in_pinecone(query_vector: List[float], top_k: int = 4, namespace: str = ""):
    print(f"\n🔍 SEARCHING PINECONE:")
    print(f"   Vector dimensions: {len(query_vector)}")
    print(f"   Top K: {top_k}")
    print(f"   Namespace: '{namespace if namespace else 'all'}'")
    
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )
    
    print(f"   ✅ Found {len(results.matches)} matches")
    for i, match in enumerate(results.matches, 1):
        score = match.score
        text = match.metadata.get('text', '')[:50]
        print(f"      Match {i}: score={score:.4f} text={text}...")
    
    return results
```

### Debug LLM Response:
```python
# Edit llm.py

def query_llm_with_context(query: str, context: str):
    print(f"\n🤖 CALLING LLM:")
    print(f"   Query: '{query}'")
    print(f"   Context length: {len(context)} chars")
    print(f"   Model: gpt-3.5-turbo")
    
    system_content = """You are a helpful assistant..."""
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Query: {query}\n\nContext:\n{context}"}
        ],
        temperature=0.4
    )
    
    result = response.choices[0].message.content
    print(f"   ✅ Response: '{result[:100]}...'")
    
    return result
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Frontend sends request but backend doesn't receive
**Debug:**
```bash
# Check if backend is running
curl http://localhost:8000/
# Should return: {"message": "HR Assistant RAG API is running"}
```

**Solution:**
```bash
# Start backend
python main.py
```

### Issue 2: Backend receives query but returns error
**Check:**
- Is `.env` file in project root with OPENAI_API_KEY and PINECONE_API_KEY?
- Are dependencies installed?

**Debug:**
```bash
python -c "from embedder import embed_User_query; print('✅ Embedder works')"
python -c "from vectorstore import index; print('✅ Pinecone works')"
python -c "from llm import query_llm_with_context; print('✅ LLM works')"
```

### Issue 3: Query embedded but no matches found
**Possible causes:**
1. Vector store is empty (no files processed)
2. Query keywords not in documents
3. Vector dimensions mismatch

**Debug:**
```python
# Check vector store status
from vectorstore import index
stats = index.describe_index_stats()
print(f"Total vectors: {stats.total_vector_count}")
print(f"Namespaces: {list(stats.namespaces.keys())}")
```

### Issue 4: Matches found but LLM returns generic response
**Possible causes:**
1. Context is not relevant
2. LLM isn't reading context properly
3. Query is too vague

**Debug:**
```python
# Check what LLM is receiving
query = "What is the revenue in 2021?"
from vectorstore import search_in_pinecone
from embedder import embed_User_query

query_vector = embed_User_query(query)
results = search_in_pinecone(query_vector)

context = "\n\n".join([m.metadata.get('text', '') for m in results.matches])
print(f"Context being sent to LLM:\n{context}")
```

---

## 📊 Monitoring in Real-Time

### Watch Backend Logs:
```bash
# Terminal 1: Start backend with logging
python main.py

# Terminal 2: In the UI, type a query
# Watch Terminal 1 for debug output
```

### Browser Network Tab:
1. Open browser DevTools (F12)
2. Go to Network tab
3. Type query in chat UI
4. Look for POST request to `/chat`
5. Check Request and Response payloads

---

## ✅ Health Check

Run this to verify all components are connected:

```bash
python debug_ui_flow.py
```

Expected output should show:
- ✅ Step 1: UI Input
- ✅ Step 2: Backend Receives
- ✅ Step 3: Query Embedded
- ✅ Step 4: Vector Search
- ✅ Step 5: LLM Response
- ✅ Step 6: Backend Returns
- ✅ Step 7: Frontend Displays
