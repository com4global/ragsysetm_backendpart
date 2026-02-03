# 📚 Complete Lifecycle Explanation: From File Upload to LLM Response

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FILE UPLOAD & PROCESSING LIFECYCLE                      │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: USER UPLOADS FILE (React Frontend)
         │
         ├─→ Select file in Admin Dashboard
         ├─→ Click "✅ Upload File"
         └─→ POST request to /api/upload

                        ↓

STEP 2: BACKEND RECEIVES FILE (main.py - /api/upload endpoint)
         │
         ├─→ Validate file extension
         ├─→ Save file to ./resources/ folder
         ├─→ Record metadata in .file_metadata.json
         └─→ Return success response

                        ↓

STEP 3: USER CLICKS "⚙️ PROCESS" (Admin Dashboard)
         │
         └─→ POST request to /api/process-file?filename=...

                        ↓

STEP 4: FILE PROCESSING PIPELINE (dataprocessor.py - process_file function)
         │
         ├─→ [PHASE 1] TEXT EXTRACTION (file_processor.py - read_file)
         │   ├─ Detect file type: PDF, Excel, CSV, TXT, Word, XML
         │   ├─ Use appropriate reader based on type
         │   └─ Output: List of text pages
         │
         ├─→ [PHASE 2] TEXT CHUNKING (chunker.py - chunk_pages)
         │   ├─ Split pages into manageable chunks
         │   ├─ Chunk size: ~900 characters
         │   ├─ Overlap: 150 characters (for context continuity)
         │   └─ Output: List of text chunks
         │
         ├─→ [PHASE 3] EMBEDDING (embedder.py - embed_chunks)
         │   ├─ Each chunk sent to OpenAI API
         │   ├─ Model: text-embedding-3-small
         │   ├─ Output: 1536-dimensional vectors
         │   └─ One embedding per chunk
         │
         └─→ [PHASE 4] VECTOR STORAGE (vectorstore.py - store_in_pinecone)
             ├─ Create vectors with metadata
             ├─ Batch upload to Pinecone
             ├─ Namespace: file type (pdf, excel, csv, etc.)
             └─ Status updated to "Completed"

                        ↓

STEP 5: USER ASKS QUESTION (Chat Interface)
         │
         └─→ Type question and press Send
             POST request to /chat endpoint

                        ↓

STEP 6: QUERY PROCESSING (QueryProcessor.py - process_user_query)
         │
         ├─→ [PHASE 1] QUERY EMBEDDING (embedder.py - embed_User_query)
         │   ├─ User's question sent to OpenAI
         │   ├─ Converted to 1536-dimensional vector
         │   └─ Same model as content embeddings
         │
         ├─→ [PHASE 2] SIMILARITY SEARCH (vectorstore.py - search_in_pinecone)
         │   ├─ Compare query vector with all stored vectors
         │   ├─ Find top 4 most similar chunks
         │   ├─ Retrieve text from metadata
         │   └─ Output: List of relevant text chunks
         │
         └─→ [PHASE 3] LLM RESPONSE GENERATION (llm.py - query_llm_with_context)
             ├─ Send system prompt to GPT-3.5-turbo
             ├─ Include user query + retrieved context
             ├─ GPT generates answer based on context
             └─ Return response to user

                        ↓

STEP 7: RESPONSE DISPLAYED (React Frontend)
         └─→ Show answer in chat interface
```

---

## 📋 Detailed Step-by-Step Walkthrough

### **PHASE 1: USER UPLOADS FILE**

#### React Frontend (AdminDashboard.js)
```javascript
// User clicks "✅ Upload File" button
const handleUpload = async () => {
  const formData = new FormData();
  formData.append('file', selectedFile); // e.g., "HR_Handbook.xlsx"
  
  const response = await axios.post(
    'http://localhost:8000/api/upload',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  // Response: { success: true, message: "File uploaded successfully" }
};
```

---

### **PHASE 2: BACKEND RECEIVES & STORES FILE**

#### main.py - /api/upload endpoint
```python
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    # STEP 1: Validate file type
    file_ext = Path(file.filename).suffix.lower()  # e.g., ".xlsx"
    if file_ext not in ['.pdf', '.xlsx', '.csv', '.txt', '.docx', '.doc', '.xml']:
        raise HTTPException(status_code=400, detail="File not supported")
    
    # STEP 2: Save file to disk
    file_path = RESOURCES_DIR / file.filename  # ./resources/HR_Handbook.xlsx
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)  # Physical file saved
    
    # STEP 3: Record metadata
    file_size = file_path.stat().st_size  # Get file size in bytes
    file_type = get_file_type(str(file_path))  # Detect file type: "excel"
    file_record = add_file_record(file.filename, file_type, file_size)
    
    # STEP 4: Return response
    return {
        "success": True,
        "message": "File HR_Handbook.xlsx uploaded successfully",
        "file": file_record
    }
```

#### file_manager.py - add_file_record function
```python
def add_file_record(file_name: str, file_type: str, file_size: int) -> dict:
    metadata = load_metadata()  # Load existing metadata from JSON
    
    # Create new record
    new_record = {
        "id": len(metadata['files']) + 1,
        "file_name": "HR_Handbook.xlsx",
        "file_type": "excel",
        "file_size": 1048576,
        "status": "uploaded",  # Not yet processed
        "uploaded_at": "2026-01-22T10:30:00",
        "processed_at": None,
        "chunks_created": 0
    }
    
    metadata['files'].append(new_record)
    save_metadata(metadata)  # Save to ./resources/.file_metadata.json
    
    return new_record
```

**Result**: File now exists at `./resources/HR_Handbook.xlsx` with metadata tracked in JSON

---

### **PHASE 3: USER CLICKS PROCESS BUTTON**

#### React Frontend (AdminDashboard.js)
```javascript
const handleProcessFile = async (filename) => {
  // User clicks "⚙️ Process" button for HR_Handbook.xlsx
  const response = await axios.post(
    'http://localhost:8000/api/process-file',
    null,
    { params: { filename: "HR_Handbook.xlsx" } }
  );
  // Response: { success: true, chunks_created: 47 }
};
```

---

### **PHASE 4A: TEXT EXTRACTION FROM FILE**

#### main.py - /api/process-file endpoint
```python
@app.post("/api/process-file")
def process_uploaded_file(filename: str):
    file_path = RESOURCES_DIR / filename  # ./resources/HR_Handbook.xlsx
    
    # Call the processing pipeline
    result = process_file(str(file_path))
    
    # Update metadata: mark as "completed"
    update_file_record(filename, result["chunks_created"])
    
    return {
        "success": True,
        "message": "File processed successfully",
        "result": result
    }
```

#### dataprocessor.py - process_file function
```python
def process_file(file_path: str):
    file_name = "HR_Handbook.xlsx"
    file_type = get_file_type(file_path)  # Returns: "excel"
    
    # STEP 1: EXTRACT TEXT FROM FILE
    pages, detected_type = read_file(file_path)
    # pages = [
    #   "Sheet1: Employee Name, Department, Salary...",
    #   "Sheet2: Benefits: Health Insurance, Dental...",
    #   ...
    # ]
    # len(pages) = 3
    
    return {
        "file_name": "HR_Handbook.xlsx",
        "file_type": "excel",
        "pages_extracted": 3,
        "chunks_created": 47,
        "namespace": "excel"
    }
```

#### file_processor.py - read_file function
```python
def read_file(file_path: str):
    file_type = get_file_type(file_path)  # Detect: "excel"
    
    if file_type == "excel":
        return read_excel_file(file_path), file_type
    # ... other file types ...

def read_excel_file(file_path: str) -> List[str]:
    """Read Excel file and extract text"""
    pages = []
    
    try:
        workbook = openpyxl.load_workbook(file_path)
        
        for sheet in workbook.sheetnames:  # ["Sheet1", "Sheet2"]
            ws = workbook[sheet]
            sheet_text = f"Sheet: {sheet}\n"
            
            # Read all cells
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value:
                        sheet_text += str(cell.value) + " "
            
            pages.append(sheet_text)
        
        return pages
    except Exception as e:
        raise Exception(f"Error reading Excel: {str(e)}")

# Result:
# pages = [
#   "Sheet: Sheet1\nEmployee Name John Smith Department HR Salary 50000...",
#   "Sheet: Sheet2\nBenefits Health Insurance Dental Vision...",
#   "Sheet: Sheet3\nLeave Policy Annual Leave 20 days Sick Leave 5 days..."
# ]
```

**Result**: Text extracted from Excel file into 3 pages

---

### **PHASE 4B: TEXT CHUNKING**

#### dataprocessor.py continues
```python
# STEP 2: CHUNK THE TEXT
chunks = chunk_pages(pages, chunk_size=900, chunk_overlap=150)
# chunks now has 47 chunks (each ~900 chars with 150 char overlap)
```

#### chunker.py - chunk_pages function
```python
def chunk_pages(pages: List[str], chunk_size: int = 900, chunk_overlap: int = 150):
    chunks = []
    
    # Combine all pages into one long text
    full_text = " ".join(pages)
    # full_text = "Sheet: Sheet1\nEmployee Name John Smith... [3000+ characters]"
    
    text_length = len(full_text)  # e.g., 45000 characters
    
    start = 0
    while start < text_length:
        # Calculate end position (max 900 chars)
        end = min(start + 900, text_length)
        
        # Extract chunk
        chunk = full_text[start:end].strip()
        chunks.append(chunk)
        
        # Example chunks created:
        # Chunk 1: "Sheet: Sheet1\nEmployee Name John Smith Department HR..."
        # Chunk 2: "Smith Department HR Salary 50000 Employee2 Jane Doe..." (overlaps with chunk 1)
        # Chunk 3: "Doe Department Finance Salary 60000 Sheet: Sheet2..." (overlaps with chunk 2)
        # ... (total of 47 chunks)
        
        # Move to next chunk (overlap by 150 chars for context continuity)
        start = end - chunk_overlap  # 900 - 150 = 750 characters forward
    
    return chunks
```

**Result**: 47 chunks created, each ~900 characters with 150-char overlap

```
VISUALIZATION OF CHUNKING:
┌─────────────────────────────────────┐
│  Chunk 1: [============================]  (chars 0-900)
│           └──────────────────────────┘
│                   ↓ (overlap: 150 chars)
│                   Chunk 2: [============================]  (chars 750-1650)
│                            └──────────────────────────┘
│                                    ↓ (overlap: 150 chars)
│                                    Chunk 3: [============================]  (chars 1500-2400)
└─────────────────────────────────────┘
```

---

### **PHASE 4C: CONVERTING CHUNKS TO EMBEDDINGS**

#### dataprocessor.py continues
```python
# STEP 3: EMBED CHUNKS (Convert to vectors)
embedded_chunks = embed_chunks(chunks)
# embedded_chunks = [
#   [0.123, -0.456, 0.789, ..., 0.321],  # Chunk 1 embedding (1536 dimensions)
#   [0.234, -0.567, 0.890, ..., 0.432],  # Chunk 2 embedding (1536 dimensions)
#   [0.345, -0.678, 0.901, ..., 0.543],  # Chunk 3 embedding (1536 dimensions)
#   ...
# ]
```

#### embedder.py - embed_chunks function
```python
from openai import OpenAI

client = OpenAI(api_key="sk-xxxxxxxx")
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536-dimensional vectors

def embed_chunks(chunks: List[str]) -> List[List[float]]:
    embeddings = []
    
    for i, chunk in enumerate(chunks):  # For each of 47 chunks
        # Send chunk to OpenAI API
        response = client.embeddings.create(
            input=chunk,
            model="text-embedding-3-small"
        )
        
        # Extract embedding vector (1536 dimensions)
        embedding = response.data[0].embedding
        # embedding = [0.123, -0.456, 0.789, ..., 0.321]
        # (1536 numbers representing meaning of the text)
        
        embeddings.append(embedding)
    
    return embeddings

# WHAT IS AN EMBEDDING?
# - A mathematical representation of text meaning
# - 1536 numbers that capture semantic information
# - Similar texts have similar embeddings (closer vectors)
# - Enables semantic search (find meaning, not just keywords)
#
# Example:
# "Benefits include health insurance"  → [0.1, 0.2, 0.3, ..., 1536 numbers]
# "Health coverage is provided"        → [0.11, 0.21, 0.31, ..., 1536 numbers]
# These embeddings are similar (close vectors) because text means similar things
```

**Result**: Each chunk converted to a 1536-dimensional vector (embedding)

---

### **PHASE 4D: STORING IN VECTOR DATABASE (PINECONE)**

#### dataprocessor.py continues
```python
# STEP 4: STORE IN PINECONE
namespace = "excel"  # Use file type as namespace
store_in_pinecone(chunks, embedded_chunks, namespace=namespace)
```

#### vectorstore.py - store_in_pinecone function
```python
from pinecone import Pinecone

pinecone_client = Pinecone(api_key="pcask_xxxxx")
index = pinecone_client.Index("hr-assistant-index")

def store_in_pinecone(chunks: List[str], embeddings: List[List[float]], namespace: str):
    vectors_to_upsert = []
    
    # Create vector objects with metadata
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_data = {
            "id": f"chunk_{i}",  # Unique ID: chunk_0, chunk_1, ..., chunk_46
            "values": embedding,  # The 1536-dimensional embedding
            "metadata": {
                "text": chunk,  # Original text (for retrieval)
                "chunk_index": i
            }
        }
        vectors_to_upsert.append(vector_data)
    
    # Batch upload to Pinecone (100 vectors per batch)
    batch_size = 100
    for i in range(0, len(vectors_to_upsert), batch_size):
        batch = vectors_to_upsert[i:i + batch_size]
        index.upsert(vectors=batch, namespace=namespace)
        # Uploads to Pinecone in namespace "excel"

# WHAT'S STORED IN PINECONE?
# 
# Index: "hr-assistant-index"
# ├─ Namespace: "pdf"
# │  ├─ Vector ID: chunk_0
# │  │  ├─ Values: [0.123, -0.456, ..., 1536 numbers] (embedding)
# │  │  └─ Metadata: {text: "HR Policy content...", chunk_index: 0}
# │  ├─ Vector ID: chunk_1
# │  │  ├─ Values: [0.234, -0.567, ..., 1536 numbers]
# │  │  └─ Metadata: {text: "More HR content...", chunk_index: 1}
# │  └─ ... (12 chunks from PDF)
# │
# └─ Namespace: "excel"
#    ├─ Vector ID: chunk_0
#    │  ├─ Values: [0.345, -0.678, ..., 1536 numbers] (different embedding)
#    │  └─ Metadata: {text: "Sheet1 data...", chunk_index: 0}
#    ├─ Vector ID: chunk_1
#    │  ├─ Values: [0.456, -0.789, ..., 1536 numbers]
#    │  └─ Metadata: {text: "Sheet2 benefits...", chunk_index: 1}
#    └─ ... (47 chunks from Excel)
```

**Result**: All 47 chunks stored in Pinecone with embeddings, organized in "excel" namespace

**File Metadata Updated**:
```json
{
  "id": 1,
  "file_name": "HR_Handbook.xlsx",
  "file_type": "excel",
  "file_size": 1048576,
  "status": "completed",  // Changed from "uploaded"
  "uploaded_at": "2026-01-22T10:30:00",
  "processed_at": "2026-01-22T10:35:00",
  "chunks_created": 47
}
```

---

## 📝 PHASE 5: USER ASKS A QUESTION

### React Frontend (ChatInterface.js)
```javascript
// User types: "What are the benefits in the Excel file?"
// and presses Send

const handleSend = async () => {
  const response = await axios.post(
    'http://localhost:8000/chat',
    { query: "What are the benefits in the Excel file?" }
  );
  // Response: { response: "The benefits include..." }
};
```

---

## 🔍 PHASE 6A: QUERY EMBEDDING

#### main.py - /chat endpoint
```python
@app.post("/chat")
def chat(request: QueryRequest):  # Query: "What are the benefits..."
    response = process_user_query(request.query)
    return QueryResponse(response=response, query=request.query)
```

#### QueryProcessor.py - process_user_query function
```python
def process_user_query(query: str):
    # STEP 1: EMBED THE USER'S QUERY
    query_vector = embed_User_query(query)
    # query_vector = [0.567, -0.234, ..., 1536 numbers]
    # (semantic representation of "What are the benefits...")
    
    # STEP 2: SEARCH FOR SIMILAR CHUNKS IN PINECONE
    matched_chunks = search_in_pinecone(query_vector)
    # matched_chunks = [
    #   "Sheet: Sheet2\nBenefits Health Insurance Premium covered...",
    #   "Sheet: Sheet2\nBenefits Dental Coverage up to $5000...",
    #   "Sheet: Sheet2\nBenefits Vision Coverage 100% routine exams...",
    #   "Sheet: Sheet2\nBenefits Life Insurance 2x annual salary..."
    # ]
    # (Top 4 most similar chunks to the query)
    
    # STEP 3: GENERATE RESPONSE FROM LLM
    generated_response = query_llm_with_context(query, matched_chunks)
    # generated_response = "Based on the Excel file, the benefits include:
    #                       1. Health Insurance (premium covered)
    #                       2. Dental Coverage (up to $5000)
    #                       3. Vision Coverage (100% routine exams)
    #                       4. Life Insurance (2x annual salary)"
    
    return generated_response
```

#### embedder.py - embed_User_query function
```python
def embed_User_query(query: str) -> List[float]:
    # Convert user's question to embedding using SAME model as content
    response = client.embeddings.create(
        input="What are the benefits in the Excel file?",
        model="text-embedding-3-small"  # Same model!
    )
    
    embedding = response.data[0].embedding
    # embedding = [0.567, -0.234, 0.890, ..., 0.999]
    # (1536 dimensions)
    
    return embedding
```

**Result**: User query converted to same format as stored embeddings

---

## 🔍 PHASE 6B: SEMANTIC SEARCH IN VECTOR DATABASE

#### vectorstore.py - search_in_pinecone function
```python
def search_in_pinecone(query_vector: List[float], top_k: int = 4, namespace: str = ""):
    # Query Pinecone: "Find 4 vectors most similar to this query vector"
    results = index.query(
        vector=query_vector,      # [0.567, -0.234, ..., 0.999]
        top_k=4,                  # Return top 4 matches
        include_metadata=True,    # Include original text
        namespace=namespace       # Search all namespaces (or specific one)
    )
    
    # PINECONE SIMILARITY SEARCH (Vector Similarity)
    # Query embedding: [0.567, -0.234, 0.890, ..., 0.999]
    #
    # Compares with stored embeddings using COSINE SIMILARITY:
    # 
    # Chunk 1 embedding:  [0.568, -0.235, 0.891, ...] → Similarity: 0.98 ✅ MATCH!
    # Chunk 2 embedding:  [0.120, -0.456, 0.780, ...] → Similarity: 0.42
    # Chunk 3 embedding:  [0.569, -0.236, 0.892, ...] → Similarity: 0.99 ✅ MATCH!
    # Chunk 4 embedding:  [0.800, -0.100, 0.500, ...] → Similarity: 0.35
    # Chunk 5 embedding:  [0.567, -0.234, 0.890, ...] → Similarity: 1.00 ✅ PERFECT!
    # ...
    #
    # Top 4 Results (highest similarity):
    # 1. Chunk 47 with similarity 1.00
    # 2. Chunk 5 with similarity 0.99
    # 3. Chunk 1 with similarity 0.98
    # 4. Chunk 12 with similarity 0.97
    
    print(f"Found {len(results.matches)} matches for the query.")
    
    matched_chunks = []
    for match in results.matches:  # Top 4 matches
        matched_chunks.append(match.metadata.get("text", ""))
        # Retrieves original text from metadata
    
    return matched_chunks
    
# RESULT:
# matched_chunks = [
#   "Sheet: Sheet2\nBenefits Health Insurance Premium covered...",
#   "Sheet: Sheet2\nBenefits Dental Coverage up to $5000...",
#   "Sheet: Sheet2\nBenefits Vision Coverage 100% routine exams...",
#   "Sheet: Sheet2\nBenefits Life Insurance 2x annual salary..."
# ]
```

**Result**: Top 4 most relevant chunks retrieved based on semantic similarity

---

## 🤖 PHASE 6C: LLM GENERATES FINAL ANSWER

#### llm.py - query_llm_with_context function
```python
def query_llm_with_context(query: str, context: str):
    system_content = """
    You are a helpful assistant for answering HR questions based on provided context.
    Use the context to provide accurate answers.
    If context doesn't contain info, say so.
    """
    
    # Create the prompt for GPT
    user_message = f"""
    Query: What are the benefits in the Excel file?
    
    Context:
    Sheet: Sheet2
    Benefits Health Insurance Premium covered...
    Sheet: Sheet2
    Benefits Dental Coverage up to $5000...
    Sheet: Sheet2
    Benefits Vision Coverage 100% routine exams...
    Sheet: Sheet2
    Benefits Life Insurance 2x annual salary...
    """
    
    # Send to GPT-3.5-turbo
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_message}
        ],
        temperature=0.4  # Lower = more factual, less creative
    )
    
    # GPT generates response based on context (not from its training data!)
    return response.choices[0].message.content

# GPT RESPONSE:
# "Based on the provided context, the benefits in the Excel file include:
#
#  1. Health Insurance - Premium is covered
#  2. Dental Coverage - Up to $5000 coverage
#  3. Vision Coverage - 100% routine exams covered
#  4. Life Insurance - 2x annual salary
#
#  These are the comprehensive benefits currently outlined in Sheet2
#  of the Excel file."
```

**Result**: GPT generates accurate answer based on retrieved context

---

## 📤 PHASE 7: RESPONSE RETURNED TO USER

#### React Frontend (ChatInterface.js)
```javascript
// Response received and displayed
const response = {
  response: "Based on the provided context, the benefits include...",
  query: "What are the benefits..."
};

// Displayed in chat:
// Assistant: "Based on the provided context, the benefits include..."
```

---

## 📊 Complete Data Flow Summary

```
USER UPLOADS: "HR_Handbook.xlsx" (1 MB)
                    ↓
            File saved to disk
            Metadata recorded
                    ↓
USER CLICKS: "⚙️ Process"
                    ↓
        [TEXT EXTRACTION]
        3 sheets → 3 pages of text
                    ↓
        [TEXT CHUNKING]
        3 pages → 47 chunks (~900 chars each)
                    ↓
        [EMBEDDING]
        47 chunks → 47 vectors (1536-dimensional embeddings)
        OpenAI API called 47 times
        Cost: ~$0.002 per file
                    ↓
        [VECTOR STORAGE]
        47 vectors stored in Pinecone
        Organized in "excel" namespace
        File status: "completed"
                    ↓
USER ASKS: "What are the benefits?"
                    ↓
        [QUERY EMBEDDING]
        1 query → 1 vector (1536-dimensional)
        OpenAI API called 1 time
                    ↓
        [SEMANTIC SEARCH]
        Compare query vector with 47 stored vectors
        Find top 4 most similar chunks
                    ↓
        [CONTEXT RETRIEVAL]
        4 most relevant chunks retrieved
        Total context: ~3600 characters
                    ↓
        [LLM GENERATION]
        Query + Context → GPT-3.5-turbo
        Generates answer from context (not hallucinated)
                    ↓
RESPONSE: "Based on the context, benefits include:
           1. Health Insurance...
           2. Dental Coverage...
           3. Vision Coverage...
           4. Life Insurance..."
```

---

## 🔑 Key Concepts Explained

### **1. Embeddings (Vectors)**
- Mathematical representation of text meaning
- 1536 numbers for each chunk
- Similar texts = similar vectors
- Enables semantic search

### **2. Chunking**
- Split large documents into manageable pieces
- 900 characters per chunk (typical)
- 150 character overlap for context continuity

### **3. Namespaces**
- Organization in Pinecone by file type
- "pdf" namespace: PDF chunks
- "excel" namespace: Excel chunks
- Allows separate organization of different document types

### **4. Similarity Search**
- Find vectors similar to query vector
- Uses cosine similarity metric
- Returns top-k most similar vectors

### **5. RAG (Retrieval Augmented Generation)**
- Retrieve relevant context from vector DB
- Augment prompt with context
- Generate response from LLM
- Result: Accurate, context-grounded answers

### **6. Temperature Setting (0.4)**
- Lower values = more factual
- Higher values = more creative
- 0.4 chosen for factual HR responses

---

## 💰 Cost Breakdown

| Operation | API Calls | Cost |
|-----------|-----------|------|
| Upload Excel (1MB) | 0 | Free |
| Extract text | 0 | Free |
| Create 47 chunks | 0 | Free |
| Embed 47 chunks | 47 OpenAI calls | ~$0.0006 |
| Process complete | 0 | Free |
| User query | 1 OpenAI query embed | ~$0.00001 |
| Search in Pinecone | 1 vector query | Free (Pinecone) |
| Generate response | 1 GPT call | ~$0.001 |
| **Total per file + query** | **~49 API calls** | **~$0.0016** |

---

## ✅ Summary

**The complete lifecycle:**

1. ✅ User uploads file
2. ✅ File saved to disk & metadata recorded
3. ✅ User processes file
4. ✅ Text extracted based on format
5. ✅ Text split into chunks
6. ✅ Each chunk converted to embedding
7. ✅ Embeddings stored in Pinecone with metadata
8. ✅ User asks question
9. ✅ Question converted to embedding
10. ✅ Semantic search finds top 4 similar chunks
11. ✅ Retrieved context sent to GPT-3.5-turbo
12. ✅ GPT generates answer from context
13. ✅ Answer displayed to user

**All within seconds, with high accuracy and no hallucinations!**
