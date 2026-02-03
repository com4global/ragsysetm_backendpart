# 🔴 QUICK DEBUG REFERENCE

## Start Debugging (3 Steps)

1. **Press Ctrl+Shift+D** (Run & Debug)
2. **Select "Debug FastAPI Backend"** from dropdown
3. **Press F5** to start

Backend starts on: **http://localhost:8000/docs**

---

## Test the Endpoint

1. Open http://localhost:8000/docs
2. Click `/chat` endpoint
3. Click "Try it out"
4. Enter:
   ```json
   {
     "query": "What is the revenue in 2021?"
   }
   ```
5. Click "Execute"

**Result**: Code stops at 🔴 breakpoint in `main.py` line 39

---

## Debug Controls

| Key | Action |
|-----|--------|
| F5 | Resume / Continue |
| F10 | Step over (next line) |
| F11 | Step into (enter function) |
| Shift+F11 | Step out (exit function) |
| Shift+F5 | Stop debugging |

---

## Where to Look

**Variables Panel (Left)**: See all variables
- `request` - What frontend sent
- `response` - What backend will send

**Debug Console (Bottom)**: Type commands
```python
request.query                    # See the query
response                         # See the response
len(chunks)                      # How many chunks found
```

---

## Current Breakpoints

✅ **Line 39 in main.py** - `/chat` endpoint

To add more breakpoints:
- Click line number to add red dot
- Breakpoint fires when code reaches that line

---

## What Gets Debugged

```
Frontend (React)
    ↓ axios.post('http://localhost:8000/chat')
    ↓ 🔴 BREAKPOINT HERE (inspect request)
Backend (FastAPI)
    ↓ Embeds query
    ↓ Searches Pinecone
    ↓ Calls LLM
    ↓ Returns response
Frontend (React)
    ↓ Displays in chat
```

---

## Frontend Connection Fix

❌ **Before**: Connection refused at :8000/chat
✅ **Now**: Backend running, ready to receive requests

**Error messages expected** (can ignore):
- WebSocket ws://localhost:3000/ws - This is React dev server, not used for chat

---

## Next: Start Frontend

After debugging backend, start React frontend:

```bash
# Open new terminal
cd frontend
npm start
```

Then open browser to http://localhost:3000 and chat!

---

## Need Help?

See [DEBUG_BACKEND.md](DEBUG_BACKEND.md) for full guide with examples and troubleshooting.
