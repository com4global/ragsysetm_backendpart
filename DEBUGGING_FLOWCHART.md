# 📊 DEBUGGING SETUP FLOWCHART

## Complete Flow: From Frontend Request to Backend Debug

```
╔═══════════════════════════════════════════════════════════════════╗
║                  START: You Press F5 in VS Code                   ║
╚═══════════════════════════════════════════════════════════════════╝
                              ↓
┌───────────────────────────────────────────────────────────────────┐
│ 🚀 VS Code Runs Debug Config from .vscode/launch.json             │
│    - Launches: python -m uvicorn main:app --reload               │
│    - With: debugpy listening on localhost:5678                   │
│    - Port: 8000 (HTTP)                                           │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ✅ Backend Started: http://127.0.0.1:8000                        │
│    Terminal shows: "Uvicorn running on..."                       │
│    Status: Waiting for requests                                  │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 🌐 Open Browser: http://localhost:8000/docs                      │
│    (Swagger UI - FastAPI auto-generated docs)                    │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 📋 Find /chat Endpoint in Swagger UI                              │
│    - Scroll to "/chat"                                            │
│    - Method: POST                                                 │
│    - Description: Process user query through RAG pipeline         │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ▶️  Click "Try it out" Button                                     │
│    Request body editor appears                                   │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ✏️  Enter Test Query in Request Body                              │
│                                                                   │
│    {                                                              │
│      "query": "What is the revenue in 2021?"                     │
│    }                                                              │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ▶️  Click "Execute" Button                                        │
│    Sends POST request to backend                                 │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 📡 Request Travels to Backend                                     │
│    POST http://localhost:8000/chat                               │
│    Body: {"query": "What is the revenue in 2021?"}               │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 🔴 BACKEND RECEIVES REQUEST AT /chat ENDPOINT                    │
│                                                                   │
│    @app.post("/chat")                                            │
│    def chat(request: QueryRequest):                              │
│        breakpoint()  ← 🔴 CODE STOPS HERE                        │
│                                                                   │
│    VS Code pauses execution                                      │
│    Shows: Orange highlight on line 39                            │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 📊 YOU CAN NOW INSPECT                                            │
│                                                                   │
│    Left Panel (Variables):                                       │
│    ├─ request                                                    │
│    │  ├─ query: "What is the revenue in 2021?"                 │
│    │  └─ ...other fields                                        │
│    └─ ... (other local variables)                               │
│                                                                   │
│    Bottom Panel (Debug Console):                                 │
│    Type commands:                                                │
│    >>> request.query                                             │
│    'What is the revenue in 2021?'                                │
│                                                                   │
│    Top Toolbar:                                                  │
│    ┌─ F5 (Continue) ─ F10 (Step) ─ F11 (Into) ─ ...            │
│    └─ Step Shift+F11 (Out) ─ Stop (Shift+F5)                    │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
            YOU CAN DECIDE:
            ├─→ [F10] Step over to next line
            ├─→ [F11] Step into process_user_query()
            ├─→ [F5] Continue execution
            └─→ Add more breakpoints to explore

            (We choose F5 to continue for now)

            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ▶️  Press F5 - Code Continues                                     │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 🔄 Pipeline Executes (No more breakpoints in default config)     │
│                                                                   │
│    try:                                                           │
│        response = process_user_query(request.query)              │
│        ├─ embedder.py: Embed query to vector                    │
│        ├─ vectorstore.py: Search Pinecone for chunks            │
│        ├─ llm.py: Send chunks to OpenAI LLM                     │
│        └─ Return: LLM response                                    │
│                                                                   │
│    return QueryResponse(                                          │
│        response=response,                                         │
│        query=request.query                                        │
│    )                                                              │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ ✅ Response Generated                                              │
│    {                                                              │
│      "response": "The revenue in 2021 for BMW Group was          │
│                    €111,239 million.",                            │
│      "query": "What is the revenue in 2021?"                     │
│    }                                                              │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 📤 Response Sent Back to Browser                                  │
│    HTTP 200 OK                                                    │
│    Body: {response: "...", query: "..."}                         │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
┌───────────────────────────────────────────────────────────────────┐
│ 🌐 Browser Receives Response                                      │
│    Swagger UI displays:                                           │
│                                                                   │
│    ┌─────────────────────────────────────────┐                   │
│    │ Response body:                          │                   │
│    │ {                                       │                   │
│    │   "response": "The revenue in 2021     │                   │
│    │               for BMW Group was        │                   │
│    │               €111,239 million.",      │                   │
│    │   "query": "What is the revenue in    │                   │
│    │            2021?"                      │                   │
│    │ }                                       │                   │
│    │                                         │                   │
│    │ Server response code: 200               │                   │
│    └─────────────────────────────────────────┘                   │
└───────────┬────────────────────────────────────────────────────────┘
            ↓
╔═══════════════════════════════════════════════════════════════════╗
║                          ✅ SUCCESS!                              ║
║                                                                   ║
║  You successfully:                                               ║
║  • Started debugger with F5                                      ║
║  • Sent query via Swagger UI                                     ║
║  • Hit breakpoint in backend                                     ║
║  • Inspected variables                                           ║
║  • Continued execution                                           ║
║  • Got response from LLM                                         ║
║                                                                  ║
║  Backend debugging setup is COMPLETE & WORKING! 🚀              ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Debug Session Timeline

```
TIME    EVENT                              YOUR ACTION
───────────────────────────────────────────────────────────────
0:00    Press F5                           ← Start debugging
0:02    Backend starts                     ✅ Terminal shows "running"
0:03    Browser: localhost:8000/docs       → Open Swagger UI
0:05    Find /chat endpoint                → Click "Try it out"
0:07    Enter query                        → Type test query
0:08    Click "Execute"                    → Send request
0:09    🔴 BREAKPOINT HIT                  ← Code pauses
0:10    Inspect variables                  → Look at request object
0:12    Click F5                           → Continue execution
0:13    Pipeline processing                - Backend runs
0:20    Response generated                 - LLM returns answer
0:21    Browser displays response          ✅ You see the answer
0:22    Debug session still active         → Can test again
```

---

## Decision Tree: What to Do at Breakpoint

```
                    🔴 BREAKPOINT HIT
                            ↓
                   What do you want?
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
    Just look around   Step through code   Go deep into functions
    (press F5)         (press F10)          (press F11)
        ↓                   ↓                   ↓
    F5 = Continue      F10 = Next line      F11 = Enter function
    ↓ Execute rest     ↓ Step by step       ↓ Debug internals
    ✅ Get response    ✅ Watch flow        ✅ Find issues
```

---

## Where to Add More Breakpoints

To understand the full pipeline better, add breakpoints at:

```
main.py                   🔴 Line 39 (already added)
        ↓
QueryProcessor.py         Add 🔴 to see function calls
        ↓
embedder.py               Add 🔴 to check embedding
        ↓
vectorstore.py            Add 🔴 to see chunks found
        ↓
llm.py                    Add 🔴 to inspect LLM response
```

Just click line numbers to add red dots! ✅

---

## Swagger UI Tips

### Find /chat endpoint
```
Ctrl+F in Swagger UI and search for "chat"
Or scroll down to find it
```

### Request format
```json
{
  "query": "Your question here"
}
```

### Response format
```json
{
  "response": "Answer from LLM",
  "query": "Your question"
}
```

### Test different queries
```
"What is the revenue in 2021?"
"Tell me about the HR policy"
"What is the cost of sales?"
```

---

## Keyboard Shortcuts Cheat Sheet

```
ACTION                  SHORTCUT
────────────────────────────────────
Open Run & Debug        Ctrl+Shift+D
Start Debugging         F5
Stop Debugging          Shift+F5
Step Over              F10
Step Into              F11
Step Out               Shift+F11
Toggle Breakpoint      F9 (on current line)
Add Watch              Right-click variable
```

---

## You're Now Ready!

The diagram above shows the complete flow from your F5 press to seeing the response. 

**Next: Press F5 and follow the flow!** 🚀

