<!-- markdownlint-disable -->
# 🔴 DEBUG GUIDE - Backend Debugging Setup

## Quick Start to Debug the Backend

### Option 1: Using VS Code Debug UI (Recommended)

1. **Open VS Code** and go to your workspace folder
2. **Go to Run & Debug** (Ctrl+Shift+D)
3. **Select "Debug FastAPI Backend"** from the dropdown
4. **Press F5** or click the Green Play button
5. The backend will start on `http://localhost:8000`

### Option 2: Using Debug Script

```bash
cd C:\Startup\GenAISample\RAG_HR_ASSISTANT
python debug_backend.py
```

---

## Testing the Backend with Swagger UI

Once the backend is running:

1. **Open Swagger UI**: http://localhost:8000/docs
2. **Find the `/chat` endpoint**
3. **Click "Try it out"**
4. **Enter a test query**:
   ```json
   {
     "query": "What is the revenue in 2021?"
   }
   ```
5. **Click "Execute"**

### 🔴 What Will Happen:

When you click Execute, the code will **STOP at the breakpoint** in `main.py`:

```python
@app.post("/chat")
def chat(request: QueryRequest):
    breakpoint()  # 🔴 Code stops here!
```

---

## Debugging in VS Code

When the breakpoint is hit, you'll see:

1. **Integrated Terminal** shows the debugger is paused
2. **Left sidebar** shows variables and their values
3. **Watch expressions** let you inspect data

### Common Debug Actions:

| Keyboard | Action |
|----------|--------|
| **F10** | Step over (execute current line) |
| **F11** | Step into (go inside function calls) |
| **Shift+F11** | Step out (exit current function) |
| **F5** | Continue (resume execution until next breakpoint) |
| **Shift+F5** | Stop debugging |

### Inspect Variables:

In the **Debug Console** (at the bottom), you can type:
```python
# See what the frontend sent
request.query

# Check the response
response
```

---

## Adding More Breakpoints

To add a breakpoint anywhere in the code:

1. **Click** on the line number in the editor (a red dot appears)
2. Or use keyboard: **Ctrl+Shift+B** to toggle breakpoint

### Example - Debug Vector Search:

Edit [QueryProcessor.py](QueryProcessor.py#L10):

```python
def process_user_query(query):
    breakpoint()  # 🔴 Stop here to inspect query
    
    # Embed the query
    query_vector = embed_user_query(query)
    breakpoint()  # 🔴 Check if embedding worked
    
    # Search in Pinecone
    chunks = search_in_pinecone(query_vector)
    breakpoint()  # 🔴 Verify chunks retrieved
    
    return query_llm_with_context(query, chunks)
```

---

## Debugging Flow for Your RAG System

### Full Debug Journey:

```
1. Frontend sends query via axios.post() to http://localhost:8000/chat
   ↓ 🔴 BREAKPOINT 1 - in main.py chat() function
   
2. Backend receives QueryRequest object
   ↓ 🔴 BREAKPOINT 2 - inspect request.query
   
3. QueryProcessor.py: process_user_query(query) is called
   ↓ 🔴 BREAKPOINT 3 - check query value
   
4. embedder.py: Query is embedded to vector
   ↓ 🔴 BREAKPOINT 4 - verify vector dimensions (should be 1536)
   
5. vectorstore.py: Search Pinecone for matching chunks
   ↓ 🔴 BREAKPOINT 5 - see what chunks were retrieved
   
6. llm.py: Pass chunks to LLM
   ↓ 🔴 BREAKPOINT 6 - check context being sent to LLM
   
7. LLM generates response
   ↓ 🔴 BREAKPOINT 7 - inspect LLM response
   
8. main.py: Return response to frontend
   ↓ Frontend displays message in chat ✅
```

---

## Common Issues & Solutions

### ❌ "Port 8000 already in use"

**Solution**: Kill the existing process:
```powershell
# Find process on port 8000
netstat -ano | findstr :8000

# Kill it (replace PID with actual number)
taskkill /PID <PID> /F
```

### ❌ "No module named 'module_name'"

**Solution**: Install missing dependencies:
```bash
python -m pip install -r requirements.txt
```

### ❌ Breakpoint not hit

**Possible causes**:
- Backend not running - check the terminal
- Different endpoint being called - verify in DevTools Network tab
- Wrong file being debugged - check the file path in launch.json

### ❌ "The backend appears to not be running"

The frontend is looking for:
- POST `http://localhost:8000/chat` (API endpoint)
- Make sure the backend debug session is active

---

## Key Files for Debugging

| File | Purpose |
|------|---------|
| [main.py](main.py) | FastAPI backend with `/chat` endpoint |
| [QueryProcessor.py](QueryProcessor.py) | Orchestrates the query processing |
| [embedder.py](embedder.py) | Embeds queries to vectors |
| [vectorstore.py](vectorstore.py) | Searches Pinecone |
| [llm.py](llm.py) | Calls OpenAI API |
| [debug_ui_flow.py](debug_ui_flow.py) | Simulates complete UI-to-LLM flow |

---

## Example Debug Session

### Setup:
1. Open [main.py](main.py)
2. Click on line 39 (the `breakpoint()` line) to confirm red dot
3. Go to Run → Select "Debug FastAPI Backend"
4. Press F5

### Testing:
1. Browser opens to http://localhost:8000/docs
2. Scroll to `/chat` endpoint
3. Click "Try it out"
4. Enter: `{"query": "What is the revenue in 2021?"}`
5. Click "Execute"

### Debugging:
1. VS Code pauses at breakpoint
2. Look at **Variables** panel on left → see `request` object
3. Inspect `request.query` in Debug Console
4. Press **F5** to continue to next breakpoint
5. Watch the flow through QueryProcessor → vectorstore → llm

---

## Frontend Connection

Once backend is running, the frontend (React) will:

1. **Stop getting connection refused errors** at `/chat`
2. **Receive proper responses** from the backend
3. **Display messages** in the chat interface

The WebSocket errors for `ws://localhost:3000/ws` are expected - those are for the React dev server only (hot reload), not needed for functionality.

---

## Next Steps

After debugging and confirming the backend works:

1. ✅ Test with Swagger UI
2. ✅ Start React frontend: `npm start` in `frontend/` folder
3. ✅ Test end-to-end through the chat interface

