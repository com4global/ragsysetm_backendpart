# 🎯 UI-to-Backend Troubleshooting Guide

## Problem: User types query in UI but doesn't get response

This guide helps you diagnose why the backend isn't responding to UI queries.

---

## 🔍 Quick Diagnostics

### 1. Is the backend running?

```bash
# Terminal: Try to connect to backend
curl http://localhost:8000/

# Expected: {"message": "HR Assistant RAG API is running"}
```

**If this fails:**
```bash
# Start the backend
python main.py
```

---

### 2. Are all dependencies installed?

```bash
# Check critical modules
python -c "from embedder import embed_User_query; print('✅ embedder works')"
python -c "from vectorstore import index; print('✅ vectorstore works')"
python -c "from llm import query_llm_with_context; print('✅ llm works')"
python -c "from openai import OpenAI; print('✅ OpenAI installed')"
python -c "from pinecone import Pinecone; print('✅ Pinecone installed')"
```

**If any fail**, install missing packages:
```bash
pip install openai pinecone-client python-dotenv
```

---

### 3. Is .env file configured?

```bash
# Check if .env exists
ls -la .env  # Linux/Mac
dir .env     # Windows

# Check contents have keys
cat .env     # Linux/Mac
type .env    # Windows
```

**Must contain:**
```
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=pc-...
PINECONE_INDEX_NAME=hr-assistant-index
```

---

### 4. Run the flow debugger

```bash
python debug_ui_flow.py
```

This will trace each step and show where it fails.

---

## 🚨 Common Issues & Solutions

### ISSUE 1: Backend shows no errors but UI doesn't get response

**Symptoms:**
- Backend is running
- No error in console
- UI shows "Sending..." forever

**Debugging:**

```bash
# Step 1: Test backend directly
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue?"}'
```

**If works:** Issue is in frontend
**If fails:** Issue is in backend

---

### ISSUE 2: Backend returns error "No module named 'openai'"

**Root Cause:** OpenAI library not installed

**Solution:**
```bash
pip install openai
```

---

### ISSUE 3: Backend returns error "Pinecone API key not found"

**Root Cause:** .env file missing or incorrect

**Solution:**

1. Check `.env` file exists in project root:
```bash
ls .env  # or `dir .env` on Windows
```

2. If missing, create it:
```
OPENAI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=hr-assistant-index
```

3. Restart backend:
```bash
python main.py
```

---

### ISSUE 4: Backend returns "0 matches found"

**Root Cause:** Query keywords not in vector store

**Debugging:**

```python
# Step 1: Check if vector store has data
from vectorstore import index
stats = index.describe_index_stats()
print(f"Total vectors: {stats.total_vector_count}")
print(f"Namespaces: {list(stats.namespaces.keys())}")

# If 0 vectors, you need to upload and process files
```

**Solution:**
1. Upload file via UI
2. Process file: `/api/process-file?filename=your_file.xlsx`
3. Try query again

---

### ISSUE 5: Backend returns generic response "I cannot find..."

**Root Cause:** Retrieved chunks don't contain answer

**Debugging:**

```python
from embedder import embed_User_query
from vectorstore import search_in_pinecone

query = "What is the revenue?"
query_vector = embed_User_query(query)
results = search_in_pinecone(query_vector)

print(f"Found {len(results.matches)} matches")
for match in results.matches:
    print(f"Score: {match.score}")
    print(f"Text: {match.metadata['text'][:100]}")
```

**Solution:**
- Try rephrasing query
- Use more specific keywords
- Check if document contains the information

---

### ISSUE 6: CORS error in browser console

**Error:** `Access to XMLHttpRequest has been blocked by CORS policy`

**Root Cause:** Frontend and backend on different origins

**Solution:** Check [main.py](main.py) has CORS enabled:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### ISSUE 7: Frontend sends request but backend doesn't log anything

**Root Cause:** Frontend not actually sending request

**Debugging:**

1. Open browser DevTools (F12)
2. Network tab
3. Type query in UI
4. Look for POST request to `/chat`

**If no request appears:**
- Frontend has error (check Console tab)
- Endpoint URL is wrong in ChatInterface.js

**Check ChatInterface.js:**
```javascript
const response = await axios.post('http://localhost:8000/chat', {
    query: inputValue
});
```

Must match your backend URL.

---

### ISSUE 8: Request shows 500 Internal Server Error

**Root Cause:** Backend crashed or exception occurred

**Debugging:**

1. Look at backend terminal output
2. Find the error traceback
3. Follow the specific error guide below

**Common errors:**

#### Error: "Cannot connect to Pinecone"
```
Fix: Check PINECONE_API_KEY in .env
```

#### Error: "OpenAI API rate limit"
```
Fix: Wait a few minutes and try again
```

#### Error: "No chunks to embed"
```
Fix: Upload and process a file first
```

---

## 📊 Complete Debugging Workflow

### Step 1: Run flow debugger
```bash
python debug_ui_flow.py
```
**This identifies which component is failing**

### Step 2: Based on error, check specific component

**If Step 3 (Embedding) fails:**
```bash
python -c "from embedder import embed_User_query; embed_User_query('test')"
```

**If Step 4 (Vector Search) fails:**
```bash
python -c "from vectorstore import index; print(index.describe_index_stats())"
```

**If Step 5 (LLM) fails:**
```bash
python -c "from llm import query_llm_with_context; print('OpenAI OK')"
```

### Step 3: Add logging to debug specific issue

**To debug backend:**
Edit [main.py](main.py):
```python
@app.post("/chat")
def chat(request: QueryRequest):
    print(f"🔵 Query: {request.query}")
    
    try:
        from QueryProcessor import process_user_query
        response = process_user_query(request.query)
        print(f"✅ Response: {response}")
        return QueryResponse(response=response, query=request.query)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
```

**To debug QueryProcessor:**
Edit [QueryProcessor.py](QueryProcessor.py):
```python
def process_user_query(query: str):
    print(f"\n📍 Processing: {query}")
    
    # Step 1
    print(f"  Step 1: Embedding...")
    query_vector = embed_User_query(query)
    print(f"  ✅ Vector created: {len(query_vector)} dims")
    
    # Step 2
    print(f"  Step 2: Searching...")
    matched_chunks = search_in_pinecone(query_vector)
    print(f"  ✅ Found {len(matched_chunks)} chunks")
    
    # Step 3
    print(f"  Step 3: Calling LLM...")
    generated_response = query_llm_with_context(query, matched_chunks)
    print(f"  ✅ Response: {generated_response[:50]}...")
    
    return generated_response
```

### Step 4: Check browser console

1. Open F12 in browser
2. Go to Console tab
3. Look for JavaScript errors
4. Also check Network tab for failed requests

---

## ✅ Verification Checklist

Before assuming system is broken:

- [ ] Backend running: `curl http://localhost:8000/`
- [ ] Dependencies installed: `pip list | grep openai`
- [ ] .env file exists with keys
- [ ] Vector store has data: `python -c "from vectorstore import index; print(index.describe_index_stats().total_vector_count)"`
- [ ] API keys are valid (not expired)
- [ ] Files uploaded and processed
- [ ] Browser console has no errors (F12)
- [ ] Frontend and backend on same origin (or CORS enabled)

---

## 🎬 Testing Flow (Step-by-Step)

### Test 1: Backend API directly

```bash
# Terminal 1: Start backend
python main.py

# Terminal 2: Test endpoint
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue in 2021?"}'

# Expected: {"response": "The revenue in 2021 was €95,476 million.", "query": "..."}
```

### Test 2: Full Python flow

```bash
python debug_ui_flow.py
```

### Test 3: Frontend UI

1. Open http://localhost:3000 in browser
2. Type: "What is the revenue in 2021?"
3. Should see response appear

### Test 4: Debug with logging enabled

```bash
# Edit main.py to add print statements
# Restart backend
python main.py

# In UI, type query
# Check backend terminal for debug output
```

---

## 🔧 Emergency Fixes

### Reset and start fresh:

```bash
# 1. Stop backend (Ctrl+C in terminal)

# 2. Clear any stuck processes
# Windows:
taskkill /F /IM python.exe

# 3. Check API keys are still valid

# 4. Restart backend
python main.py

# 5. Test with debug script
python debug_ui_flow.py

# 6. Restart frontend dev server if needed
cd frontend && npm start
```

---

## 📞 Advanced Debugging

### Enable full request/response logging:

```python
# Add to main.py
import logging

logging.basicConfig(level=logging.DEBUG)

@app.middleware("http")
async def log_requests(request, call_next):
    print(f"\n📨 {request.method} {request.url}")
    response = await call_next(request)
    print(f"📤 Status: {response.status_code}")
    return response
```

### Monitor API calls:

```bash
# Linux/Mac: Watch backend logs in real-time
tail -f backend.log

# Or use a logging file in main.py
```

### Check Pinecone directly:

```python
from vectorstore import index

# View stats
stats = index.describe_index_stats()
print(f"Vectors: {stats.total_vector_count}")
print(f"Namespaces: {list(stats.namespaces.keys())}")

# List vectors in namespace
results = index.list(limit=10, namespace="excel")
for vector_id in results:
    print(vector_id)
```

---

## 📝 Logging Template

When reporting issues, include:

1. **Error message** from terminal/console
2. **Steps to reproduce** (what query you typed)
3. **Output of debug script:**
   ```bash
   python debug_ui_flow.py
   ```
4. **Environment check:**
   ```bash
   python -c "import openai; import pinecone; print('OK')"
   ```
5. **Pinecone status:**
   ```python
   from vectorstore import index
   print(index.describe_index_stats())
   ```
