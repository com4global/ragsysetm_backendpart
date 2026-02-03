# 🎯 UI-to-LLM Debugging Suite - Complete Overview

## What You Asked For

> "When user write prompt in the UI interface, can you help me debug: how it hits and looks into the backend, and passes and responds accordingly"

## What I Created For You

A **complete debugging suite** to trace the journey of a user query from UI → Backend → LLM → UI Response.

---

## 📦 New Debugging Tools Created

### 1. **debug_ui_flow.py** (🚀 START HERE)
**Purpose:** Automatic tracer for complete request flow

```bash
python debug_ui_flow.py
```

**What it shows:**
- Step 1: Frontend sends query ✅
- Step 2: Backend receives ✅
- Step 3: Query embedding ✅
- Step 4: Vector search ✅
- Step 5: LLM response ✅
- Step 6-8: Response returns ✅

**Output Example:**
```
✅ COMPLETE FLOW SUCCESSFUL!
(or identifies exactly which step failed)
```

---

### 2. **DEBUG_UI_TO_LLM_FLOW.md** (📖 Complete Guide)
**Purpose:** Detailed step-by-step guide with code examples

**Contains:**
- Complete flow diagram
- How to debug each component independently
- Code to add logging to backend
- Browser DevTools instructions
- API testing examples

**Use when:** You need detailed instructions for a specific step

---

### 3. **UI_TROUBLESHOOTING_GUIDE.md** (🔧 Problem Solver)
**Purpose:** Solutions for 8 common issues

**Problems covered:**
1. Backend running but no response
2. Missing modules (openai, pinecone)
3. Missing .env file
4. No vectors in Pinecone
5. Generic "I cannot find" responses
6. CORS errors
7. Request timeouts
8. 500 Internal Server Error

**Use when:** Something isn't working and you need a fix

---

### 4. **DEBUG_COMPLETE_GUIDE.md** (📚 Full Reference)
**Purpose:** Complete end-to-end debugging reference

**Includes:**
- Complete flow diagram with detailed annotations
- 3-step debugging process
- Quick verification checklist
- Real-time monitoring setup
- Success test procedures

**Use when:** You want the complete picture

---

### 5. **DEBUG_QUICK_REFERENCE.md** (⚡ Quick Lookup)
**Purpose:** Visual quick reference with decision trees

**Features:**
- Debugging decision tree
- Common failures & instant fixes
- Test scenarios (working vs broken)
- Browser DevTools guide
- Emergency checklist

**Use when:** You need quick answers

---

### 6. **request_monitor.py** (📊 Real-Time Monitoring)
**Purpose:** Monitor requests/responses in real-time

**Features:**
- Logs all HTTP requests
- Logs all HTTP responses
- Logs errors with full context
- Saves to log file
- Pretty-prints data

**How to use:**
See instructions in file for adding to main.py

---

## 🎬 How to Use These Tools

### Scenario 1: "My query reaches backend but no response"

```bash
# Run this:
python debug_ui_flow.py

# It will show which step fails
# Then check the failing step's guide:
# - Step 3 fails? → pip install openai
# - Step 4 fails? → Check .env PINECONE_API_KEY
# - Step 5 fails? → Check .env OPENAI_API_KEY
```

### Scenario 2: "UI shows response but it's wrong"

```bash
# Check what data LLM received:
# 1. Edit llm.py to add print statements
# 2. Type query in UI
# 3. Check backend terminal for debug output
# 4. See what chunks were retrieved
# 5. That's your context - is it correct?
```

### Scenario 3: "No request reaches backend at all"

```bash
# 1. Open F12 in browser
# 2. Go to Network tab
# 3. Type query
# 4. Look for POST request to /chat
# If no request appears: JavaScript error (check Console tab)
# If request shows 500: Backend error (check main.py logs)
```

### Scenario 4: "Everything looks correct but I'm not sure"

```bash
# Run complete verification:
python debug_ui_flow.py

# This proves all components work together
```

---

## 📍 Complete Request Flow (What Happens)

```
STEP 1: User Types in UI
   Input: "What is the revenue in 2021?"
   ↓
STEP 2: Frontend Sends Request
   axios.post('http://localhost:8000/chat', {query: "..."})
   ↓
STEP 3: Backend Receives
   main.py /chat endpoint
   Parses: QueryRequest(query="...")
   ↓
STEP 4: QueryProcessor.process_user_query()
   ├─ Embeds query (embedder.py)
   │  Input: "What is the revenue..."
   │  Output: Vector [0.024, -0.018, ...] (1536 dims)
   │
   ├─ Searches Pinecone (vectorstore.py)
   │  Input: Query vector
   │  Output: 4 matching chunks from documents
   │
   └─ Calls OpenAI LLM (llm.py)
      Input: Query + Matched chunks
      Output: "The revenue in 2021 was €95,476 million."
   ↓
STEP 5: Backend Returns Response
   QueryResponse(
      response="The revenue in 2021 was €95,476 million.",
      query="What is the revenue in 2021?"
   )
   ↓
STEP 6: Frontend Receives
   axios response caught
   ↓
STEP 7: Frontend Updates UI
   setMessages([...prev, botMessage])
   ↓
STEP 8: User Sees Response
   Chat bubble: "The revenue in 2021 was €95,476 million."
```

---

## 🔍 Key Debugging Commands

```bash
# Test backend API
curl http://localhost:8000/

# Test /chat endpoint
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue?"}'

# Check dependencies
python -c "from openai import OpenAI; print('✅')"
python -c "from pinecone import Pinecone; print('✅')"

# Check .env
cat .env      # Linux/Mac
type .env     # Windows

# Check vector store
python -c "from vectorstore import index; print(index.describe_index_stats())"

# Run complete flow tracer
python debug_ui_flow.py

# Test backend connection
python -c "import requests; r=requests.post('http://localhost:8000/chat', json={'query':'test'}); print(r.json())"
```

---

## 📊 Debugging Workflow

```
START
  │
  ├─→ Run: python debug_ui_flow.py
  │   │
  │   ├─ All ✅? → System works!
  │   │
  │   └─ ❌ somewhere? → Find which step
  │       │
  │       ├─ Step 3 (Embed)? → pip install openai
  │       ├─ Step 4 (Search)? → Check PINECONE_API_KEY
  │       └─ Step 5 (LLM)? → Check OPENAI_API_KEY
  │
  └─→ Still not working?
      │
      ├─ Test backend directly: curl http://localhost:8000/chat
      │
      ├─ Check browser F12 Network tab
      │
      └─ Read: DEBUG_COMPLETE_GUIDE.md or UI_TROUBLESHOOTING_GUIDE.md
```

---

## 🎓 What Each File Does

| File | Run Command | Use Case |
|------|-------------|----------|
| `debug_ui_flow.py` | `python debug_ui_flow.py` | Identify which step fails |
| `DEBUG_UI_TO_LLM_FLOW.md` | Read it | Need detailed explanations |
| `UI_TROUBLESHOOTING_GUIDE.md` | Read it | Have specific error |
| `DEBUG_COMPLETE_GUIDE.md` | Read it | Want full understanding |
| `DEBUG_QUICK_REFERENCE.md` | Read it | Need quick answers |
| `request_monitor.py` | See file for setup | Monitor real requests |

---

## ✅ Verification Checklist

Before assuming something is broken:

```
□ Backend running: curl http://localhost:8000/
□ Frontend running: Browser shows chat UI
□ .env exists with API keys
□ OpenAI API key is valid
□ Pinecone API key is valid
□ Files uploaded and processed
□ No errors in browser F12 Console
□ No CORS errors in browser
□ debug_ui_flow.py shows all ✅
```

---

## 🚀 Quick Start

1. **First:** Run the flow debugger
   ```bash
   python debug_ui_flow.py
   ```

2. **It will show:**
   - ✅ or ❌ for each step
   - Error messages if something fails
   - Next steps to fix

3. **If something fails:**
   - Read the error message
   - Check [UI_TROUBLESHOOTING_GUIDE.md](UI_TROUBLESHOOTING_GUIDE.md)
   - Find your issue in the table
   - Apply the fix

4. **Test again:**
   ```bash
   python debug_ui_flow.py
   ```

5. **When all steps pass:**
   - Backend and UI are connected ✅
   - Query gets embedded correctly ✅
   - Vector search works ✅
   - LLM generates responses ✅
   - Everything ready! 🎉

---

## 📞 Getting Help

1. **Error appears in debug output?**
   → Read the error → Check [UI_TROUBLESHOOTING_GUIDE.md](UI_TROUBLESHOOTING_GUIDE.md)

2. **Browser shows error?**
   → Open F12 Console tab → Read error → Fix it

3. **Backend logs show error?**
   → Read error → Check [DEBUG_COMPLETE_GUIDE.md](DEBUG_COMPLETE_GUIDE.md)

4. **Don't know where to start?**
   → Run: `python debug_ui_flow.py`
   → It will guide you!

---

## 🎯 Summary

I've created a **complete debugging suite** with:

✅ **Automatic Flow Tracer** - Identifies exactly which step fails
✅ **Detailed Guides** - Step-by-step instructions for each component
✅ **Troubleshooting** - Solutions for 8 common problems
✅ **Quick Reference** - Visual decision trees and checklists
✅ **Real-Time Monitor** - See requests/responses as they happen

**Start with:** `python debug_ui_flow.py`

**When it fails:** Use the guides to fix it

**Done!** 🚀
