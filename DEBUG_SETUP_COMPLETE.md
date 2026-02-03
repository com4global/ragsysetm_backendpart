# ✅ DEBUGGING SETUP COMPLETE

## What Was Fixed

### 1. ✅ Launch Configuration Fixed
- Created proper `launch.json` with "Debug FastAPI Backend" configuration
- Can now press F5 to start debugging with automatic breakpoints

### 2. ✅ Breakpoints Added
- Added `breakpoint()` in [main.py](main.py#L39) at `/chat` endpoint
- Backend will pause when you call the endpoint from Swagger UI

### 3. ✅ Dependencies Installed
- `debugpy` installed for Python debugging
- All requirements from `requirements.txt` already installed

### 4. ✅ Debug Tools Created
- [debug_backend.py](debug_backend.py) - Alternative debug launcher
- [test_backend.py](test_backend.py) - Test if backend is running
- [DEBUG_BACKEND.md](DEBUG_BACKEND.md) - Full debugging guide
- [QUICK_DEBUG.md](QUICK_DEBUG.md) - Quick reference

---

## 🎯 How to Debug Now

### Step 1: Start Debugging
```
Press: Ctrl+Shift+D (or Run → Run and Debug)
Select: "Debug FastAPI Backend"
Press: F5
```

### Step 2: Open Swagger UI
Once backend starts, go to: **http://localhost:8000/docs**

### Step 3: Test the Endpoint
1. Scroll down to find `/chat` endpoint
2. Click "Try it out"
3. Enter query:
   ```json
   {
     "query": "What is the revenue in 2021?"
   }
   ```
4. Click "Execute"

### Step 4: Hit Breakpoint
Code stops at 🔴 breakpoint in `main.py` line 39

### Step 5: Debug in VS Code
- **Left panel**: See all variables and their values
- **Bottom panel**: Debug console to inspect data
- **Top toolbar**: F5 (continue), F10 (step), F11 (into), Shift+F11 (out)

---

## 📊 What You Can Debug

### Inspect the Request
```python
# In Debug Console, type:
request.query                    # "What is the revenue in 2021?"
request                          # Full request object
```

### Follow the Flow
```
1. request arrives at /chat endpoint → 🔴 BREAKPOINT
2. process_user_query() is called
3. Query is embedded to vector (1536 dimensions)
4. Vector searched in Pinecone
5. Chunks returned
6. LLM generates response
7. Response sent back to frontend
```

### Add More Breakpoints
Click on any line number to add a red dot:
- [QueryProcessor.py](QueryProcessor.py) - Process orchestration
- [vectorstore.py](vectorstore.py) - Vector search
- [llm.py](llm.py) - LLM response generation

---

## 🔧 Debugging Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **F5** | Start debugging / Continue from breakpoint |
| **Ctrl+Shift+D** | Open Run & Debug panel |
| **F9** | Toggle breakpoint on current line |
| **F10** | Step over (execute one line) |
| **F11** | Step into (enter function) |
| **Shift+F11** | Step out (exit function) |
| **Shift+F5** | Stop debugging |

---

## 🧪 Verify Setup

To verify the backend is working, run:

```bash
python test_backend.py
```

This will test:
1. ✅ Backend is running
2. ✅ Swagger UI is accessible
3. ✅ `/chat` endpoint is working

---

## 📝 Important Notes

### Frontend Connection Errors

The frontend shows these errors (you can ignore them):
```
WebSocket connection to 'ws://localhost:3000/ws' failed
Failed to load resource: net::ERR_CONNECTION_REFUSED at :8000/chat
```

**Why?**
- WebSocket error is for React dev server (not running)
- :8000/chat error means backend wasn't running before
- Now that backend is running, connect it to React frontend

### Running React Frontend

After debugging the backend:

```bash
# Open NEW terminal window
cd frontend
npm install                  # Only needed first time
npm start                    # Starts React on http://localhost:3000
```

Then chat via: http://localhost:3000

---

## 🎓 Full Debug Example

### Scenario: User asks "What is the revenue in 2021?"

1. **User types in chat** → Frontend sends POST to /chat
2. **🔴 Breakpoint hit** in main.py
   - F5 to continue
3. **Query embedded** → 1536-dimensional vector created
   - (Optional: Add breakpoint in embedder.py to see vector)
4. **Vector searched** in Pinecone → 4 chunks found
   - (Optional: Add breakpoint in vectorstore.py to inspect chunks)
5. **LLM processes** with context → Generates response
   - (Optional: Add breakpoint in llm.py to see LLM input/output)
6. **Response returned** → Frontend displays in chat ✅

---

## 🚀 Next Steps

1. ✅ Press F5 to start debugging
2. ✅ Go to http://localhost:8000/docs
3. ✅ Test `/chat` endpoint with a query
4. ✅ Watch code execution in VS Code
5. ✅ After debugging, start React frontend with `npm start` in frontend folder
6. ✅ Chat via http://localhost:3000

---

## 📚 Reference Files

- [main.py](main.py) - FastAPI with `/chat` endpoint (has breakpoint at line 39)
- [QueryProcessor.py](QueryProcessor.py) - Query processing orchestration
- [debug_ui_flow.py](debug_ui_flow.py) - Simulates complete flow
- [debug_pipeline.py](debug_pipeline.py) - Tests RAG pipeline
- [DEBUG_BACKEND.md](DEBUG_BACKEND.md) - Full debugging documentation
- [QUICK_DEBUG.md](QUICK_DEBUG.md) - Quick reference card

---

## ❓ Troubleshooting

### "Port 8000 already in use"
```powershell
netstat -ano | findstr :8000        # Find PID
taskkill /PID <number> /F           # Kill it
```

### "Breakpoint not hit"
- Make sure F5 is running (check left panel)
- Make sure code reaches that line
- Check if breakpoint is on a valid line

### "Can't connect to localhost:8000"
- Make sure VS Code debug session is active
- Press F5 to start it
- Watch for "Server running on..." message

### "Module not found"
```bash
python -m pip install -r requirements.txt
```

---

✅ **Setup Complete!** You're ready to debug. Press F5 to start.

