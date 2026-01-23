from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from QueryProcessor import process_user_query
from file_manager import add_file_record, get_all_files, get_file_stats, update_file_record
from dataprocessor import process_file
from file_processor import get_supported_formats
import os
import shutil
from pathlib import Path

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESOURCES_DIR = Path("./resources")
RESOURCES_DIR.mkdir(exist_ok=True)

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    query: str

@app.get("/")
def read_root():
    return {"message": "HR Assistant RAG API is running"}

@app.post("/chat")
def chat(request: QueryRequest):
    """
    Process user query through the RAG pipeline
    """
    # ============== DEBUGGING OUTPUT ===============
    print("\n" + "="*70)
    print("🔴 CHAT ENDPOINT HIT!")
    print("="*70)
    print(f"📥 RECEIVED REQUEST")
    print(f"   Type: {type(request)}")
    print(f"   Query: {request.query}")
    print(f"   Query Length: {len(request.query)}")
    print("-"*70)
    
    try:
        print(f"\n🔄 STEP 1: Processing query...")
        print(f"   Calling: process_user_query('{request.query}')")
        
        response = process_user_query(request.query)
        
        print(f"\n✅ STEP 2: Response received from LLM")
        print(f"   Type: {type(response)}")
        print(f"   Length: {len(str(response))}")
        print(f"   Content: {response[:100]}..." if len(str(response)) > 100 else f"   Content: {response}")
        
        print(f"\n📤 RETURNING RESPONSE")
        print(f"   Status: SUCCESS")
        print("="*70 + "\n")
        
        return QueryResponse(response=response, query=request.query)
        
    except Exception as e:
        print(f"\n❌ ERROR OCCURRED")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {str(e)}")
        
        import traceback
        print(f"\n📋 TRACEBACK:")
        traceback.print_exc()
        print("="*70 + "\n")
        
        return {"error": str(e), "query": request.query}

# ============== FILE MANAGEMENT ENDPOINTS ==============

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to resources folder
    Supports: PDF, Excel, CSV, TXT, Word, XML
    """
    try:
        # Validate file extension
        supported = get_supported_formats()
        file_ext = Path(file.filename).suffix.lower()
        
        if file_ext not in supported:
            raise HTTPException(
                status_code=400, 
                detail=f"File type {file_ext} not supported. Supported: {', '.join(supported)}"
            )
        
        # Save file
        file_path = RESOURCES_DIR / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = file_path.stat().st_size
        
        # Get file type
        from file_processor import get_file_type
        file_type = get_file_type(str(file_path))
        
        # Record in metadata
        file_record = add_file_record(file.filename, file_type, file_size)
        
        return {
            "success": True,
            "message": f"File {file.filename} uploaded successfully",
            "file": file_record
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-file")
def process_uploaded_file(filename: str):
    """
    Process an uploaded file and store in vector DB
    """
    try:
        file_path = RESOURCES_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
        # Process the file
        result = process_file(str(file_path))
        
        # Update metadata
        update_file_record(filename, result["chunks_created"])
        
        return {
            "success": True,
            "message": f"File processed successfully",
            "result": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
def get_files():
    """
    Get all uploaded files with their metadata
    """
    try:
        files = get_all_files()
        stats = get_file_stats()
        return {
            "files": files,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/stats")
def get_stats():
    """
    Get file upload statistics
    """
    try:
        stats = get_file_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/supported-formats")
def get_formats():
    """
    Get list of supported file formats
    """
    return {
        "supported_formats": get_supported_formats(),
        "description": "Upload documents in any of these formats for RAG processing"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
