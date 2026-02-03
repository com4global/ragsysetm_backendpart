# ✅ SETUP VERIFICATION CHECKLIST

## Before You Start Debugging

- [ ] You have VS Code open with the RAG_HR_ASSISTANT workspace
- [ ] Python virtual environment is activated (.myenv)
- [ ] All dependencies installed (pip install -r requirements.txt)
- [ ] .env file has OPENAI_API_KEY and PINECONE_API_KEY set

## Launch Configuration

- [ ] `.vscode/launch.json` exists and has "Debug FastAPI Backend" option
- [ ] No syntax errors in launch.json
- [ ] Debugpy is installed (`pip install debugpy`)

## Breakpoint Setup

- [ ] [main.py](main.py#L39) has `breakpoint()` at line 39 in `/chat` endpoint
- [ ] Red dot appears on line 39 when you click it

## Starting Debugging

- [ ] Press **Ctrl+Shift+D** to open Run & Debug
- [ ] Dropdown shows "Debug FastAPI Backend"
- [ ] Green play button visible
- [ ] Press **F5** to start

## Backend Running

- [ ] Integrated Terminal shows "Uvicorn running on http://127.0.0.1:8000"
- [ ] No error messages in terminal
- [ ] Terminal is ready (not frozen/stuck)

## Testing with Swagger UI

- [ ] Open browser to http://localhost:8000/docs
- [ ] Swagger UI loads successfully
- [ ] Find `/chat` endpoint in the list
- [ ] Click "Try it out" button appears

## Send Test Request

- [ ] Click "Try it out" for /chat endpoint
- [ ] Request body shows input field
- [ ] Enter test query:
   ```json
   {
     "query": "What is the revenue in 2021?"
   }
   ```
- [ ] "Execute" button is available

## Breakpoint Hit

- [ ] Click "Execute" in Swagger UI
- [ ] Code pauses at line 39 in main.py (orange highlight bar)
- [ ] Left panel shows "Variables" section
- [ ] Debug toolbar appears at top of editor
- [ ] Terminal shows "[Breakpoint]" message

## Debug Controls Available

- [ ] F5 button works (continue)
- [ ] F10 button works (step over)
- [ ] F11 button works (step into)
- [ ] Shift+F11 button works (step out)
- [ ] Shift+F5 button works (stop debugging)

## Inspect Variables

- [ ] Left panel shows `request` variable
- [ ] Can expand `request` to see contents
- [ ] Can see `request.query` value
- [ ] Debug Console (bottom) accepts Python commands

## Continue Execution

- [ ] Press F5 to continue
- [ ] Code runs through:
   - [ ] Embedding query
   - [ ] Searching Pinecone
   - [ ] Calling LLM API
   - [ ] Returning response
- [ ] Swagger UI shows response
- [ ] Response matches expected output

## Final Verification

- [ ] Response in Swagger UI is not an error
- [ ] Response contains financial information
- [ ] Debug session still running (can test again)
- [ ] Can repeat test multiple times without issues

---

## If Any Item Is Not Checked

### ❌ Launch configuration missing?
- Create `.vscode/launch.json` with "Debug FastAPI Backend" configuration
- See [DEBUG_BACKEND.md](DEBUG_BACKEND.md#launch-configuration)

### ❌ Breakpoint not showing?
- Click directly on line 39 in main.py
- Should see red dot appear
- If not, check if line 39 contains valid Python code

### ❌ Backend won't start?
- Check terminal for error messages
- Ensure port 8000 is not in use
- Try: `netstat -ano | findstr :8000` to check

### ❌ Breakpoint not hit?
- Verify Swagger UI request was actually sent
- Check browser DevTools Network tab
- Make sure you clicked "Execute" button

### ❌ Variables not visible?
- Make sure you're stopped AT the breakpoint (not after)
- Left panel should show Variables section
- Click on the Variables tab if needed

### ❌ Debug console not working?
- Click in the bottom panel (Debug Console area)
- Type a simple command: `request`
- Press Enter to execute

---

## What Should Happen

When you press F5 and execute a query:

```
You → Browser
  ↓ POST http://localhost:8000/chat
Backend → Receives request
  ↓ 🔴 STOPS AT BREAKPOINT
You → Click F5
  ↓ (inspect variables in left panel)
Backend → Continues execution
  ↓ Embeds query
  ↓ Searches Pinecone
  ↓ Calls LLM
  ↓ Returns response
Browser → Displays response in Swagger UI ✅
```

---

## Success Indicators

✅ **You've successfully set up debugging when you can:**

1. Start debug session with F5
2. Send query from Swagger UI
3. Code pauses at breakpoint
4. View variables in left panel
5. Continue with F5
6. See correct response in Swagger UI

If all above work → ✅ **Setup complete and working!**

---

## Next Steps After Verification

1. ✅ Test multiple queries
2. ✅ Try adding more breakpoints to explore
3. ✅ Once confident, start React frontend:
   ```bash
   cd frontend
   npm start
   ```
4. ✅ End-to-end testing via http://localhost:3000

---

## Quick Troubleshooting Table

| Problem | Solution |
|---------|----------|
| Port 8000 in use | `taskkill /PID <number> /F` (find PID from netstat) |
| Breakpoint not appearing | Click line 39, wait 1 second for red dot |
| Code not pausing | Make sure you clicked "Execute" in Swagger UI |
| Variables empty | Click on Variables tab in left panel |
| Debug console not working | Click in bottom panel before typing |
| Backend won't start | Check terminal for error, try restarting F5 |
| Module not found error | Run: `pip install -r requirements.txt` |

---

## 📞 Getting Help

If something doesn't work:

1. **Read** [DEBUG_BACKEND.md](DEBUG_BACKEND.md) - Full guide
2. **Check** [QUICK_DEBUG.md](QUICK_DEBUG.md) - Quick reference
3. **Run** `python test_backend.py` - Test backend connectivity
4. **Run** `python debug_ui_flow.py` - Test full flow

---

## ✅ Checklist Complete

Once all items are checked off, you have:

- ✅ Proper debug configuration in VS Code
- ✅ Breakpoint set at /chat endpoint
- ✅ Backend running with debugger attached
- ✅ Ability to inspect variables and step through code
- ✅ Full end-to-end debugging capability

**You're ready to debug the backend!**

