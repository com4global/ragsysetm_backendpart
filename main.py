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
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status, Query, BackgroundTasks
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
origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "https://ragsysetm-backendpart.onrender.com",
    "https://zenzeebot.netlify.app",
    "https://ragsystem-1f65p6bm4-com4globals-projects.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*-zenzeebot\.netlify\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount static files for TTS audio
# On production (Linux), use /tmp since app dir is read-only
import pathlib as _pathlib
if os.name == "nt":
    _tts_audio_dir = _pathlib.Path(__file__).parent / "static" / "tts_audio"
else:
    _tts_audio_dir = _pathlib.Path("/tmp") / "tts_audio"
_tts_audio_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/tts_audio", StaticFiles(directory=str(_tts_audio_dir)), name="tts_audio")

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

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    language: Optional[str] = "en"  # "en" for English, "ta" for Tamil

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
            user_token=current_user.access_token
        )
        if not file_record:
            raise HTTPException(status_code=500, detail="Failed to save file metadata to database")
        return {"success": True, "file": file_record}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file_endpoint(
    file: UploadFile = File(...), 
    current_user: User = Depends(get_current_user)
):
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
        
        # 3. New Persistence: Upload to Supabase Storage (Blocking / Synchronous)
        # We MUST block here, otherwise the frontend calls /process immediately and fails
        # because the file isn't in Supabase yet (race condition on serverless).
        blob_url = None
        try:
            # Re-read file content to upload
            with open(local_path, "rb") as f:
                file_content = f.read()

            # Sanitize filename
            clean_filename = f"{int(datetime.utcnow().timestamp())}_{file.filename}"
            
            # Use the user's token or service role
            from supabase import create_client
            import os
            
            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            url = os.getenv("SUPABASE_URL")
            
            if service_key:
                uploader = create_client(url, service_key)
            else:
                uploader = create_client(url, os.getenv("SUPABASE_KEY"))
                uploader.auth.set_session(current_user.access_token, "refresh_token_placeholder") 

            # Upload (Blocking)
            logger.info(f"☁️ Uploading {clean_filename} to Supabase (Sync)...")
            uploader.storage.from_('uploads').upload(
                path=clean_filename,
                file=file_content,
                file_options={"content-type": file.content_type or "application/octet-stream"}
            )
            
            # Get Public URL
            blob_url = uploader.storage.from_('uploads').get_public_url(clean_filename)
            logger.info(f"☁️ Server-side upload success: {blob_url}")

        except Exception as e:
             logger.error(f"❌ Server-side upload failed: {e}")
             # Don't fail completely? Or maybe fail so user knows?
             # Let's proceed, maybe local processing works if on same instance (unlikely on serverless)
        
        # 4. Record metadata in Supabase (Sync) — MUST succeed for process to work
        try:
            db_result = user_db.add_user_file(
                user_id=current_user.id,
                filename=file.filename,
                file_type=file.content_type or 'application/octet-stream',
                file_size=file_size,
                blob_url=blob_url,
                user_token=current_user.access_token
            )
            if not db_result:
                logger.error(f"❌ Supabase metadata save returned empty for {file.filename}")
                raise Exception("Database metadata save returned empty result")
            logger.info(f"✅ Supabase metadata recorded for {file.filename}")
        except Exception as e:
            logger.error(f"❌ Supabase metadata record failed: {e}")
            # Don't silently swallow — this is critical for process step
            raise HTTPException(status_code=500, detail=f"File saved but metadata registration failed: {e}. Please try uploading again.")
        
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
    """Process a file for RAG — uses Supabase for metadata and Blob/Local for content"""
    try:
        from dataprocessor import process_file
        
        logger.info(f"⚙️ Processing file: {filename} for user {current_user.id}")
        
        # 1. Try to get metadata from Supabase (Primary for Vercel)
        file_meta = None
        blob_url = None
        try:
            # Add strict retry logic for "just uploaded" files
            import time
            retries = 3
            for attempt in range(retries):
                s_files = user_db.get_user_files(current_user.id, current_user.access_token)
                # Flexible matching for filename/file_name
                file_meta = next((f for f in s_files if f.get('filename') == filename or f.get('file_name') == filename), None)
                
                if file_meta:
                    blob_url = file_meta.get('blob_url')
                    logger.info(f"✅ Found metadata in Supabase for {filename} (Attempt {attempt+1})")
                    break
                else:
                    logger.warning(f"Metadata not found in Supabase for {filename} (Attempt {attempt+1}/{retries})")
                    time.sleep(1) # Wait for propagation if needed
                    
        except Exception as e:
            logger.warning(f"Supabase metadata fetch failed: {e}")

        # 2. Fallback to local metadata (Legacy/Local Dev)
        if not file_meta:
            existing_files = _read_local_file_metadata()
            file_meta = next(
                (f for f in existing_files if f.get('filename') == filename or f.get('file_name') == filename), 
                None
            )
            if file_meta:
                 blob_url = file_meta.get('blob_url')
                 logger.info(f"✅ Found metadata in local storage for {filename} (Fallback)")
        
        if not file_meta:
            # DEBUG INFO
            logger.error(f"❌ CRITICAL: Metadata missing for {filename}")
            logger.error(f"User ID: {current_user.id}")
            raise HTTPException(status_code=404, detail=f"File metadata not found for {filename}. Please try uploading again.")

        # 3. Resolve file path
        # Check writable first, then static
        local_path = WRITE_RESOURCES_DIR / filename
        if not local_path.exists():
            local_path = STATIC_RESOURCES_DIR / filename

        user_temp_dir = WRITE_RESOURCES_DIR / current_user.id
        
        if not local_path.exists():
            local_path = user_temp_dir / filename

        # 4. If local file missing, try to download from Blob URL
        if not local_path.exists():
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
                    error_detail = "File download failed."
                    if "403" in str(e):
                        error_detail = "Access Denied: Is your Supabase 'uploads' bucket set to Public?"
                    elif "404" in str(e):
                        error_detail = "File not found in storage. It may have been deleted."
                    raise HTTPException(status_code=404, detail=error_detail)
            else:
                 # Detailed error for user
                 logger.warning(f"❌ File {filename} has metadata but no content (Blob URL missing)")
                 raise HTTPException(
                     status_code=404, 
                     detail="File content not found. This file may have been uploaded before persistent storage was enabled. Please delete and re-upload it."
                 )
        
        logger.info(f"⚙️ File found at: {local_path}")
        
        # 5. Process and Index with User Isolation
        result = process_file(str(local_path), user_id=current_user.id)
        
        # 6. Update metadata (Supabase Primary)
        metadata_updated = False
        try:
            user_db.update_file_processed(
                user_id=current_user.id,
                filename=filename,
                chunks_created=result["chunks_created"],
                user_token=current_user.access_token
            )
            metadata_updated = True
            logger.info(f"✅ Supabase status updated for {filename}")
        except Exception as e:
            logger.error(f"❌ Supabase status update failed for {filename}: {e}")
            # Don't fail the whole processing, but flag the issue

        # Update local (Best effort)
        existing_files = _read_local_file_metadata()
        for f in existing_files:
            if f.get('filename') == filename or f.get('file_name') == filename:
                f['processed'] = True
                f['status'] = 'completed'
                f['chunks_created'] = result.get("chunks_created", 0)
                break
        _save_local_file_metadata(existing_files)
            
        return {"success": True, "result": result}
    except HTTPException:
        raise
    except ValueError as ve:
        logger.error(f"Validation error processing {filename}: {ve}")
        raise HTTPException(status_code=422, detail=f"Processing failed: {str(ve)}")
    except Exception as e:
        logger.error(f"Error processing file {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest, current_user: User = Depends(get_current_user)):
    """Process user query with authenticated session and data isolation"""
    try:
        from QueryProcessor import process_user_query
        
        session_id = request.session_id or str(uuid.uuid4())
        
        # Process with user-specific context
        # Pass language preference to get response in selected language
        language = request.language or "en"
        result = process_user_query(request.query, user_id=current_user.id, language=language)
        
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
    metadata_path = WRITE_RESOURCES_DIR / ".file_metadata.json"
    
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

# ============================================================
# EDTECH AI TEACHER ENDPOINTS
# ============================================================

@app.get("/api/edtech/documents")
async def edtech_list_documents(
    current_user: User = Depends(get_current_user)
):
    """List user's processed documents available for AI Teacher lessons."""
    try:
        # Get files from Supabase (the same source used by admin panel)
        supabase_files = user_db.get_user_files(current_user.id, user_token=current_user.access_token)
        
        # Only show processed files (those with chunks in the vector DB)
        processed_docs = []
        for f in supabase_files:
            if f.get('processed'):
                processed_docs.append({
                    "filename": f.get('filename'),
                    "file_type": f.get('file_type', 'document'),
                    "chunks_created": f.get('chunks_created', 0),
                    "uploaded_at": f.get('created_at')
                })
        
        return {"success": True, "documents": processed_docs}
    
    except Exception as e:
        logger.error(f"EdTech document list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/edtech/chapters")
async def edtech_get_chapters(
    doc_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get all chapters/sections detected in a processed document."""
    try:
        from vectorstore import index, get_user_namespaces
        from collections import defaultdict
        import re as _re

        namespaces = get_user_namespaces(current_user.id)
        all_chunks = []

        for ns in namespaces:
            try:
                dummy_vec = [0.0] * 1536
                res = index.query(
                    vector=dummy_vec,
                    top_k=10000,
                    include_metadata=True,
                    namespace=ns,
                    filter={"doc_name": {"$eq": doc_name}}
                )
                for match in res.matches:
                    meta = match.metadata
                    text = meta.get("text", "")
                    page = meta.get("page", "")
                    chapter = meta.get("chapter", "")
                    if text:
                        all_chunks.append({
                            "text": text,
                            "page": page,
                            "chapter": chapter
                        })
            except Exception as e:
                logger.warning(f"Namespace {ns} query failed: {e}")
                continue

        if not all_chunks:
            return {"success": True, "chapters": [], "message": f"No chunks found for document '{doc_name}'."}

        # Group chunks by chapter
        chapter_groups = defaultdict(list)
        for c in all_chunks:
            ch = c.get("chapter", "") or "Untitled Section"
            chapter_groups[ch].append(c)

        def _page_num(p):
            nums = _re.findall(r'\d+', str(p))
            return int(nums[0]) if nums else 0

        # Build chapter list with metadata
        chapters = []
        for ch_name, ch_chunks in chapter_groups.items():
            page_nums = [_page_num(c.get("page", "0")) for c in ch_chunks]
            page_nums = [p for p in page_nums if p > 0]
            chapters.append({
                "name": ch_name,
                "chunk_count": len(ch_chunks),
                "page_start": min(page_nums) if page_nums else 0,
                "page_end": max(page_nums) if page_nums else 0,
                "preview": ch_chunks[0]["text"][:200] + "..." if ch_chunks else ""
            })

        # Sort by page_start to maintain book order
        chapters.sort(key=lambda x: x["page_start"])

        logger.info(f"📚 EdTech: Found {len(chapters)} chapters in '{doc_name}' ({len(all_chunks)} total chunks)")

        return {
            "success": True,
            "chapters": chapters,
            "document": doc_name,
            "total_chunks": len(all_chunks)
        }

    except Exception as e:
        logger.error(f"EdTech chapter listing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/edtech/topics")
async def edtech_extract_topics(
    doc_name: str,
    current_user: User = Depends(get_current_user),
    language: str = "en",
    chapter: str = ""
):
    """
    Extract teaching topics from a document.
    If 'chapter' is provided, extracts DETAILED topics from only that chapter's chunks.
    Otherwise, samples across the entire document (fallback for small docs).
    """
    try:
        from edtech_service import extract_topics
        from vectorstore import index, get_user_namespaces
        import re as _re

        namespaces = get_user_namespaces(current_user.id)
        all_chunks = []

        # Build Pinecone filter — optionally filter by chapter
        if chapter:
            pinecone_filter = {
                "$and": [
                    {"doc_name": {"$eq": doc_name}},
                    {"chapter": {"$eq": chapter}}
                ]
            }
        else:
            pinecone_filter = {"doc_name": {"$eq": doc_name}}

        for ns in namespaces:
            try:
                dummy_vec = [0.0] * 1536
                res = index.query(
                    vector=dummy_vec,
                    top_k=10000,
                    include_metadata=True,
                    namespace=ns,
                    filter=pinecone_filter
                )
                for match in res.matches:
                    meta = match.metadata
                    text = meta.get("text", "")
                    page = meta.get("page", "")
                    ch = meta.get("chapter", "")
                    if text:
                        all_chunks.append({
                            "text": text,
                            "page": page,
                            "chapter": ch
                        })
            except Exception as e:
                logger.warning(f"Namespace {ns} query failed: {e}")
                continue

        if not all_chunks:
            msg = f"No chunks found for chapter '{chapter}'" if chapter else f"No chunks found for '{doc_name}'"
            return {"success": True, "topics": [], "message": msg}

        # Sort by page number
        def _page_num(x):
            nums = _re.findall(r'\d+', str(x.get("page", "0")))
            return int(nums[0]) if nums else 0
        all_chunks.sort(key=_page_num)

        logger.info(f"📚 EdTech topics: {len(all_chunks)} chunks for '{doc_name}'" +
                     (f" chapter='{chapter}'" if chapter else ""))

        CHAR_BUDGET = 15000

        if chapter:
            # CHAPTER-SPECIFIC: use all chunks from this chapter for detailed topics
            content_parts = []
            total_chars = 0
            for c in all_chunks:
                part = f"[Page {c['page']}]\n{c['text']}"
                if total_chars + len(part) > CHAR_BUDGET:
                    break
                content_parts.append(part)
                total_chars += len(part)
        else:
            # WHOLE DOC fallback: sample strategically
            MAX_SAMPLE = 40
            if len(all_chunks) > MAX_SAMPLE:
                step = max(1, len(all_chunks) // MAX_SAMPLE)
                sampled = [all_chunks[i] for i in range(0, len(all_chunks), step)][:MAX_SAMPLE]
            else:
                sampled = all_chunks

            content_parts = []
            total_chars = 0
            for c in sampled:
                ch_label = f" | Chapter: {c['chapter']}" if c.get('chapter') else ""
                part = f"[Page {c['page']}{ch_label}]\n{c['text']}"
                if total_chars + len(part) > CHAR_BUDGET:
                    break
                content_parts.append(part)
                total_chars += len(part)

        combined = "\n\n---\n\n".join(content_parts)
        logger.info(f"📚 Sending {len(content_parts)} chunks ({total_chars} chars) to LLM" +
                     (f" [chapter: {chapter}]" if chapter else " [whole doc]"))

        topics = extract_topics(combined, language, [doc_name])

        return {
            "success": True,
            "topics": topics,
            "document": doc_name,
            "chapter": chapter,
            "chunks_used": len(content_parts),
            "total_chunks": len(all_chunks)
        }

    except Exception as e:
        logger.error(f"EdTech topic extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════════════════
# ▸ Lesson Cache Helpers (Supabase DB + Storage)
# ══════════════════════════════════════════════════════════════════════

def _lesson_cache_key(user_id: str, doc_name: str, topic: str, language: str, lesson_type: str) -> str:
    """Generate a deterministic cache key."""
    import hashlib
    raw = f"{user_id}:{doc_name}:{topic}:{language}:{lesson_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached_lesson(cache_key: str):
    """Check lesson_cache table for a matching entry. Returns dict or None."""
    try:
        result = supabase.table("lesson_cache").select("*").eq("cache_key", cache_key).limit(1).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        logger.warning(f"Lesson cache lookup failed (non-fatal): {e}")
    return None


def _save_lesson_cache(
    user_id: str, cache_key: str, topic: str, doc_name: str,
    language: str, lesson_type: str, lesson_json: dict,
    audio_storage_paths: list = None
):
    """Save a lesson to the cache table."""
    try:
        supabase.table("lesson_cache").upsert({
            "user_id": user_id,
            "cache_key": cache_key,
            "topic": topic,
            "doc_name": doc_name,
            "language": language,
            "lesson_type": lesson_type,
            "lesson_json": lesson_json,
            "audio_storage_paths": audio_storage_paths or [],
            "updated_at": datetime.utcnow().isoformat()
        }, on_conflict="cache_key").execute()
        logger.info(f"✅ Lesson cached: {topic} ({lesson_type})")
    except Exception as e:
        logger.warning(f"Lesson cache save failed (non-fatal): {e}")


def _upload_audio_to_storage(local_path: str, storage_path: str) -> str:
    """Upload an audio file to Supabase Storage 'tts-cache' bucket. Returns public URL."""
    try:
        with open(local_path, "rb") as f:
            audio_bytes = f.read()
        supabase.storage.from_("tts-cache").upload(
            path=storage_path,
            file=audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"}
        )
        # Build public URL
        sb_url = os.getenv("SUPABASE_URL", "")
        return f"{sb_url}/storage/v1/object/public/tts-cache/{storage_path}"
    except Exception as e:
        logger.warning(f"Audio upload to Storage failed: {e}")
        return ""


@app.post("/api/edtech/generate-lesson")
async def edtech_generate_lesson(
    topic: str = Form(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """Generate an AI teacher dialogue lesson for a specific topic."""
    try:
        from edtech_service import generate_teacher_dialogue
        from embedder import embed_User_query
        from vectorstore import search_user_documents

        # ── 1. Check cache first ──
        cache_key = _lesson_cache_key(current_user.id, "", topic, language, "conversation")
        cached = _get_cached_lesson(cache_key)
        if cached:
            logger.info(f"🎯 Lesson cache HIT: {topic}")
            return {"success": True, "lesson": cached["lesson_json"], "cached": True}

        # ── 2. Cache miss — generate from scratch ──
        logger.info(f"🔄 Lesson cache MISS: {topic}")

        # Search for relevant chunks about this topic
        query_vec = embed_User_query(topic)
        results = search_user_documents(query_vec, current_user.id, top_k=10)

        if not results:
            return {"success": False, "detail": "No relevant content found for this topic. Please process more documents."}

        # Include document references so the dialogue is grounded
        chunks_with_refs = []
        for r in results:
            text = r.get("text", "")
            doc_name = r.get("doc_name", "Unknown")
            page = r.get("page", "")
            if text:
                chunks_with_refs.append(f"[From: {doc_name}, Page: {page}]\n{text}")

        if not chunks_with_refs:
            return {"success": False, "detail": "No relevant content found for this topic."}

        combined = "\n\n---\n\n".join(chunks_with_refs)
        lesson = generate_teacher_dialogue(topic, combined, language)

        # ── 3. Generate TTS audio for each dialogue line ──
        audio_urls = []
        audio_storage_paths = []
        voice_map = lesson.get("voice_map", {})
        dialogue = lesson.get("dialogue", [])
        if dialogue and voice_map:
            try:
                from heygen_service import generate_dialogue_audio, TTS_AUDIO_DIR
                audio_files = generate_dialogue_audio(
                    dialogue_lines=dialogue,
                    voice_map=voice_map,
                    topic=topic,
                    user_id=current_user.id,
                    doc_name=doc_name
                )
                # Upload each audio file to Supabase Storage
                for f in audio_files:
                    if f:
                        local_file = TTS_AUDIO_DIR / f
                        storage_path = f"dialogue/{current_user.id}/{f}"
                        public_url = _upload_audio_to_storage(str(local_file), storage_path)
                        if public_url:
                            audio_urls.append(public_url)
                            audio_storage_paths.append(storage_path)
                        else:
                            # Fallback to local static path
                            audio_urls.append(f"/static/tts_audio/{f}")
                            audio_storage_paths.append("")
                    else:
                        audio_urls.append("")
                        audio_storage_paths.append("")
            except Exception as audio_err:
                logger.warning(f"Dialogue audio generation failed (non-fatal): {audio_err}")
                audio_urls = []

        lesson["audio_urls"] = audio_urls

        # ── 4. Save to cache ──
        _save_lesson_cache(
            user_id=current_user.id,
            cache_key=cache_key,
            topic=topic,
            doc_name=doc_name if chunks_with_refs else "",
            language=language,
            lesson_type="conversation",
            lesson_json=lesson,
            audio_storage_paths=audio_storage_paths
        )

        return {"success": True, "lesson": lesson}

    except Exception as e:
        logger.error(f"EdTech lesson generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/edtech/ask")
async def edtech_ask_question(
    question: str = Form(...),
    topic: str = Form(""),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """Answer a student's question using RAG within the lesson context."""
    try:
        from QueryProcessor import process_user_query

        # Enhance question with topic context
        enhanced_q = f"[Topic: {topic}] {question}" if topic else question
        result = process_user_query(enhanced_q, user_id=current_user.id, language=language)

        return {"success": True, "answer": result.get("answer", ""), "sources": result.get("sources", [])}

    except Exception as e:
        logger.error(f"EdTech Q&A failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# HEYGEN VIDEO GENERATION ENDPOINTS
# ============================================================

@app.post("/api/edtech/generate-video")
async def edtech_generate_video(
    topic: str = Form(...),
    doc_name: str = Form(""),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """
    Generate an AI teaching video for a specific topic.
    Uses HeyGen Video Agent API.
    Pipeline: chunks → LLM script → HeyGen → video_id (async)
    """
    try:
        from heygen_service import generate_video_for_topic, get_cached_video
        from embedder import embed_User_query
        from vectorstore import search_user_documents

        # 1. Check cache — return immediately if video exists
        cached = get_cached_video(current_user.id, doc_name, topic)
        if cached and cached.get("video_url"):
            return {
                "success": True,
                "status": "completed",
                "video_url": cached["video_url"],
                "video_id": cached.get("video_id", ""),
                "cached": True,
                "message": "Video already generated!"
            }

        # 2. Search for relevant chunks about this topic (same as lesson generation)
        query_vec = embed_User_query(topic)
        results = search_user_documents(query_vec, current_user.id, top_k=10)

        if not results:
            return {
                "success": False,
                "status": "failed",
                "error": "No relevant content found for this topic. Please process more documents."
            }

        # 3. Combine chunks with source references
        chunks_with_refs = []
        for r in results:
            text = r.get("text", "")
            source = r.get("doc_name", "Unknown")
            page = r.get("page", "")
            if text:
                chunks_with_refs.append(f"[From: {source}, Page: {page}]\n{text}")

        if not chunks_with_refs:
            return {
                "success": False,
                "status": "failed",
                "error": "No relevant content found for this topic."
            }

        combined_content = "\n\n---\n\n".join(chunks_with_refs)

        # 4. Generate video (script + HeyGen call)
        result = generate_video_for_topic(
            topic=topic,
            content=combined_content,
            user_id=current_user.id,
            doc_name=doc_name,
            language=language
        )

        return {
            "success": result.get("status") != "failed",
            **result
        }

    except Exception as e:
        logger.error(f"EdTech video generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/edtech/video-status")
async def edtech_video_status(
    video_id: str,
    topic: str = "",
    doc_name: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Check the status of a HeyGen video generation.
    The frontend polls this endpoint until status = 'completed' or 'failed'.
    When completed, the video URL is cached for future use.
    """
    try:
        from heygen_service import check_video_status, update_video_cache

        result = check_video_status(video_id)

        # If video is completed, cache the URL for future requests
        if result.get("status") == "completed" and result.get("video_url"):
            if topic and current_user.id:
                update_video_cache(
                    user_id=current_user.id,
                    doc_name=doc_name,
                    topic=topic,
                    video_url=result["video_url"],
                    video_id=video_id,
                    thumbnail_url=result.get("thumbnail_url", "")
                )

        return {"success": True, **result}

    except Exception as e:
        logger.error(f"Video status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/edtech/video-cache")
async def edtech_video_cache(
    topic: str,
    doc_name: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Quick check: does a completed video already exist for this topic?
    Used by the frontend to show 'Play Video' vs 'Generate Video' button.
    """
    try:
        from heygen_service import get_cached_video

        cached = get_cached_video(current_user.id, doc_name, topic)

        if cached and cached.get("video_url"):
            return {
                "success": True,
                "has_video": True,
                "video_url": cached["video_url"],
                "video_id": cached.get("video_id", ""),
                "thumbnail_url": cached.get("thumbnail_url", "")
            }

        return {"success": True, "has_video": False}

    except Exception as e:
        logger.error(f"Video cache check failed: {e}")
        return {"success": True, "has_video": False}


@app.post("/api/edtech/generate-tts-video")
async def edtech_generate_tts_video(
    topic: str = Form(...),
    doc_name: str = Form(""),
    language: str = Form("en"),
    voice: str = Form("nova"),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a TTS teaching video (script + audio) using OpenAI TTS.
    Returns audio URL + sentences for subtitle sync.
    This is synchronous — no polling needed (takes ~5-10 seconds).
    """
    try:
        from heygen_service import generate_tts_video_for_topic, TTS_AUDIO_DIR
        from embedder import embed_User_query
        from vectorstore import search_user_documents

        # ── 1. Check cache first ──
        cache_key = _lesson_cache_key(current_user.id, doc_name, topic, language, "tts_video")
        cached = _get_cached_lesson(cache_key)
        if cached:
            logger.info(f"🎯 TTS video cache HIT: {topic}")
            return {"success": True, **cached["lesson_json"], "cached": True}

        # ── 2. Cache miss — generate from scratch ──
        logger.info(f"🔄 TTS video cache MISS: {topic}")

        # Search for relevant chunks
        query_vec = embed_User_query(topic)
        results = search_user_documents(query_vec, current_user.id, top_k=10)

        if not results:
            return {
                "success": False,
                "status": "failed",
                "error": "No relevant content found for this topic."
            }

        chunks_with_refs = []
        for r in results:
            text = r.get("text", "")
            source = r.get("doc_name", "Unknown")
            page = r.get("page", "")
            if text:
                chunks_with_refs.append(f"[From: {source}, Page: {page}]\n{text}")

        if not chunks_with_refs:
            return {
                "success": False,
                "status": "failed",
                "error": "No relevant content found."
            }

        combined_content = "\n\n---\n\n".join(chunks_with_refs)

        result = generate_tts_video_for_topic(
            topic=topic,
            content=combined_content,
            user_id=current_user.id,
            doc_name=doc_name,
            language=language,
            voice=voice
        )

        # ── 3. Upload audio to Supabase Storage + build response ──
        audio_storage_paths = []
        if result.get("status") == "completed" and result.get("audio_filename"):
            local_file = TTS_AUDIO_DIR / result["audio_filename"]
            storage_path = f"tts_video/{current_user.id}/{result['audio_filename']}"
            public_url = _upload_audio_to_storage(str(local_file), storage_path)
            if public_url:
                result["audio_url"] = public_url
                audio_storage_paths = [storage_path]
            else:
                result["audio_url"] = f"/static/tts_audio/{result['audio_filename']}"

        response = {"success": result.get("status") != "failed", **result}

        # ── 4. Save to cache ──
        if result.get("status") == "completed":
            _save_lesson_cache(
                user_id=current_user.id,
                cache_key=cache_key,
                topic=topic,
                doc_name=doc_name,
                language=language,
                lesson_type="tts_video",
                lesson_json=response,
                audio_storage_paths=audio_storage_paths
            )

        return response

    except Exception as e:
        logger.error(f"TTS video generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/analyze-legal")
async def analyze_legal_endpoint(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """Analyze a legal document (File or URL) with comprehensive structured analysis"""
    try:
        from legal_service import analyze_legal_document
        from file_processor import read_file
        import json
        import traceback
        
        content = ""
        page_count = None
        
        # 1. Handle File Upload
        if file:
            file_content = await file.read()
            
            # Always save to temp and use file_processor for proper extraction
            temp_path = BASE_DIR / f"temp_{file.filename}"
            try:
                with open(temp_path, "wb") as tmp_f:
                    tmp_f.write(file_content)
                
                try:
                    pages, file_type = read_file(str(temp_path))
                    page_count = len(pages)
                    content = "\n\n".join([p["text"] for p in pages if p.get("text")])
                    logger.info(f"Legal analysis: extracted {page_count} pages from {file.filename}")
                except ValueError:
                    # Unsupported file type — try plain text decode
                    try:
                        content = file_content.decode('utf-8')
                    except UnicodeDecodeError:
                        content = file_content.decode('latin-1', errors='ignore')
            finally:
                if temp_path.exists():
                    temp_path.unlink()

        # 2. Handle URL
        elif url:
            content = f"Content from URL: {url}"

        if not content or not content.strip():
            raise HTTPException(status_code=400, detail="No content could be extracted from the file")

        # 3. Analyze with enhanced service
        logger.info(f"Legal analysis starting for {file.filename if file else url} ({len(content)} chars, {page_count} pages)")
        analysis_result = analyze_legal_document(content, page_count=page_count, language=language or "en")
        
        # Parse if string
        if isinstance(analysis_result, str):
            analysis_result = json.loads(analysis_result)

        return {"success": True, "analysis": analysis_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legal Analysis failed: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/files")
async def list_files_endpoint(current_user: User = Depends(get_current_user)):
    """List files strictly for the authenticated user (Supabase Source of Truth)"""
    try:
        logger.info(f"📂 /api/files called by user_id={current_user.id}, email={current_user.email}")
        
        # 1. SOURCE OF TRUTH: Supabase
        # We ONLY show files that actully belong to this user in the DB.
        supabase_files = []
        try:
            supabase_files = user_db.get_user_files(current_user.id, user_token=current_user.access_token)
            logger.info(f"📂 Retrieved {len(supabase_files)} files from Supabase for user {current_user.id}")
        except Exception as e:
            logger.error(f"❌ Critical: Supabase file fetch failed: {e}")
            raise HTTPException(status_code=500, detail="Could not fetch user files")

        # 2. Enrich with Local Metadata (Status/Progress) ONLY for these files
        # We do NOT add files from local metadata that aren't in Supabase (prevents leaks)
        local_files_map = {f.get('filename'): f for f in _read_local_file_metadata()}
        
        final_files_list = []
        
        for sf in supabase_files:
            filename = sf.get('filename')
            
            # Base object from Supabase
            file_obj = {
                "filename": filename,
                "file_name": filename, # frontend might use either
                "file_type": sf.get('file_type', 'document'),
                "file_size": sf.get('file_size', 0),
                "blob_url": sf.get('blob_url'),
                "uploaded_at": sf.get('created_at'),
                "processed": sf.get('processed', False),
                "chunks_created": sf.get('chunks_created', 0),
                "status": "completed" if sf.get('processed') else "pending"
            }
            
            # Enrich with local info if available (e.g. if currently processing)
            if filename in local_files_map:
                local_f = local_files_map[filename]
                # If local says processed, trust it for UI update speed
                if local_f.get('processed'):
                    file_obj['processed'] = True
                    file_obj['status'] = 'completed'
                    file_obj['chunks_created'] = local_f.get('chunks_created', file_obj['chunks_created'])
            
            final_files_list.append(file_obj)
        
        # Stats
        stats = {
            "total_files": len(final_files_list),
            "processed_files": sum(1 for f in final_files_list if f.get('processed')),
            "total_chunks": sum(f.get('chunks_created', 0) for f in final_files_list),
            "total_size_bytes": sum(f.get('file_size', 0) for f in final_files_list),
        }
        
        # Try to get chat count from Supabase
        try:
            supabase_stats = user_db.get_user_stats(current_user.id, user_token=current_user.access_token)
            stats["total_chats"] = supabase_stats.get("total_chats", 0)
        except Exception:
            pass
        
        return {"files": final_files_list, "stats": stats}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/{filename}")
async def delete_file_endpoint(filename: str, current_user: User = Depends(get_current_user)):
    """Delete file record, disk file, and chunks for authenticated user"""
    try:
        logger.info(f"🗑️ Delete requested: {filename} by user {current_user.id}")
        
        # 1. Start with Supabase (Primary)
        file_found = False
        try:
            file_found = user_db.file_belongs_to_user(current_user.id, filename, current_user.access_token)
        except Exception as e:
            logger.warning(f"Supabase check failed: {e}")

        # 2. Check local if not in Supabase (Legacy)
        if not file_found:
            existing_files = _read_local_file_metadata()
            file_found = any(
                f.get('filename') == filename or f.get('file_name') == filename 
                for f in existing_files
            )
        
        if not file_found:
             # If strictly not found anywhere, 404. 
             # But for delete, we might want to be permissive to allow cleanup of "zombie" files
             logger.warning(f"File {filename} not found in DBs, attempting cleanup anyway")
        
        # 3. Delete from Supabase (Primary)
        try:
            user_db.delete_user_file(current_user.id, filename, user_token=current_user.access_token)
            logger.info(f"🗑️ Removed {filename} from Supabase")
        except Exception as e:
             logger.error(f"Supabase deletion failed: {e}")

        # 4. Remove from local .file_metadata.json
        existing_files = _read_local_file_metadata()
        updated_files = [
            f for f in existing_files 
            if f.get('filename') != filename and f.get('file_name') != filename
        ]
        if len(existing_files) != len(updated_files):
             _save_local_file_metadata(updated_files)
             logger.info(f"🗑️ Removed {filename} from local metadata")
        
        # 5. Delete physical file from disk (Cleanup)
        # Only delete from writable
        local_path = WRITE_RESOURCES_DIR / filename
        if local_path.exists():
            local_path.unlink()
            logger.info(f"🗑️ Deleted file from disk: {local_path}")
            
        # Also clean up user temp dir copy if exists
        user_temp_file = WRITE_RESOURCES_DIR / current_user.id / filename
        if user_temp_file.exists():
            user_temp_file.unlink()
        
        # 6. Delete vectors from Pinecone (Crucial)
        try:
            from dataprocessor import delete_user_file_vectors
            delete_user_file_vectors(current_user.id, filename)
            logger.info(f"🗑️ Deleted vectors for {filename}")
        except Exception as ve:
            logger.warning(f"Vector deletion failed (non-critical): {ve}")
            
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
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
