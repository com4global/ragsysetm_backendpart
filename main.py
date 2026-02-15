"""
FastAPI Main Application with Authentication
Production-ready API with user isolation and security
"""

# from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from typing import Dict, Optional, List
# import os
# import shutil
# from pathlib import Path
# from fastapi.staticfiles import StaticFiles
# from datetime import datetime, timedelta
# import uuid
# from datetime import timezone
# from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Query
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from typing import Optional, List, Dict, Any
# import os
# import shutil
# from pathlib import Path
# from fastapi.staticfiles import StaticFiles
# from datetime import datetime, timedelta
# import uuid
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import shutil
import uuid
from datetime import datetime
import logging
import uvicorn
import requests
from pathlib import Path
from contextlib import asynccontextmanager
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
import re

# Local modules
from database import user_db, supabase
from Auth import get_current_user, User
# from Auth import (
#     Token, UserCreate, UserLogin, 
#     create_access_token, create_refresh_token, 
#     verify_password, get_password_hash,
#     verify_token, verify_refresh_token
# )
# from services.file_manager import FileManager
# from services.dataprocessor import DataProcessor
# from services.vectorstore import VectorStore
# from services.chat_service import ChatService # If you have one

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
# Determine environment
IS_VERCEL = os.environ.get("VERCEL") == "1" or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")

# Base paths
BASE_DIR = Path("/tmp") if IS_VERCEL else Path(".")

# Writable directories (always in /tmp on Vercel)
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
WRITE_RESOURCES_DIR = BASE_DIR / "resources"

# Ensure writable directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(WRITE_RESOURCES_DIR, exist_ok=True)

# Static resources (read-only in Vercel)
STATIC_RESOURCES_DIR = Path("./resources")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(title="RAG HR Assistant", version="2.0", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://ragsysetm-backendpart.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RESOURCES_DIR is split into WRITE and STATIC. 
# Helpers will resolve paths dynamically.

# === Models ===
class FileMetadataRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int

class RegisterFileRequest(BaseModel):
    filename: str
    file_type: str
    file_size: int
    blob_url: str
    blob_url: str

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

class QueryResponse(BaseModel):
    response: str
    query: str
    sources: List[Dict[str, Any]] = []
    session_id: Optional[str] = None

# === Endpoints ===

@app.get("/")
def read_root():
    return {
        "message": "RAG HR Assistant API v3.0 (Secure)",
        "status": "operational",
        "features": ["authentication", "user_isolation", "file_management", "chat"]
    }

@app.post("/api/record-metadata")
async def record_metadata(request: FileMetadataRequest, current_user: User = Depends(get_current_user)):
    """Record file metadata in Supabase after frontend uploads to Vercel Blob"""
    try:
        file_record = user_db.add_user_file(
            user_id=current_user.id,
            filename=request.file_name,
            file_type=request.file_type,
            file_size=request.file_size,
            blob_url=request.blob_url,
            user_token=current_user.access_token
        )
        return {"success": True, "file": file_record}
    except Exception as e:
        logger.error(f"Error recording metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Upload a file via multipart/form-data, save locally, and record metadata"""
    try:
        from datetime import datetime
        logger.info(f"📤 Upload started: {file.filename} by user {current_user.id}")
        
        # 1. Save file to local storage (resources directory root)
        # Always write to writable directory
        local_path = WRITE_RESOURCES_DIR / file.filename
        
        with open(local_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        file_size = len(content)
        logger.info(f"📤 File saved: {local_path} ({file_size} bytes)")
        
        # 2. Record metadata in local .file_metadata.json
        existing_files = _read_local_file_metadata()
        # Remove existing entry for same filename (update)
        existing_files = [f for f in existing_files if f.get('filename') != file.filename and f.get('file_name') != file.filename]
        existing_files.append({
            "filename": file.filename,
            "file_name": file.filename,
            "file_type": file.content_type or 'application/octet-stream',
            "file_size": file_size,
            "chunks_created": 0,
            "processed": False,
            "status": "pending",
            "uploaded_at": datetime.utcnow().isoformat(),
        })
        _save_local_file_metadata(existing_files)
        logger.info(f"📤 Metadata saved locally for {file.filename}")
        
        # 3. Also try to record in Supabase (best effort)
        try:
            user_db.add_user_file(
                user_id=current_user.id,
                filename=file.filename,
                file_type=file.content_type or 'application/octet-stream',
                file_size=file_size,
                blob_url=None,
                user_token=current_user.access_token
            )
        except Exception as e:
            logger.warning(f"Supabase metadata record failed (local OK): {e}")
        
        return {
            "success": True,
            "file_name": file.filename,
            "filename": file.filename,
            "file_size": file_size,
            "file_type": file.content_type,
            "message": f"File {file.filename} uploaded successfully"
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/register-file")
async def register_file_endpoint(request: RegisterFileRequest, current_user: User = Depends(get_current_user)):
    """Register a file uploaded to Vercel Blob"""
    try:
        logger.info(f"📝 Registering blob file: {request.filename} ({request.blob_url})")
        
        # 1. Save to Supabase (Primary for Blob)
        try:
            user_db.add_user_file(
                user_id=current_user.id,
                filename=request.filename,
                file_type=request.file_type,
                file_size=request.file_size,
                blob_url=request.blob_url,
                user_token=current_user.access_token
            )
        except Exception as e:
            logger.error(f"Failed to register in Supabase: {e}")
            raise HTTPException(status_code=500, detail="Database registration failed")

        # 2. Update local metadata (for hybrid visibility)
        existing_files = _read_local_file_metadata()
        existing_files = [f for f in existing_files if f.get('filename') != request.filename]
        existing_files.append({
            "filename": request.filename,
            "file_name": request.filename,
            "file_type": request.file_type,
            "file_size": request.file_size,
            "chunks_created": 0,
            "processed": False,
            "status": "pending",
            "uploaded_at": datetime.utcnow().isoformat(),
            "blob_url": request.blob_url
        })
        _save_local_file_metadata(existing_files)
        
        return {"success": True, "message": "File registered successfully"}
    except Exception as e:
        logger.error(f"Error registering file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-file")
async def process_file_endpoint(filename: str, current_user: User = Depends(get_current_user)):
    """Process a file for RAG — uses local metadata and file storage"""
    try:
        from dataprocessor import process_file
        
        logger.info(f"⚙️ Processing file: {filename} for user {current_user.id}")
        
        # 1. Check local metadata for the file
        existing_files = _read_local_file_metadata()
        file_meta = next(
            (f for f in existing_files if f.get('filename') == filename or f.get('file_name') == filename), 
            None
        )
        
        if not file_meta:
            raise HTTPException(status_code=404, detail="File metadata not found")

        # 2. Resolve file path
        # Check writable first, then static
        local_path = WRITE_RESOURCES_DIR / filename
        if not local_path.exists():
            local_path = STATIC_RESOURCES_DIR / filename

        user_temp_dir = WRITE_RESOURCES_DIR / current_user.id
        
        if not local_path.exists():
            local_path = user_temp_dir / filename

        # 3. If local file missing, try to download from Blob URL
        if not local_path.exists():
            blob_url = file_meta.get('blob_url')
            # Check Supabase if local metadata missing blob_url
            if not blob_url:
                try:
                    s_files = user_db.get_user_files(current_user.id, current_user.access_token)
                    s_file = next((f for f in s_files if f['filename'] == filename), None)
                    if s_file:
                        blob_url = s_file.get('blob_url')
                except:
                    pass

            if blob_url:
                logger.info(f"⬇️ Downloading from Blob: {blob_url}")
                try:
                    response = requests.get(blob_url)
                    response.raise_for_status()
                    # Ensure user directory
                    user_temp_dir.mkdir(exist_ok=True)
                    local_path = user_temp_dir / filename
                    with open(local_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"⬇️ Downloaded to {local_path}")
                except Exception as e:
                    logger.error(f"Failed to download blob: {e}")
                    raise HTTPException(status_code=404, detail="File download failed")
            else:
                 raise HTTPException(status_code=404, detail=f"File {filename} not found on disk or blob")
        
        logger.info(f"⚙️ File found at: {local_path}")
        
        # 3. Process and Index with User Isolation
        result = process_file(str(local_path), user_id=current_user.id)
        
        # 4. Update local metadata
        for f in existing_files:
            if f.get('filename') == filename or f.get('file_name') == filename:
                f['processed'] = True
                f['status'] = 'completed'
                f['chunks_created'] = result.get("chunks_created", 0)
                break
        _save_local_file_metadata(existing_files)
        logger.info(f"⚙️ Local metadata updated for {filename}: {result.get('chunks_created', 0)} chunks")
        
        # 5. Also try to update Supabase (best effort)
        try:
            user_db.update_file_processed(
                user_id=current_user.id,
                filename=filename,
                chunks_created=result["chunks_created"],
                user_token=current_user.access_token
            )
        except Exception as e:
            logger.warning(f"Supabase update failed (local OK): {e}")
            
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest, current_user: User = Depends(get_current_user)):
    """Process user query with authenticated session and data isolation"""
    try:
        from QueryProcessor import process_user_query
        
        session_id = request.session_id or str(uuid.uuid4())
        
        # Process with user-specific context
        result = process_user_query(request.query, user_id=current_user.id)
        
        # Save to history
        user_db.add_chat_message(
            user_id=current_user.id,
            session_id=session_id,
            query=request.query,
            response=result["answer"],
            sources=result.get("sources", []),
            user_token=current_user.access_token
        )
        
        return QueryResponse(
            response=result["answer"],
            query=request.query,
            sources=result.get("sources", []),
            session_id=session_id
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _read_local_file_metadata():
    """Read file metadata from local .file_metadata.json"""
    import json as _json
    # Check writable first, then static
    metadata_path = WRITE_RESOURCES_DIR / ".file_metadata.json"
    if not metadata_path.exists():
         metadata_path = STATIC_RESOURCES_DIR / ".file_metadata.json"

    if not metadata_path.exists():
        return []
    
    try:
        with open(metadata_path, "r") as f:
            metadata = _json.load(f)
        
        files = []
        for file_meta in metadata.get("files", []):
            filename = file_meta.get("file_name", "")
            if not filename:
                continue
            
            # Get actual file size from disk
            # Check writable first
            file_path = WRITE_RESOURCES_DIR / filename
            if not file_path.exists():
                file_path = STATIC_RESOURCES_DIR / filename
            
            file_size = int(file_path.stat().st_size) if file_path.exists() else file_meta.get("file_size", 0)
            
            files.append({
                "filename": filename,
                "file_name": filename,
                "file_type": file_meta.get("file_type", "document"),
                "file_size": file_size,
                "chunks_created": file_meta.get("chunks_created", 0),
                "processed": file_meta.get("processed", False),
                "status": "completed" if file_meta.get("processed") else "pending",
                "uploaded_at": file_meta.get("uploaded_at", ""),
            })
        
        return files
    except Exception as e:
        logger.error(f"Error reading local file metadata: {e}")
        return []

def _save_local_file_metadata(files_list):
    """Save file metadata to local .file_metadata.json"""
    import json as _json
    metadata_path = RESOURCES_DIR / ".file_metadata.json"
    
    # Convert to storage format
    storage_files = []
    for i, f in enumerate(files_list):
        storage_files.append({
            "id": i + 1,
            "file_name": f.get("filename") or f.get("file_name", ""),
            "file_type": f.get("file_type", "document"),
            "file_size": f.get("file_size", 0),
            "chunks_created": f.get("chunks_created", 0),
            "processed": f.get("processed", False),
            "uploaded_at": f.get("uploaded_at", ""),
        })
    
    try:
        with open(metadata_path, "w") as fp:
            _json.dump({"files": storage_files}, fp, indent=2)
    except Exception as e:
        logger.error(f"Error saving local file metadata: {e}")

@app.get("/api/files")
async def list_files_endpoint(current_user: User = Depends(get_current_user)):
    """List all files and stats for authenticated user"""
    try:
        logger.info(f"📂 /api/files called by user_id={current_user.id}, email={current_user.email}")
        
        # Read from local .file_metadata.json (primary source)
        files = _read_local_file_metadata()
        logger.info(f"📂 Read {len(files)} files from local metadata")
        
        # Merge with Supabase files (for Vercel/Cloud persistence)
        try:
            supabase_files = user_db.get_user_files(current_user.id, user_token=current_user.access_token)
            if supabase_files:
                local_filenames = {f.get('filename') for f in files}
                for sf in supabase_files:
                    if sf.get('filename') not in local_filenames:
                        files.append(sf)
                logger.info(f"📂 Merged Supabase files. Total: {len(files)}")
        except Exception as e:
            logger.warning(f"Supabase file fetch failed (using local only): {e}")
        
        # Build stats from the files we have
        total_files = len(files)
        processed_files = sum(1 for f in files if f.get('processed'))
        total_chunks = sum(f.get('chunks_created', 0) for f in files)
        total_size = sum(f.get('file_size', 0) for f in files)
        
        stats = {
            "total_files": total_files,
            "processed_files": processed_files,
            "total_chats": 0,
            "total_chunks": total_chunks,
            "total_size_bytes": total_size,
            "files_this_week": 0
        }
        
        # Try to get chat count from Supabase
        try:
            supabase_stats = user_db.get_user_stats(current_user.id, user_token=current_user.access_token)
            stats["total_chats"] = supabase_stats.get("total_chats", 0)
        except Exception:
            pass
        
        logger.info(f"📂 Found {len(files)} files, stats={stats}")
        return {"files": files, "stats": stats}
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/{filename}")
async def delete_file_endpoint(filename: str, current_user: User = Depends(get_current_user)):
    """Delete file record, disk file, and chunks for authenticated user"""
    try:
        logger.info(f"🗑️ Delete requested: {filename} by user {current_user.id}")
        
        # 1. Check local metadata for the file
        existing_files = _read_local_file_metadata()
        file_found = any(
            f.get('filename') == filename or f.get('file_name') == filename 
            for f in existing_files
        )
        
        if not file_found:
            raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
        # 2. Remove from local .file_metadata.json
        updated_files = [
            f for f in existing_files 
            if f.get('filename') != filename and f.get('file_name') != filename
        ]
        _save_local_file_metadata(updated_files)
        logger.info(f"🗑️ Removed {filename} from local metadata")
        
        # 3. Delete physical file from disk
        # Only delete from writable
        local_path = WRITE_RESOURCES_DIR / filename
        if local_path.exists():
            local_path.unlink()
            logger.info(f"🗑️ Deleted file from disk: {local_path}")
        
        # 4. Delete vectors from Pinecone (best effort)
        try:
            from dataprocessor import delete_user_file_vectors
            delete_user_file_vectors(current_user.id, filename)
        except Exception as ve:
            logger.warning(f"Vector deletion failed (non-critical): {ve}")
            
        # 5. Delete from Supabase (best effort)
        try:
            user_db.delete_user_file(current_user.id, filename, user_token=current_user.access_token)
        except Exception as e:
            logger.warning(f"Supabase deletion failed (non-critical): {e}")
        
        return {"success": True, "message": f"File {filename} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chat/history")
async def history_endpoint(session_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Get chat history for authenticated user"""
    try:
        history = user_db.get_chat_history(user_id=current_user.id, session_id=session_id, user_token=current_user.access_token)
        return {"history": history}
    except Exception as e:
        logger.error(f"History error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
