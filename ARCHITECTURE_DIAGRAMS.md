# 🎯 Visual Architecture & Flow Diagrams

## System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         HR ASSISTANT RAG SYSTEM                           │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                      USER INTERFACE (PORT 3000)                    │  │
│  │                                                                      │  │
│  │  ┌───────────────────────┐    ┌────────────────────────────────┐  │  │
│  │  │   Chat Interface      │    │   Admin Dashboard              │  │  │
│  │  │  (localhost:3000)     │◄──►│  (localhost:3000/admin)        │  │  │
│  │  │                       │    │                                │  │  │
│  │  │ - Ask questions       │    │ - Upload files                │  │  │
│  │  │ - View responses      │    │ - Process files               │  │  │
│  │  │ - Chat history        │    │ - View statistics             │  │  │
│  │  └───────────────────────┘    │ - File management             │  │  │
│  │              │                 └────────────────────────────────┘  │  │
│  │              │                             │                       │  │
│  │              └─────────────────┬───────────┘                       │  │
│  │                                │                                   │  │
│  │                         React Router                               │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    BACKEND API (PORT 8000)                         │  │
│  │                      FastAPI Server                                │  │
│  │                                                                     │  │
│  │  /chat              /api/upload         /api/process-file          │  │
│  │   ▲                    ▲                    ▲                      │  │
│  │   │                    │                    │                      │  │
│  │   │                    │                    │                      │  │
│  │   └────────┬───────────┴────────┬──────────┘                      │  │
│  │            │                    │                                  │  │
│  │            ▼                    ▼                                  │  │
│  │       ┌─────────────┐    ┌──────────────┐                        │  │
│  │       │QueryProcessor│    │DataProcessor │                        │  │
│  │       └─────────────┘    └──────────────┘                        │  │
│  │            │                    │                                  │  │
│  │            └────────┬───────────┘                                  │  │
│  │                     │                                              │  │
│  │              ┌──────▼─────────┐                                   │  │
│  │              │ File Processor │                                   │  │
│  │              │ (Multi-format) │                                   │  │
│  │              └────────┬────────┘                                   │  │
│  │                       │                                            │  │
│  │  ┌────────────────────┴────────────────────┐                      │  │
│  │  │                                          │                      │  │
│  │  ▼                                          ▼                      │  │
│  │ ┌────────────────┐                  ┌─────────────────┐           │  │
│  │ │  Chunker       │                  │  Embedder       │           │  │
│  │ │ (Text chunks)  │                  │ (OpenAI API)    │           │  │
│  │ └────────────────┘                  └─────────────────┘           │  │
│  │                                              │                     │  │
│  │  ┌────────────────────────────────────────┬─┴──────────────┐      │  │
│  │  │                                         │                │      │  │
│  │  ▼                                         ▼                │      │  │
│  │ ┌──────────────────────┐    ┌──────────────────────────┐   │      │  │
│  │ │ FileManager (JSON)   │    │   VectorStore            │   │      │  │
│  │ │ ./resources/         │    │ (Pinecone Client)        │   │      │  │
│  │ │ .file_metadata.json  │    │                          │   │      │  │
│  │ └──────────────────────┘    └──────────────────────────┘   │      │  │
│  │                                      │                       │      │  │
│  │                                      │                       │      │  │
│  │  ┌──────────────────────────────────┴────────────────┐      │      │  │
│  │  │           LLM Module (GPT-3.5-turbo)             │      │      │  │
│  │  └────────────────────────────────────────────────────┘      │      │  │
│  │                                                             │      │  │
│  └─────────────────────────────────────────────────────────────┘      │  │
│                                                                        │  │
├───────────────────────────────────────────────────────────────────────┤  │
│                          EXTERNAL SERVICES                            │  │
│                                                                        │  │
│  ┌─────────────────────────────┐  ┌──────────────────────────────┐   │  │
│  │     OpenAI API              │  │   Pinecone Vector DB         │   │  │
│  │                             │  │                              │   │  │
│  │ - text-embedding-3-small    │  │ - Store embeddings           │   │  │
│  │ - gpt-3.5-turbo             │  │ - Semantic search            │   │  │
│  │ - 1536-dimensional vectors  │  │ - Namespaces (pdf, excel...) │   │  │
│  │                             │  │                              │   │  │
│  └─────────────────────────────┘  └──────────────────────────────┘   │  │
│                                                                        │  │
│  ┌─────────────────────────────┐                                      │  │
│  │    Local File Storage       │                                      │  │
│  │                             │                                      │  │
│  │ ./resources/                │                                      │  │
│  │ ├── HRPolicy.pdf           │                                      │  │
│  │ ├── HR_Handbook.xlsx       │                                      │  │
│  │ ├── Employee_Data.csv      │                                      │  │
│  │ └── .file_metadata.json    │                                      │  │
│  └─────────────────────────────┘                                      │  │
│                                                                        │  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## File Upload & Processing Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    FILE UPLOAD PROCESS                          │
└─────────────────────────────────────────────────────────────────┘

USER ACTION:
┌─────────────┐
│ Upload File │
│ (Excel/PDF) │
└──────┬──────┘
       │
       ▼
[Admin Dashboard - Frontend]
       │
       ├─→ Select Format (.xlsx)
       ├─→ Select File
       └─→ Click "Upload" Button
           │
           ▼
       FormData Created
       │
       ▼
POST /api/upload
       │
       ▼
[Backend - main.py]
       │
       ├─→ Validate Extension
       │   • Check if in [.pdf, .xlsx, .csv, .txt, .docx, .xml]
       │   • If invalid: Return error
       │
       ├─→ Save to Disk
       │   • File → ./resources/HR_Handbook.xlsx
       │   • Preserve original filename
       │
       ├─→ Get File Metadata
       │   • Size: 1048576 bytes
       │   • Type: "excel" (detected)
       │
       ├─→ Record in Metadata
       │   • file_manager.add_file_record()
       │   • Save to ./resources/.file_metadata.json
       │   • Status: "uploaded"
       │
       └─→ Return Response
           • { success: true, message: "File uploaded" }

Result:
File physically exists at: ./resources/HR_Handbook.xlsx
Metadata exists at: ./resources/.file_metadata.json
Status: Ready to process

UI Shows:
✅ Upload successful
📑 File appears in Files Table
📊 Statistics updated (Total Files +1)
⏳ Status: "Uploaded"
```

---

## File Processing & Vector Storage Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                   FILE PROCESSING PIPELINE                       │
└──────────────────────────────────────────────────────────────────┘

USER ACTION:
┌─────────────────────┐
│ Click "Process"     │
│ Button for File     │
└──────────┬──────────┘
           │
           ▼
[Admin Dashboard - Frontend]
       │
       └─→ POST /api/process-file?filename=HR_Handbook.xlsx
           │
           ▼
[Backend - dataprocessor.py]


PHASE 1: TEXT EXTRACTION
┌────────────────────────────────────┐
│ Input: HR_Handbook.xlsx (1 MB)     │
└────────────────────────────────────┘
           │
           ▼
get_file_type()
  • Detect extension: .xlsx
  • Return type: "excel"
           │
           ▼
read_file()
  • Route to read_excel_file()
  • Open workbook
  • Read all sheets: ["Sheet1", "Sheet2", "Sheet3"]
  • Extract cell values
           │
           ▼
        Pages
    ┌──────────────┐
    │  Sheet 1:    │
    │  Employee    │
    │  data...     │ (3000 chars)
    ├──────────────┤
    │  Sheet 2:    │
    │  Benefits    │
    │  data...     │ (2500 chars)
    ├──────────────┤
    │  Sheet 3:    │
    │  Policies    │
    │  data...     │ (2000 chars)
    └──────────────┘
    
    Result: 3 pages, 7500 total chars


PHASE 2: TEXT CHUNKING
┌────────────────────────────────────┐
│ Input: 3 pages (7500 chars)        │
└────────────────────────────────────┘
           │
           ▼
chunk_pages(chunk_size=900, overlap=150)
           │
           ├─→ Combine all pages into single text
           │
           ├─→ Split into chunks
           │   Start: 0    End: 900     → Chunk 1
           │   Start: 750  End: 1650    → Chunk 2
           │   Start: 1500 End: 2400    → Chunk 3
           │   ... (overlap: 150 chars)
           │
           ▼
        Chunks
    ┌──────────────────────────────────┐
    │ Chunk 1: "Employee Name John..." │ (900 chars)
    │ Chunk 2: "Smith Department HR..." │ (900 chars)
    │ Chunk 3: "HR Salary 50000 Sheet2" │ (900 chars)
    │ Chunk 4: "Benefits Health..."     │ (900 chars)
    │ ...
    │ Chunk 47: "...Policy end"        │ (remaining)
    └──────────────────────────────────┘
    
    Result: 47 chunks


PHASE 3: EMBEDDING (Converting to Vectors)
┌────────────────────────────────────┐
│ Input: 47 chunks (text)            │
└────────────────────────────────────┘
           │
           ▼
embed_chunks()
           │
           ├─→ FOR each chunk:
           │   │
           │   ├─→ Send to OpenAI API
           │   │   Input: Chunk text
           │   │   Model: text-embedding-3-small
           │   │
           │   └─→ Receive: 1536-dimensional vector
           │       [0.123, -0.456, 0.789, ..., 0.321]
           │
           ├─→ OpenAI API called 47 times
           │   (One for each chunk)
           │
           ▼
        Embeddings
    ┌─────────────────────────────────────┐
    │ Embedding 1: [0.123, -0.456, ...]  │ (1536 dims)
    │ Embedding 2: [0.234, -0.567, ...]  │ (1536 dims)
    │ Embedding 3: [0.345, -0.678, ...]  │ (1536 dims)
    │ ...
    │ Embedding 47: [0.999, -0.001, ...] │ (1536 dims)
    └─────────────────────────────────────┘
    
    Result: 47 vectors (1536-dimensional each)


PHASE 4: VECTOR STORAGE (Pinecone)
┌────────────────────────────────────┐
│ Input: 47 chunks + 47 embeddings   │
└────────────────────────────────────┘
           │
           ▼
store_in_pinecone(chunks, embeddings, namespace="excel")
           │
           ├─→ Create vector objects:
           │   ┌─────────────────────────────────┐
           │   │ ID: "chunk_0"                   │
           │   │ Values: [0.123, -0.456, ...]    │
           │   │ Metadata: {                      │
           │   │   text: "Employee Name John...", │
           │   │   chunk_index: 0                 │
           │   │ }                                │
           │   └─────────────────────────────────┘
           │   (repeated for all 47 chunks)
           │
           ├─→ Batch upload (100 vectors per batch)
           │   Batch 1: Vectors 0-46
           │
           ├─→ Send to Pinecone API
           │   Namespace: "excel"
           │   Index: "hr-assistant-index"
           │
           ▼
        Pinecone Storage
    ┌────────────────────────────────────┐
    │ Index: hr-assistant-index          │
    │ ├─ Namespace: "pdf" (12 vectors)   │
    │ ├─ Namespace: "excel" (47 vectors) │ ← New!
    │ │  ├─ Vector ID: chunk_0           │
    │ │  │  Values: [embedding...]        │
    │ │  │  Metadata: {text, index}      │
    │ │  ├─ Vector ID: chunk_1           │
    │ │  │  Values: [embedding...]        │
    │ │  └─ ... (47 chunks)              │
    │ └─ Namespace: "csv" (0 vectors)    │
    └────────────────────────────────────┘
    
    Result: All vectors stored in Pinecone


PHASE 5: METADATA UPDATE
┌─────────────────────────────────────────┐
│ File Metadata Updated                   │
├─────────────────────────────────────────┤
│ Status: "uploaded" → "completed"        │
│ Chunks Created: 0 → 47                  │
│ Processed At: null → 2026-01-22T10:35   │
└─────────────────────────────────────────┘

UI Shows:
✅ Processing complete
📑 File status: "Completed"
📊 Chunks: 47
📈 Statistics updated
```

---

## Query Processing & Response Flow

```
┌────────────────────────────────────────────────────┐
│              QUERY PROCESSING PIPELINE             │
└────────────────────────────────────────────────────┘

USER ACTION:
┌──────────────────────────────┐
│ Type Question in Chat         │
│ "What benefits are available?"│
└──────────┬───────────────────┘
           │
           ▼
[Chat Interface - Frontend]
       │
       └─→ POST /chat
           { query: "What benefits are available?" }
           │
           ▼
[Backend - QueryProcessor.py]


PHASE 1: QUERY EMBEDDING
┌────────────────────────────────────────┐
│ Input: User Query (text)               │
│ "What benefits are available?"         │
└────────────────────────────────────────┘
           │
           ▼
embed_User_query()
       │
       ├─→ Send query to OpenAI
       │   Input: "What benefits are available?"
       │   Model: text-embedding-3-small (SAME as chunks!)
       │
       └─→ Receive: 1536-dimensional vector
           
Query Embedding:
[0.567, -0.234, 0.890, ..., 0.999]
(1536 dimensions representing semantic meaning of question)


PHASE 2: SIMILARITY SEARCH (VECTOR MATCHING)
┌────────────────────────────────────────────────┐
│ Input: Query Vector                            │
│ [0.567, -0.234, 0.890, ..., 0.999]            │
└────────────────────────────────────────────────┘
           │
           ▼
search_in_pinecone(query_vector, top_k=4)
           │
           ├─→ Connect to Pinecone
           │
           ├─→ Query: Find 4 vectors most similar to this
           │
           ├─→ Pinecone calculates COSINE SIMILARITY:
           │
           │   Query Vector vs Each Stored Vector:
           │   ┌────────────────────────────────────┐
           │   │ Chunk 0: [0.568, -0.235, ...]     │
           │   │ Similarity: 0.99 ✅               │
           │   ├────────────────────────────────────┤
           │   │ Chunk 1: [0.120, -0.456, ...]     │
           │   │ Similarity: 0.45                  │
           │   ├────────────────────────────────────┤
           │   │ Chunk 2: [0.566, -0.233, ...]     │
           │   │ Similarity: 0.98 ✅               │
           │   ├────────────────────────────────────┤
           │   │ Chunk 3: [0.567, -0.234, ...]     │
           │   │ Similarity: 1.00 ✅ BEST!         │
           │   ├────────────────────────────────────┤
           │   │ Chunk 4: [0.567, -0.234, ...]     │
           │   │ Similarity: 1.00 ✅ BEST!         │
           │   ├────────────────────────────────────┤
           │   │ Chunk 5: [0.800, -0.100, ...]     │
           │   │ Similarity: 0.35                  │
           │   └────────────────────────────────────┘
           │
           ├─→ Return TOP 4 MATCHES:
           │   1. Chunk 3 (sim: 1.00)
           │   2. Chunk 4 (sim: 1.00)
           │   3. Chunk 0 (sim: 0.99)
           │   4. Chunk 2 (sim: 0.98)
           │
           └─→ Retrieve text from metadata
           
Top 4 Matched Chunks:
┌──────────────────────────────────────────┐
│ Chunk 3: "Benefits Health Insurance..."  │
│ Chunk 4: "Benefits Dental Coverage..."   │
│ Chunk 0: "Benefits Vision Coverage..."   │
│ Chunk 2: "Benefits Life Insurance..."    │
└──────────────────────────────────────────┘

Total Retrieved Context: ~3600 characters


PHASE 3: LLM RESPONSE GENERATION
┌──────────────────────────────────────────┐
│ Inputs:                                  │
│ 1. Query: "What benefits are available?" │
│ 2. Context: 4 retrieved chunks           │
└──────────────────────────────────────────┘
           │
           ▼
query_llm_with_context(query, context)
           │
           ├─→ Construct prompt:
           │
           │   System Prompt:
           │   "You are a helpful assistant..."
           │
           │   User Message:
           │   "Query: What benefits are available?
           │    
           │    Context:
           │    Benefits Health Insurance...
           │    Benefits Dental Coverage...
           │    Benefits Vision Coverage...
           │    Benefits Life Insurance..."
           │
           ├─→ Send to GPT-3.5-turbo
           │   • Temperature: 0.4 (factual)
           │   • Model: gpt-3.5-turbo
           │
           └─→ GPT generates response from CONTEXT ONLY
           
GPT Response:
┌────────────────────────────────────────────┐
│ Based on the provided context, the        │
│ available benefits are:                    │
│                                            │
│ 1. Health Insurance - Comprehensive       │
│    coverage with premium paid by employer  │
│                                            │
│ 2. Dental Coverage - Up to $5,000 annual  │
│    coverage for dental procedures          │
│                                            │
│ 3. Vision Coverage - Routine eye exams   │
│    covered at 100%                        │
│                                            │
│ 4. Life Insurance - 2x annual salary      │
│    coverage                                │
│                                            │
│ These are the benefits outlined in your   │
│ company documents.                         │
└────────────────────────────────────────────┘

Result: ACCURATE answer based on YOUR data!


PHASE 4: RESPONSE DELIVERY
┌──────────────────────────────────────────────┐
│ Return to Frontend                           │
│ { response: "Based on provided context...",  │
│   query: "What benefits are available?" }    │
└──────────────────────────────────────────────┘
           │
           ▼
[Chat Interface - Frontend]
           │
           └─→ Display response
               • Show in chat bubble
               • Timestamp added
               • Can continue conversation
```

---

## Why This Approach Works

```
┌──────────────────────────────────────────────┐
│  WHY RAG IS BETTER THAN REGULAR GPT          │
└──────────────────────────────────────────────┘

REGULAR GPT PROBLEM:
┌────────────────────────────────┐
│ User: "What are our benefits?" │
└──────────────┬─────────────────┘
               │
               ▼
        GPT processes query using
        TRAINING DATA ONLY
               │
               ├─ May hallucinate
               ├─ May be outdated
               ├─ May be generic
               └─ No company-specific knowledge
               │
               ▼
         ❌ WRONG: "The benefits typically 
            include... (generic answer)"

RAG SOLUTION:
┌────────────────────────────────┐
│ User: "What are our benefits?" │
└──────────────┬─────────────────┘
               │
               ▼
        GPT processes query using
        YOUR UPLOADED DOCUMENTS
               │
               ├─ Searches your Excel files
               ├─ Searches your PDFs
               ├─ Finds exact matches
               └─ Uses YOUR data
               │
               ▼
        ✅ CORRECT: "Based on your 
           HR_Handbook.xlsx, the benefits
           include: 1. Health Insurance...
           2. Dental Coverage..."
```

---

## Data Persistence

```
┌──────────────────────────────────────┐
│  WHERE YOUR DATA IS STORED           │
└──────────────────────────────────────┘

LOCAL DISK:
./resources/
├── HRPolicy.pdf              (original file)
├── HR_Handbook.xlsx          (original file)
├── Employee_Data.csv         (original file)
└── .file_metadata.json       (metadata)

    .file_metadata.json structure:
    {
      "files": [
        {
          "id": 1,
          "file_name": "HRPolicy.pdf",
          "file_type": "pdf",
          "file_size": 2048576,
          "status": "completed",
          "uploaded_at": "2026-01-22T10:00:00",
          "processed_at": "2026-01-22T10:05:00",
          "chunks_created": 12
        },
        {
          "id": 2,
          "file_name": "HR_Handbook.xlsx",
          "file_type": "excel",
          "file_size": 1048576,
          "status": "completed",
          "uploaded_at": "2026-01-22T10:30:00",
          "processed_at": "2026-01-22T10:35:00",
          "chunks_created": 47
        }
      ]
    }


PINECONE VECTOR DB:
hr-assistant-index
├─ Namespace: "pdf"
│  ├─ 12 vectors (chunks from HRPolicy.pdf)
│  └─ Each has embedding + metadata
│
├─ Namespace: "excel"
│  ├─ 47 vectors (chunks from HR_Handbook.xlsx)
│  └─ Each has embedding + metadata
│
└─ Namespace: "csv"
   ├─ 23 vectors (chunks from Employee_Data.csv)
   └─ Each has embedding + metadata


PERSISTENCE GUARANTEE:
✅ Files never deleted without user action
✅ Metadata survives app restart
✅ Vectors persisted in Pinecone
✅ Data available across sessions
✅ Multiple files = multiple namespaces
```

---

## Summary

This RAG system is powerful because:

1. **Multi-Format Support** - PDF, Excel, CSV, Word, TXT, XML
2. **Semantic Search** - Finds meaning, not just keywords
3. **Context-Grounded** - Answers based on YOUR data, not training data
4. **Scalable** - Add more documents, search across all
5. **Fast** - Instant responses using vector similarity
6. **Accurate** - No hallucinations, facts from documents
7. **User-Friendly** - Simple admin dashboard for uploads
8. **Professional** - Production-ready architecture

**The magic happens in the vector embeddings - they capture semantic meaning!**
