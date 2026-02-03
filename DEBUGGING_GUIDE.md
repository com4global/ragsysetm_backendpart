# RAG Pipeline Debugging Guide
## Step-by-Step Verification for File Upload → Processing → Q&A

---

## 📋 Overview

This guide helps you debug the entire pipeline:
```
Upload File → Read File → Chunk Text → Create Embeddings → Store in Pinecone → Query → LLM Response
```

---

## 🚀 Quick Start Debugging

### Run the Complete Debug Script

```bash
# From the project root
python debug_pipeline.py
```

**OR modify and run specific steps:**

```python
from debug_pipeline import *

# Test a specific file
run_full_debug("financial-statements-2021.xlsx", "What was the revenue?")
```

---

## 🔍 Detailed Step-by-Step Debugging

### STEP 1: Verify File Exists & Is Readable

**What to check:**
- File is in `./resources/` folder
- File extension is supported

**Debug command:**
```bash
# List all files in resources folder
ls ./resources/
# OR on Windows PowerShell
Get-ChildItem .\resources\
```

**Expected output:**
```
✅ File exists: ./resources/financial-statements-2021.xlsx
📊 File size: 245892 bytes
📝 File type: excel
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| File not found | Upload file first via `/api/upload` endpoint |
| Wrong format | File must be .xlsx, .pdf, .csv, .txt, .docx, or .xml |
| File corrupted | Try uploading again |

---

### STEP 2: Verify File Reading & Content Extraction

**What to check:**
- File is being read correctly
- Content is extracted properly

**Debug command:**
```python
from debug_pipeline import debug_step_2_read_file

pages, file_type = debug_step_2_read_file("financial-statements-2021.xlsx")
print(f"Pages extracted: {len(pages)}")
print(f"First page preview: {pages[0][:300]}")
```

**Expected output:**
```
✅ File read successfully!
📄 Pages extracted: 3
📋 File type detected: excel

📖 Sample of first page:
   Sheet: Financial Data
   Revenue | 2021 | 2022 | 2023
   Q1 | 1000000 | 1100000 | 1200000
   ...
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| 0 pages extracted | File may be empty or encoding issue |
| Error reading file | Check file format and encoding |
| Special characters garbled | May be encoding issue with text extraction |

---

### STEP 3: Verify Text Chunking

**What to check:**
- Text is split into chunks of correct size
- Overlap between chunks is working

**Debug command:**
```python
from debug_pipeline import debug_step_2_read_file, debug_step_3_chunking

pages, _ = debug_step_2_read_file("financial-statements-2021.xlsx")
chunks = debug_step_3_chunking(pages)
print(f"Total chunks: {len(chunks)}")
for i, chunk in enumerate(chunks[:2]):
    print(f"Chunk {i}: {len(chunk)} chars")
```

**Expected output:**
```
✅ Chunking successful!
📦 Total chunks created: 12
📊 Chunk size stats:
   Min: 750 chars
   Max: 900 chars
   Avg: 850 chars
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| Very few chunks | File content may be small |
| Chunks too small | Increase chunk_size parameter (default 900) |
| Loss of context | Check chunk_overlap setting (default 150) |

---

### STEP 4: Verify Embeddings Generation

**What to check:**
- Each chunk converts to a 1536-dimensional vector
- Embeddings are generated without errors

**Debug command:**
```python
from debug_pipeline import debug_step_3_chunking, debug_step_4_embeddings, debug_step_2_read_file

pages, _ = debug_step_2_read_file("financial-statements-2021.xlsx")
chunks = debug_step_3_chunking(pages)
embeddings = debug_step_4_embeddings(chunks)
print(f"Total embeddings: {len(embeddings)}")
print(f"Embedding dimensions: {len(embeddings[0])}")
print(f"Sample values: {embeddings[0][:5]}")
```

**Expected output:**
```
✅ Embeddings generated successfully!
🧠 Total embeddings: 12
📏 Embedding dimensions: 1536
🔢 First embedding sample (first 10 values):
   [0.0496425368, 0.00166146422, 0.0359480456, ...]
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| API error | Check OpenAI API key in .env |
| Rate limited | Wait and retry |
| Different dimensions | Verify embedding model (should be 1536 for text-embedding-3-small) |

---

### STEP 5: Verify Pinecone Storage

**What to check:**
- Vectors are stored in Pinecone
- Correct namespace is used
- Record count increased

**Debug command:**
```python
from debug_pipeline import debug_step_5_pinecone_storage

debug_step_5_pinecone_storage("financial-statements-2021.xlsx", "excel")
```

**Expected output:**
```
✅ Connected to Pinecone!
📊 Total vectors in index: 50
📂 Namespaces in index: ['__default__', 'excel', 'pdf']

✅ Namespace 'excel' found!
   Vectors in namespace: 12

📋 All namespaces and counts:
   __default__: 38 vectors
   excel: 12 vectors
   pdf: 0 vectors
```

**How to verify in Pinecone UI:**
1. Go to https://app.pinecone.io/
2. Click your index: `hr-assistant-index`
3. Check "Record Count" should have increased
4. Click "Browse Vectors" tab
5. Filter by namespace to see your file's vectors

**Common issues:**
| Issue | Solution |
|-------|----------|
| Connection error | Check PINECONE_API_KEY in .env |
| Vectors not appearing | File may not have been processed (call `/api/process-file`) |
| Wrong namespace | Verify file_type matches namespace used |

---

### STEP 6: Test Query Retrieval

**What to check:**
- Query is embedded correctly
- Relevant chunks are retrieved
- Similarity scores are reasonable

**Debug command:**
```python
from debug_pipeline import debug_step_6_retrieval

query = "What was the revenue in 2021?"
namespace = "excel"  # Use the file type
matched_chunks = debug_step_6_retrieval(query, namespace)

if matched_chunks:
    print(f"Retrieved {len(matched_chunks)} chunks")
    for chunk in matched_chunks:
        print(f"- {chunk[:100]}...")
```

**Expected output:**
```
✅ Search completed!
📌 Matched chunks found: 4

   MATCH 1:
   Sheet: Financial Data
   Revenue | 2021 | 2022 | 2023
   Q1 | 1000000 | 1100000...

   MATCH 2:
   Q2 | 950000 | 1050000...
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| 0 matches found | Query may be too different from document content, try different keywords |
| Wrong matches | Adjust query to be more specific |
| Only retrieving from default namespace | Try searching without namespace filter |

**Debug different namespaces:**
```python
# Search across all files
matched_chunks = debug_step_6_retrieval(query, namespace="")

# Search only in specific file type
matched_chunks = debug_step_6_retrieval(query, namespace="excel")
```

---

### STEP 7: Test LLM Response

**What to check:**
- LLM receives correct context
- Response is generated properly
- Response addresses the question

**Debug command:**
```python
from debug_pipeline import debug_step_6_retrieval, debug_step_7_llm_response

query = "What was the revenue in 2021?"
matched_chunks = debug_step_6_retrieval(query, "excel")
response = debug_step_7_llm_response(query, matched_chunks)
print(f"Response: {response}")
```

**Expected output:**
```
✅ LLM response generated!

📝 RESPONSE:
Based on the financial data, the revenue in 2021 was:
- Q1: $1,000,000
- Q2: $950,000
- Q3: $1,100,000
- Q4: $1,200,000
- Total: $4,250,000
```

**Common issues:**
| Issue | Solution |
|-------|----------|
| Empty response | Chunks may be empty or malformed |
| "No information" response | Retrieved chunks don't contain answer, check retrieval step |
| Generic response | Try rephrasing question or adding more context |

---

### STEP 8: Full End-to-End Test

**What to check:**
- Complete pipeline works
- Query returns meaningful answer
- No errors in any step

**Debug command:**
```python
from debug_pipeline import run_full_debug

# Run complete debugging
run_full_debug("financial-statements-2021.xlsx", "What was the revenue in 2021?")
```

**This will run steps 1-8 and show:**
✅ File reading
✅ Chunking statistics
✅ Embedding generation
✅ Pinecone storage verification
✅ Retrieval test
✅ LLM response
✅ Metadata check

---

## 🔧 Debugging Specific Issues

### Issue: File uploaded but system says "not processed"

**Root cause:** File uploaded but `/api/process-file` endpoint not called

**Solution:**
```bash
# Option 1: Via API
curl -X POST "http://127.0.0.1:8000/api/process-file?filename=financial-statements-2021.xlsx"

# Option 2: Direct Python
from dataprocessor import process_file
result = process_file("./resources/financial-statements-2021.xlsx")
print(result)
```

---

### Issue: Query returns old data, not new file

**Root cause:** New file chunks stored in different namespace, query only searches default

**Solution:**
```python
# Test with specific namespace
from debug_pipeline import debug_step_6_retrieval

query = "revenue"
# Search in specific namespace
matches = debug_step_6_retrieval(query, namespace="excel")

# OR search all namespaces
matches = debug_step_6_retrieval(query, namespace="")
```

---

### Issue: Retrieved chunks not relevant

**Root causes:**
1. Query too vague
2. Document doesn't contain information
3. Embedding model not capturing meaning

**Solutions:**
```python
# Try more specific query
query1 = "financial revenue 2021"  # More specific
query2 = "What is the total annual revenue?"  # Add context

# Test both
for q in [query1, query2]:
    from debug_pipeline import debug_step_6_retrieval
    matches = debug_step_6_retrieval(q, namespace="excel")
    print(f"Query: {q} → {len(matches)} matches")
```

---

### Issue: Pinecone shows 0 vectors

**Root causes:**
1. File never uploaded
2. File uploaded but not processed
3. Processing failed silently

**Solutions:**
```python
# Check file metadata
from file_manager import get_all_files
files = get_all_files()
for f in files:
    print(f"{f['filename']}: {f.get('chunks_created', 0)} chunks")

# If 0 chunks, manually process
from dataprocessor import process_file
result = process_file("./resources/financial-statements-2021.xlsx")
print(f"Processed: {result['chunks_created']} chunks created")
```

---

## 📊 Monitoring Dashboard

**Quick Status Check:**
```python
from debug_pipeline import debug_metadata
debug_metadata()
```

**Expected output shows:**
- All uploaded files
- How many chunks each has
- Total statistics

```
✅ Files uploaded: 2
   📄 HRPolicy.pdf
      Type: pdf
      Size: 1024000 bytes
      Chunks: 38
   📄 financial-statements-2021.xlsx
      Type: excel
      Size: 245892 bytes
      Chunks: 12

📊 Statistics:
   Total files: 2
   Total chunks: 50
```

---

## 🎯 Testing Workflow

### For Financial Statements File:

```python
from debug_pipeline import run_full_debug

# Test queries
queries = [
    "What was the revenue in 2021?",
    "Show me the Q1 2021 revenue",
    "What is the total annual revenue?",
    "Compare 2021 and 2022 revenue"
]

for query in queries:
    run_full_debug("financial-statements-2021.xlsx", query)
    print("\n" + "="*60 + "\n")
```

### For HR Policy File:

```python
from debug_pipeline import run_full_debug

queries = [
    "What is the work timing policy?",
    "What are leave policies?",
    "What is the salary review process?"
]

for query in queries:
    run_full_debug("HRPolicy.pdf", query)
```

---

## 🚨 Critical Checklist

Before assuming the system doesn't work, verify:

- [ ] File uploaded successfully (visible in resources folder)
- [ ] File processed successfully (call `/api/process-file`)
- [ ] Pinecone index has vectors (check in Pinecone UI)
- [ ] Query is specific enough (includes keywords from document)
- [ ] API keys configured (.env file has PINECONE_API_KEY, OPENAI_API_KEY)
- [ ] Vector dimensions match (should be 1536)
- [ ] Embedding model is correct (text-embedding-3-small)

---

## 🌐 UI-to-Backend Flow Debugging

If user types a query in the UI but doesn't get a response, use this guide:

### Complete Flow Diagram:
```
User Types in UI → Frontend (ChatInterface.js) → Backend (/chat) → 
QueryProcessor → Embedder → Pinecone Search → LLM → Response
```

### Run Complete Flow Debugger:
```bash
python debug_ui_flow.py
```

This traces each step:
1. ✅ UI sends query to backend
2. ✅ Backend receives request
3. ✅ Query is embedded (embedder.py)
4. ✅ Vector store searches (vectorstore.py)
5. ✅ LLM generates response (llm.py)
6. ✅ Response returned to frontend
7. ✅ UI displays message

**Expected output:**
```
✅ COMPLETE FLOW SUCCESSFUL!
```

### Monitor Backend Requests (Real-Time):

Add logging to [main.py](main.py) `/chat` endpoint:

```python
@app.post("/chat")
def chat(request: QueryRequest):
    """Process user query through the RAG pipeline"""
    print(f"\n🔵 [BACKEND] Received query: '{request.query}'")
    
    try:
        print(f"   Calling QueryProcessor.process_user_query()...")
        response = process_user_query(request.query)
        
        print(f"   ✅ Generated response: '{response[:100]}...'")
        return QueryResponse(response=response, query=request.query)
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
```

### Browser Network Debugging:

1. Open browser (Chrome/Firefox)
2. Press F12 → Network tab
3. Type query in chat UI
4. Look for POST request to `/chat`
5. Click request → Response tab to see what backend returned

### Check API Connection Status:

```bash
# Test backend is running
curl http://localhost:8000/

# Test /chat endpoint directly
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the revenue?"}'
```

---

## 📞 Getting Help

**If debugging shows:**

❌ **File read error** → Check file format and encoding
❌ **Embedding error** → Check API keys and rate limits
❌ **Pinecone error** → Check connection and index name
❌ **No matches** → Query keywords not in document
❌ **Wrong answers** → Retrieved context doesn't contain answer
❌ **Query reaches backend but no response** → Run `debug_ui_flow.py`

**Run this for complete system info:**
```python
from debug_pipeline import debug_metadata
from vectorstore import index

# File status
debug_metadata()

# Pinecone status
stats = index.describe_index_stats()
print(f"\nPinecone vectors: {stats.total_vector_count}")
print(f"Namespaces: {list(stats.namespaces.keys())}")
```

