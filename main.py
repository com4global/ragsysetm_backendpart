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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://ragsysetm-backendpart.onrender.com",
        "https://zenzeebot.netlify.app",
        "https://ragsystem-1f65p6bm4-com4globals-projects.vercel.app"
    ],
    allow_origin_regex=r"https://.*-zenzeebot\.netlify\.app", # Allow Deploy Previews
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

@app.post("/api/analyze-legal")
async def analyze_legal_endpoint(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
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
        analysis_result = analyze_legal_document(content, page_count=page_count)
        
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
