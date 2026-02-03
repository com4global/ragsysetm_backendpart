# 🎯 SETUP SUMMARY - Backend Debugging Ready

## What Was Done

### ✅ Fixed launch.json Configuration
- **Before**: Had syntax errors, couldn't be used for debugging
- **After**: Proper "Debug FastAPI Backend" configuration added
- **File**: [.vscode/launch.json](.vscode/launch.json)

### ✅ Added Breakpoint to /chat Endpoint
- **Location**: [main.py](main.py#L39) - line 39
- **What it does**: Pauses code execution when frontend sends query
- **You can**: Inspect request, step through code, watch variables

### ✅ Installed debugpy
- **Purpose**: Enables Python debugging in VS Code
- **Installed via**: `pip install debugpy`

### ✅ Created Helper Files
1. [debug_backend.py](debug_backend.py) - Alternative way to run with debugger
2. [test_backend.py](test_backend.py) - Test if backend is working
3. [DEBUG_BACKEND.md](DEBUG_BACKEND.md) - Complete debugging guide
4. [QUICK_DEBUG.md](QUICK_DEBUG.md) - Quick reference card

---

## 🚀 HOW TO USE IT NOW

### The Simplest Way (3 Steps)

1. **Press Ctrl+Shift+D** to open Run & Debug panel
2. **Select "Debug FastAPI Backend"** from dropdown
3. **Press F5** to start

✅ Backend starts and waits for requests on `http://localhost:8000`

---

## 🧪 TEST IT

### Via Swagger UI (Browser)

1. Go to: **http://localhost:8000/docs**
2. Find the **`/chat`** endpoint
3. Click **"Try it out"**
4. Enter:
   ```json
   {
     "query": "What is the revenue in 2021?"
   }
   ```
5. Click **"Execute"**

### 🔴 What Happens

Code **STOPS at breakpoint** in `main.py`

You'll see:
- ⏸️ Execution paused (orange indicator on line 39)
- 📊 Variables panel (left) shows all values
- 💻 Debug console (bottom) for inspecting data
- ⌨️ Toolbar at top for stepping through code

### Resume Execution

- **F5** = Continue to next breakpoint
- **F10** = Step to next line
- **F11** = Step into function
- **Shift+F5** = Stop debugging

---

## 📊 THE DEBUG JOURNEY

```
Frontend (Chat UI)
    ↓ axios.post("http://localhost:8000/chat", {query: "..."})
    ↓
Backend (FastAPI)
    ↓
@app.post("/chat")
def chat(request):
    breakpoint()  ← 🔴 YOU ARE HERE (paused)
    
    ↓ F5 to continue
    
    # Now inside
    query_vector = embed_user_query(request.query)
    chunks = search_in_pinecone(query_vector)
    response = query_llm_with_context(request.query, chunks)
    
    ↓
Return response to frontend
    ↓
Frontend displays in chat ✅
```

---

## 🔍 WHAT YOU CAN INSPECT

While paused at breakpoint, check:

### In Variables Panel (Left)
- `request` - Contains the query from frontend
- `request.query` - The actual query string

### In Debug Console (Bottom)
Type Python commands:
```python
request.query
# Output: "What is the revenue in 2021?"

type(request)
# Output: <class 'fastapi.datastructures.FormData'>
```

### Step Through Code
- **F10**: Execute next line
- **F11**: Go inside function calls
- **Shift+F11**: Go back out

---

## 🎓 EXAMPLE SESSION

### 1. Start Debugging
```
→ Press F5
→ Terminal shows: "Uvicorn running on http://127.0.0.1:8000"
```

### 2. Open Swagger UI
```
→ Browser: http://localhost:8000/docs
→ Find /chat endpoint
→ Click "Try it out"
```

### 3. Send Request
```json
{
  "query": "What is the revenue in 2021?"
}
```

### 4. Code Pauses
```
→ VS Code shows line 39 highlighted (orange bar)
→ Orange dot on line 39 means execution paused
```

### 5. Inspect
```
→ Left panel shows variables
→ request.query = "What is the revenue in 2021?"
```

### 6. Continue
```
→ Press F5
→ Code runs through:
  - Embedding query
  - Searching Pinecone
  - Calling LLM
  - Returning response
→ Swagger UI shows: "The revenue in 2021 for the BMW Group was €111,239 million."
```

---

## 🔧 ADD MORE BREAKPOINTS

Want to debug deeper? Add breakpoints anywhere:

1. **Click line number** to add red dot
2. **Code will pause** when reaching that line

### Suggested Breakpoints

| File | Line | Purpose |
|------|------|---------|
| [QueryProcessor.py](QueryProcessor.py) | Top of functions | See function inputs |
| [vectorstore.py](vectorstore.py) | Before search | Inspect query vector |
| [vectorstore.py](vectorstore.py) | After search | See chunks retrieved |
| [llm.py](llm.py) | Before API call | Check context |
| [llm.py](llm.py) | After API call | Check LLM response |

---

## ⚠️ FRONTEND ERRORS (CAN IGNORE)

You'll see in browser console:
```
WebSocket connection to 'ws://localhost:3000/ws' failed
```

**This is OK!** Because:
- React dev server not running (not needed for backend testing)
- You're testing API directly via Swagger UI
- Frontend will work once you run `npm start` in `frontend/` folder

---

## 📝 NEXT STEPS

### After Debugging Backend

1. ✅ Verify backend works with Swagger UI
2. ✅ Test with different queries
3. ✅ Start React frontend:
   ```bash
   cd frontend
   npm start
   ```
4. ✅ Chat via: http://localhost:3000

### If Something Breaks

- Check [DEBUG_BACKEND.md](DEBUG_BACKEND.md) for troubleshooting
- Run: `python test_backend.py` to verify backend
- Check: `python debug_ui_flow.py` for full flow test

---

## 🎯 KEY FILES

| File | Purpose |
|------|---------|
| [.vscode/launch.json](.vscode/launch.json) | Debug configuration (NEW) |
| [main.py](main.py#L39) | Backend with breakpoint (UPDATED) |
| [debug_backend.py](debug_backend.py) | Alternate debug launcher (NEW) |
| [test_backend.py](test_backend.py) | Backend tester (NEW) |
| [DEBUG_BACKEND.md](DEBUG_BACKEND.md) | Full guide (NEW) |
| [QUICK_DEBUG.md](QUICK_DEBUG.md) | Quick reference (NEW) |

---

## ✅ VERIFICATION CHECKLIST

- [ ] Press F5 to start debugging
- [ ] Backend shows "Uvicorn running on http://127.0.0.1:8000"
- [ ] Open http://localhost:8000/docs
- [ ] Find `/chat` endpoint
- [ ] Click "Try it out"
- [ ] Send query: `{"query": "What is the revenue in 2021?"}`
- [ ] Code pauses at line 39 (🔴 breakpoint)
- [ ] Inspect variables in left panel
- [ ] Press F5 to continue
- [ ] Swagger UI shows response
- [ ] ✅ Everything works!

---

## 🆘 HELP

**The Backend Won't Start?**
- Check terminal for errors
- Make sure F5 is actually active (look for Debug toolbar)

**Code Never Hits Breakpoint?**
- Verify Swagger UI request is being sent
- Check that the `/chat` endpoint is being called

**Want More Debugging?**
- Read [DEBUG_BACKEND.md](DEBUG_BACKEND.md)
- Check [QUICK_DEBUG.md](QUICK_DEBUG.md)

---

✅ **YOU'RE ALL SET!** Press F5 and start debugging.

