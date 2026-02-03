# 🎯 UI-to-Backend Debugging - Visual Quick Reference

## When User Queries Don't Get Responses

```
┌───────────────────────────────────────────────────────────────────┐
│  USER TYPES IN UI:  "What is the revenue in 2021?"               │
│                                                                   │
│  Expected: Bot responds with answer                              │
│  Actual: No response or wrong response                           │
│                                                                   │
│  👉 RUN THIS:  python debug_ui_flow.py                          │
└───────────────────────────────────────────────────────────────────┘
```

---

## Complete Request Flow

```
┌──────────────────┐
│   USER UI        │
│  "revenue 2021?" │
└────────┬─────────┘
         │ (1) axios.post("/chat", {query: ...})
         ▼
┌──────────────────────────────────┐
│    main.py - /chat endpoint      │
│  (chat request: QueryRequest)    │
└────────┬─────────────────────────┘
         │ (2) calls process_user_query()
         ▼
┌──────────────────────────────────┐
│  QueryProcessor.process_user_    │
│  query(query)                    │
└────────┬─────────────────────────┘
         │
         ├─ (3a) embed_User_query()         [embedder.py]
         │       ↓ returns: query_vector (1536-dim)
         │
         ├─ (3b) search_in_pinecone()       [vectorstore.py]
         │       ↓ returns: matched_chunks
         │
         └─ (3c) query_llm_with_context()   [llm.py]
                 (query, matched_chunks)
                 ↓ calls OpenAI API
                 ↓ returns: LLM response
         │
         ▼
┌──────────────────────────────────┐
│  main.py returns                 │
│  QueryResponse(response="...",   │
│  query="...")                    │
└────────┬─────────────────────────┘
         │ (4) axios response received
         ▼
┌──────────────────────────────────┐
│  Frontend updates state          │
│  setMessages(...bot message...)  │
└────────┬─────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│  USER SEES RESPONSE              │
│  "The revenue in 2021 was €95,   │
│   476 million."                  │
└──────────────────────────────────┘
```

---

## 🔍 Debugging Decision Tree

```
┌─ "Query reaches backend but no response"
│
├─ YES → RUN: python debug_ui_flow.py
│        │
│        ├─ Step 3 fails (Embedding)?      → pip install openai
│        ├─ Step 4 fails (Vector Search)?  → Check .env PINECONE_API_KEY
│        ├─ Step 5 fails (LLM)?            → Check .env OPENAI_API_KEY
│        └─ Step 6+ fails?                 → Check backend error logs
│
└─ NO → Check browser Network tab
       │
       ├─ POST request appears?
       │  ├─ YES → Check Response status
       │  │       ├─ 200? → Check response content
       │  │       └─ 500? → Backend error (check logs)
       │  │
       │  └─ NO → Frontend issue
       │          ├─ Check F12 Console for errors
       │          └─ Check ChatInterface.js URL is correct
       │
       └─ Browser shows "Sending..." forever?
              → Backend not responding
              → Run: curl http://localhost:8000/
```

---

## 🚀 3-Step Debug Process

### STEP 1: Run Flow Debugger (Automatic)
```bash
python debug_ui_flow.py
```
⏱️ Time: 5-10 seconds
📊 Shows which step fails

### STEP 2: Test Backend Directly (Bypass Frontend)
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue?"}'
```
⏱️ Time: 2 seconds
✅ If works → Frontend issue
❌ If fails → Backend issue

### STEP 3: Check Browser Network (See Real Data)
1. F12 → Network tab
2. Type query in UI
3. Look for POST to `/chat`
4. Check Request & Response tabs
⏱️ Time: 1-2 minutes
🔍 See exactly what's being sent/received

---

## ⚡ Common Failures & Instant Fixes

| Error | Fix |
|-------|-----|
| `No module named 'openai'` | `pip install openai` |
| `PINECONE_API_KEY not found` | Add to `.env` file |
| `OPENAI_API_KEY not found` | Add to `.env` file |
| `0 vectors in Pinecone` | Upload & process file first |
| `0 matches found` | Query keywords not in documents |
| `Backend not responding` | `python main.py` |
| `CORS error in browser` | Check main.py has CORSMiddleware |
| `Request timeout` | LLM taking too long (wait & retry) |

---

## 🎬 Test Scenarios

### Scenario 1: Everything Works
```
✅ python debug_ui_flow.py                    → All steps pass
✅ curl http://localhost:8000/chat            → Returns data
✅ Browser Network tab                        → Response 200
✅ UI shows response                          → Message appears
```

### Scenario 2: Backend Error
```
❌ python debug_ui_flow.py                    → Fails at Step 3-5
❌ curl http://localhost:8000/chat            → Error message
❌ Browser Network tab                        → Response 500
✅ Backend terminal shows error              → Fix the error
```

### Scenario 3: Frontend Error
```
✅ python debug_ui_flow.py                    → All steps pass
✅ curl http://localhost:8000/chat            → Returns data
❌ Browser Network tab                        → No POST request
❌ F12 Console shows error                    → Fix JavaScript
```

---

## 📊 Data Flow Visualization

### What Gets Sent?
```
Frontend → Backend
{
  "query": "What is the revenue in 2021?"
}
```

### What Gets Returned?
```
Backend → Frontend
{
  "response": "The revenue in 2021 was €95,476 million.",
  "query": "What is the revenue in 2021?"
}
```

### What Happens Inside Backend?
```
1. Receive query text
2. Convert to vector using OpenAI
3. Search Pinecone for similar vectors
4. Get back matching document chunks
5. Send query + chunks to OpenAI LLM
6. LLM generates response
7. Return response to frontend
```

---

## 🔧 Adding Logging for Debugging

### In [main.py](main.py):
```python
@app.post("/chat")
def chat(request: QueryRequest):
    print(f"🔵 Query received: {request.query}")
    try:
        response = process_user_query(request.query)
        print(f"✅ Response generated: {response[:100]}...")
        return QueryResponse(response=response, query=request.query)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
```

### In [QueryProcessor.py](QueryProcessor.py):
```python
def process_user_query(query: str):
    print(f"  [1] Embedding: {query}")
    query_vector = embed_User_query(query)
    
    print(f"  [2] Searching...")
    matched_chunks = search_in_pinecone(query_vector)
    print(f"  [2] Found {len(matched_chunks)} chunks")
    
    print(f"  [3] Calling LLM...")
    response = query_llm_with_context(query, matched_chunks)
    print(f"  [3] LLM response ready")
    
    return response
```

Now when you type in UI, backend terminal shows what's happening!

---

## 📱 Browser DevTools Guide

### Network Tab (See HTTP Requests)
```
1. F12 → Network tab
2. Type query in chat
3. Look for POST request
4. Click it
5. Check:
   - Headers: Shows method, URL, headers
   - Request: Shows what UI sent
   - Response: Shows what backend returned
   - Status: 200 = success, 500 = error
```

### Console Tab (See JavaScript Errors)
```
1. F12 → Console tab
2. Look for red errors
3. Read error message - it tells you what's wrong
   Examples:
   - "Cannot POST /chat" → Wrong URL
   - "CORS error" → Backend CORS not configured
   - "undefined is not a function" → JavaScript bug
```

---

## 🚨 Emergency Checklist

If nothing works, try this in order:

```
1. ☐ Backend running?
     curl http://localhost:8000/
     
2. ☐ Frontend running?
     Browser at http://localhost:3000
     
3. ☐ .env file exists?
     ls .env (or dir .env on Windows)
     
4. ☐ API keys configured?
     cat .env (or type .env on Windows)
     
5. ☐ Dependencies installed?
     pip list | grep openai
     pip list | grep pinecone
     
6. ☐ Files uploaded?
     ls resources/
     
7. ☐ Vector store has data?
     python -c "from vectorstore import index; print(index.describe_index_stats())"
     
8. ☐ Backend responding to requests?
     curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"query": "test"}'
     
9. ☐ All 3 steps pass in debug script?
     python debug_ui_flow.py
     
10. ☐ Browser Network tab shows request?
    F12 → Network tab → Type query → Look for POST /chat
```

---

## 📞 Files to Reference

| File | Purpose |
|------|---------|
| [debug_ui_flow.py](debug_ui_flow.py) | Traces complete UI→Backend flow |
| [DEBUG_UI_TO_LLM_FLOW.md](DEBUG_UI_TO_LLM_FLOW.md) | Detailed guide with code |
| [UI_TROUBLESHOOTING_GUIDE.md](UI_TROUBLESHOOTING_GUIDE.md) | 8 common issues & fixes |
| [DEBUG_COMPLETE_GUIDE.md](DEBUG_COMPLETE_GUIDE.md) | Full reference |
| [request_monitor.py](request_monitor.py) | Real-time monitoring |

---

## 🎯 Start Here

1. **Run this ONE command:**
   ```bash
   python debug_ui_flow.py
   ```

2. **It will tell you:**
   - Which step is failing
   - Why it's failing
   - How to fix it

3. **Then use:**
   - [UI_TROUBLESHOOTING_GUIDE.md](UI_TROUBLESHOOTING_GUIDE.md) for detailed fixes

That's it! 🚀
