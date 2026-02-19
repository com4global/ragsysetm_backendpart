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
    global _job_queue, _worker_tasks
    # Startup
    logger.info("Starting up...")
    _job_queue = asyncio.Queue()
    
    # Start worker pool
    for i in range(MAX_CONCURRENT_WORKERS):
        task = asyncio.create_task(_job_worker(i))
        _worker_tasks.append(task)
    logger.info(f"🚀 Started {MAX_CONCURRENT_WORKERS} background processing workers")
    
    # Recovery: re-queue any stale jobs from previous runs
    try:
        stale = supabase.table("batch_jobs").select("*").in_("status", ["queued", "processing"]).execute()
        for job in (stale.data or []):
            _update_batch_status(job["id"], "queued", progress=0)
            logger.info(f"♻️ Re-queued stale job: {job.get('doc_name', 'unknown')} ({job['id']})")
            # Note: we can't re-queue without access_token; mark as failed instead
            _update_batch_status(job["id"], "failed", error="Server restarted. Please re-process this file.")
    except Exception as e:
        logger.warning(f"Stale job recovery skipped: {e}")
    
    yield
    
    # Shutdown: stop workers gracefully
    logger.info("Shutting down workers...")
    for _ in range(MAX_CONCURRENT_WORKERS):
        await _job_queue.put(None)  # Poison pill
    for task in _worker_tasks:
        task.cancel()
    _worker_tasks.clear()
    logger.info("Workers stopped.")

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

import asyncio

# ── Job Queue for Background Processing ──
# Limits concurrent processing to avoid overwhelming OpenAI rate limits
MAX_CONCURRENT_WORKERS = 3
_processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
_job_queue: asyncio.Queue = None  # Initialized in lifespan
_worker_tasks: list = []

async def _job_worker(worker_id: int):
    """Background worker that pulls jobs from the queue and processes them."""
    logger.info(f"👷 Worker {worker_id} started")
    while True:
        try:
            job = await _job_queue.get()
            if job is None:  # Poison pill for shutdown
                break
            
            user_id, filename, access_token, job_id = job
            logger.info(f"👷 Worker {worker_id} picked up: {filename} (job {job_id})")
            
            async with _processing_semaphore:
                try:
                    await _background_process_and_pregenerate(user_id, filename, access_token, job_id)
                except Exception as e:
                    logger.error(f"❌ Worker {worker_id} failed on {filename}: {e}")
                    _update_batch_status(job_id, "failed", error=str(e))
            
            _job_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Worker {worker_id} unexpected error: {e}")
    logger.info(f"👷 Worker {worker_id} stopped")

def _enqueue_processing(user_id: str, filename: str, access_token: str, job_id: str):
    """Queue a file for background processing. Returns immediately."""
    if _job_queue is not None:
        _job_queue.put_nowait((user_id, filename, access_token, job_id))
        logger.info(f"📥 Queued {filename} for processing (job {job_id}, queue size: ~{_job_queue.qsize()})")
    else:
        # Fallback if queue not initialized
        asyncio.create_task(_background_process_and_pregenerate(user_id, filename, access_token, job_id))
        logger.warning(f"⚠️ Job queue not ready, falling back to direct task for {filename}")


# ── Background Processing Helpers ──

def _update_batch_status(job_id: str, status: str, progress: int = 0,
                         completed_steps: int = 0, total_steps: int = 0, error: str = None):
    """Update batch job status in Supabase."""
    try:
        data = {
            "status": status,
            "progress": progress,
            "completed_steps": completed_steps,
            "total_steps": total_steps,
            "updated_at": datetime.utcnow().isoformat()
        }
        if error:
            data["error"] = error
        supabase.table("batch_jobs").update(data).eq("id", job_id).execute()
    except Exception as e:
        logger.warning(f"Batch status update failed: {e}")


async def _background_process_and_pregenerate(user_id: str, filename: str, access_token: str, job_id: str):
    """
    Background worker: process document → extract topics → pre-generate lessons & videos.
    Runs as an asyncio task after upload returns to user.
    """
    import asyncio
    try:
        logger.info(f"🔄 Background processing started: {filename} for user {user_id}")
        _update_batch_status(job_id, "processing", progress=5, total_steps=4, completed_steps=0)

        # ── Step 1: Process file (chunking + embedding) ──
        from dataprocessor import process_file
        import time as _time

        # Get file metadata
        file_meta = None
        blob_url = None
        s_files = user_db.get_user_files(user_id, access_token)
        file_meta = next((f for f in s_files if f.get('filename') == filename or f.get('file_name') == filename), None)
        if file_meta:
            blob_url = file_meta.get('blob_url')

        # Resolve local path
        local_path = WRITE_RESOURCES_DIR / filename
        if not local_path.exists():
            local_path = STATIC_RESOURCES_DIR / filename
        user_temp_dir = WRITE_RESOURCES_DIR / user_id
        if not local_path.exists():
            local_path = user_temp_dir / filename
        if not local_path.exists() and blob_url:
            logger.info(f"⬇️ [BG] Downloading from blob: {blob_url}")
            response = requests.get(blob_url)
            response.raise_for_status()
            user_temp_dir.mkdir(exist_ok=True)
            local_path = user_temp_dir / filename
            with open(local_path, 'wb') as f:
                f.write(response.content)

        if not local_path.exists():
            _update_batch_status(job_id, "failed", error="File not found locally or in storage")
            return

        # Run chunking + embedding in a THREAD POOL (this is CPU/IO-bound!)
        # Without run_in_executor, this blocks the entire event loop → backend unresponsive
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: process_file(str(local_path), user_id=user_id))
        chunks_created = result.get("chunks_created", 0)

        # Update file metadata
        try:
            user_db.update_file_processed(user_id=user_id, filename=filename,
                                          chunks_created=chunks_created, user_token=access_token)
        except Exception as e:
            logger.warning(f"[BG] Metadata update failed: {e}")

        _update_batch_status(job_id, "extracting_topics", progress=30, completed_steps=1)
        logger.info(f"✅ [BG] Step 1 done: {filename} chunked ({chunks_created} chunks)")

        # ── Step 2: Extract chapters + topics ──
        from edtech_service import extract_topics
        from vectorstore import index, get_user_namespaces
        import re as _re

        # First get chapters
        namespaces = get_user_namespaces(user_id)
        all_chunks = []
        doc_name = filename.rsplit('.', 1)[0]  # Remove extension for doc_name matching

        for ns in namespaces:
            try:
                dummy_vec = [0.0] * 1536
                res = await loop.run_in_executor(None, lambda ns=ns: index.query(
                    vector=dummy_vec, top_k=10000, include_metadata=True,
                    namespace=ns, filter={"doc_name": {"$eq": filename}}
                ))
                for match in res.matches:
                    meta = match.metadata
                    text = meta.get("text", "")
                    page = meta.get("page", "")
                    ch = meta.get("chapter", "")
                    if text:
                        all_chunks.append({"text": text, "page": page, "chapter": ch})
            except Exception:
                continue

        if not all_chunks:
            _update_batch_status(job_id, "completed", progress=100, completed_steps=4, total_steps=4)
            logger.info(f"⚠️ [BG] No chunks found for {filename}, skipping pre-generation")
            return

        # Get unique chapters
        chapters = list(set(c.get("chapter", "") for c in all_chunks if c.get("chapter")))
        if not chapters:
            chapters = [""]  # Single unnamed chapter

        # Extract topics for each chapter
        all_topics = []
        CHAR_BUDGET = 15000
        for chapter in chapters:
            chapter_chunks = [c for c in all_chunks if c.get("chapter") == chapter] if chapter else all_chunks
            content_parts = []
            total_chars = 0
            for c in chapter_chunks:
                part = f"[Page {c['page']}]\n{c['text']}"
                if total_chars + len(part) > CHAR_BUDGET:
                    break
                content_parts.append(part)
                total_chars += len(part)

            if content_parts:
                combined = "\n\n---\n\n".join(content_parts)
                try:
                    topics = await loop.run_in_executor(None, lambda: extract_topics(combined, "en", [filename]))
                    all_topics.extend(topics)
                except Exception as e:
                    logger.warning(f"[BG] Topic extraction failed for chapter '{chapter}': {e}")

        _update_batch_status(job_id, "generating_lessons", progress=50, completed_steps=2,
                             total_steps=4)
        logger.info(f"✅ [BG] Step 2 done: {len(all_topics)} topics extracted")

        if not all_topics:
            _update_batch_status(job_id, "completed", progress=100, completed_steps=4, total_steps=4)
            return

        # ── Step 3: Pre-generate lessons (conversation) for each topic ──
        from edtech_service import generate_teacher_dialogue
        from heygen_service import generate_dialogue_audio, TTS_AUDIO_DIR
        from embedder import embed_User_query
        from vectorstore import search_user_documents

        generated = 0
        for topic_name in all_topics[:20]:  # Cap at 20 topics to avoid overloading
            try:
                cache_key = _lesson_cache_key(user_id, "", topic_name, "en", "conversation")
                if _get_cached_lesson(cache_key):
                    generated += 1
                    continue  # Already cached

                # Search chunks
                query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic_name))
                results = await loop.run_in_executor(None, lambda: search_user_documents(query_vec, user_id, top_k=10))
                if not results:
                    continue

                chunks_refs = []
                for r in results:
                    text = r.get("text", "")
                    dn = r.get("doc_name", "Unknown")
                    pg = r.get("page", "")
                    if text:
                        chunks_refs.append(f"[From: {dn}, Page: {pg}]\n{text}")

                if not chunks_refs:
                    continue

                combined = "\n\n---\n\n".join(chunks_refs)
                lesson = await loop.run_in_executor(None, lambda: generate_teacher_dialogue(topic_name, combined, "en"))

                # Generate TTS audio for dialogue
                audio_urls = []
                audio_storage_paths = []
                voice_map = lesson.get("voice_map", {})
                dialogue = lesson.get("dialogue", [])
                if dialogue and voice_map:
                    try:
                        audio_files = await loop.run_in_executor(None, lambda: generate_dialogue_audio(
                            dialogue_lines=dialogue, voice_map=voice_map,
                            topic=topic_name, user_id=user_id, doc_name=filename
                        ))
                        for f_name in audio_files:
                            if f_name:
                                local_file = TTS_AUDIO_DIR / f_name
                                storage_path = f"dialogue/{user_id}/{f_name}"
                                public_url = _upload_audio_to_storage(str(local_file), storage_path)
                                if public_url:
                                    audio_urls.append(public_url)
                                    audio_storage_paths.append(storage_path)
                                else:
                                    audio_urls.append(f"/static/tts_audio/{f_name}")
                                    audio_storage_paths.append("")
                            else:
                                audio_urls.append("")
                                audio_storage_paths.append("")
                    except Exception as ae:
                        logger.warning(f"[BG] Audio gen failed for '{topic_name}': {ae}")

                lesson["audio_urls"] = audio_urls

                _save_lesson_cache(
                    user_id=user_id, cache_key=cache_key, topic=topic_name,
                    doc_name=filename, language="en", lesson_type="conversation",
                    lesson_json=lesson, audio_storage_paths=audio_storage_paths
                )
                generated += 1
                pct = 50 + int((generated / min(len(all_topics), 20)) * 25)
                _update_batch_status(job_id, "generating_lessons", progress=pct, completed_steps=2)
                logger.info(f"📝 [BG] Lesson {generated}/{len(all_topics)}: {topic_name}")

                # Tiny sleep to avoid rate-limiting OpenAI
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"[BG] Lesson pre-gen failed for '{topic_name}': {e}")

        _update_batch_status(job_id, "generating_videos", progress=80, completed_steps=3)
        logger.info(f"✅ [BG] Step 3 done: {generated} lessons pre-generated")

        # ── Step 4: Pre-generate TTS videos for first N topics ──
        from heygen_service import generate_tts_video_for_topic
        video_count = 0
        for topic_name in all_topics[:10]:  # Cap at 10 videos
            try:
                cache_key = _lesson_cache_key(user_id, filename, topic_name, "en", "tts_video")
                if _get_cached_lesson(cache_key):
                    video_count += 1
                    continue

                query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic_name))
                results = await loop.run_in_executor(None, lambda: search_user_documents(query_vec, user_id, top_k=10))
                if not results:
                    continue

                chunks_refs = []
                for r in results:
                    text = r.get("text", "")
                    src = r.get("doc_name", "Unknown")
                    pg = r.get("page", "")
                    if text:
                        chunks_refs.append(f"[From: {src}, Page: {pg}]\n{text}")

                if not chunks_refs:
                    continue

                combined = "\n\n---\n\n".join(chunks_refs)
                result = await loop.run_in_executor(None, lambda: generate_tts_video_for_topic(
                    topic=topic_name, content=combined, user_id=user_id,
                    doc_name=filename, language="en", voice="nova"
                ))

                if result.get("status") == "completed" and result.get("audio_filename"):
                    local_file = TTS_AUDIO_DIR / result["audio_filename"]
                    storage_path = f"tts_video/{user_id}/{result['audio_filename']}"
                    public_url = _upload_audio_to_storage(str(local_file), storage_path)
                    if public_url:
                        result["audio_url"] = public_url
                    response_data = {"success": True, **result}
                    _save_lesson_cache(
                        user_id=user_id, cache_key=cache_key, topic=topic_name,
                        doc_name=filename, language="en", lesson_type="tts_video",
                        lesson_json=response_data, audio_storage_paths=[storage_path]
                    )
                    video_count += 1
                    pct = 80 + int((video_count / min(len(all_topics), 10)) * 20)
                    _update_batch_status(job_id, "generating_videos", progress=pct, completed_steps=3)
                    logger.info(f"🎬 [BG] Video {video_count}: {topic_name}")

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"[BG] TTS video pre-gen failed for '{topic_name}': {e}")

        _update_batch_status(job_id, "completed", progress=100, completed_steps=4, total_steps=4)
        logger.info(f"🎉 [BG] Background processing complete: {filename} "
                     f"({generated} lessons, {video_count} videos)")

    except Exception as e:
        logger.error(f"❌ [BG] Background processing failed for {filename}: {e}")
        _update_batch_status(job_id, "failed", error=str(e))


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
        
        # 5. Create batch job and fire background processing
        batch_job_id = None
        try:
            job_result = supabase.table("batch_jobs").insert({
                "user_id": current_user.id,
                "doc_name": file.filename,
                "status": "queued",
                "progress": 0,
                "total_steps": 4,
                "completed_steps": 0
            }).execute()
            if job_result.data:
                batch_job_id = job_result.data[0]["id"]
                logger.info(f"📋 Batch job created: {batch_job_id}")
        except Exception as e:
            logger.warning(f"Batch job creation failed (non-fatal): {e}")

        # Fire background processing (non-blocking)
        if batch_job_id:
            asyncio.create_task(
                _background_process_and_pregenerate(
                    user_id=current_user.id,
                    filename=file.filename,
                    access_token=current_user.access_token,
                    job_id=batch_job_id
                )
            )
            logger.info(f"🚀 Background processing fired for {file.filename}")

        return {
            "success": True,
            "file_name": file.filename,
            "filename": file.filename,
            "file_size": file_size,
            "file_type": file.content_type,
            "batch_job_id": batch_job_id,
            "message": f"File {file.filename} uploaded! Processing in background."
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/register-file")
async def register_file_endpoint(request: RegisterFileRequest, current_user: User = Depends(get_current_user)):
    """Register a file uploaded to Supabase Storage and auto-queue processing"""
    try:
        logger.info(f"📝 Registering file: {request.filename} ({request.blob_url})")
        
        # 1. Save to Supabase (Primary)
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

        # 2. Update local metadata
        existing_files = _read_local_file_metadata()
        existing_files = [f for f in existing_files if f.get('filename') != request.filename]
        existing_files.append({
            "filename": request.filename,
            "file_name": request.filename,
            "file_type": request.file_type,
            "file_size": request.file_size,
            "chunks_created": 0,
            "processed": False,
            "status": "queued",
            "uploaded_at": datetime.utcnow().isoformat(),
            "blob_url": request.blob_url
        })
        _save_local_file_metadata(existing_files)
        
        # 3. Auto-queue processing (NEW: no more manual "Process" click needed)
        batch_job_id = str(uuid.uuid4())
        try:
            supabase.table("batch_jobs").insert({
                "id": batch_job_id,
                "user_id": current_user.id,
                "doc_name": request.filename,
                "status": "queued",
                "progress": 0,
                "total_steps": 4,
                "completed_steps": 0
            }).execute()
        except Exception as e:
            logger.warning(f"Batch job creation failed: {e}")
        
        _enqueue_processing(current_user.id, request.filename, current_user.access_token, batch_job_id)
        
        return {
            "success": True, 
            "message": "File registered and queued for processing",
            "batch_job_id": batch_job_id,
            "status": "queued"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-file")
async def process_file_endpoint(filename: str, current_user: User = Depends(get_current_user)):
    """Queue a file for processing (non-blocking). Returns batch_job_id for polling."""
    try:
        logger.info(f"⚙️ Queuing file for processing: {filename} for user {current_user.id}")
        
        # Create batch job
        batch_job_id = str(uuid.uuid4())
        try:
            supabase.table("batch_jobs").insert({
                "id": batch_job_id,
                "user_id": current_user.id,
                "doc_name": filename,
                "status": "queued",
                "progress": 0,
                "total_steps": 4,
                "completed_steps": 0
            }).execute()
        except Exception as e:
            logger.warning(f"Batch job creation failed: {e}")
        
        # Enqueue for background processing (returns immediately)
        _enqueue_processing(current_user.id, filename, current_user.access_token, batch_job_id)
        
        return {
            "success": True, 
            "queued": True,
            "batch_job_id": batch_job_id,
            "message": f"File {filename} queued for processing"
        }
    except Exception as e:
        logger.error(f"Error queuing file {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch-status")
async def batch_status_endpoint(
    doc_name: str = "",
    job_id: str = "",
    current_user: User = Depends(get_current_user)
):
    """Get background processing job status."""
    try:
        if job_id:
            result = supabase.table("batch_jobs").select("*").eq("id", job_id).eq("user_id", current_user.id).execute()
        elif doc_name:
            result = supabase.table("batch_jobs").select("*").eq("doc_name", doc_name).eq("user_id", current_user.id).order("created_at", desc=True).limit(1).execute()
        else:
            # Return all recent jobs for user
            result = supabase.table("batch_jobs").select("*").eq("user_id", current_user.id).order("created_at", desc=True).limit(10).execute()

        jobs = result.data if result.data else []

        # Map status to user-friendly message
        status_labels = {
            "queued": "Waiting to start...",
            "processing": "📄 Chunking & embedding document...",
            "extracting_topics": "🔍 Extracting chapters & topics...",
            "generating_lessons": "📝 Pre-generating AI lessons...",
            "generating_videos": "🎬 Pre-generating teaching videos...",
            "completed": "✅ Ready! All lessons & videos pre-built.",
            "failed": "❌ Processing failed."
        }

        for job in jobs:
            job["status_label"] = status_labels.get(job.get("status", ""), job.get("status", ""))

        return {"success": True, "jobs": jobs}
    except Exception as e:
        logger.error(f"Batch status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

# In-memory caches for chapters/topics (results don't change once doc is processed)
_chapters_cache: dict = {}   # key: "user_id:doc_name" → {"data": response, "ts": time}
_topics_cache: dict = {}     # key: "user_id:doc_name:chapter:language" → {"data": response, "ts": time}
_EDTECH_CACHE_TTL = 1800     # 30 minutes (chapters/topics don't change)

@app.get("/api/edtech/chapters")
async def edtech_get_chapters(
    doc_name: str,
    current_user: User = Depends(get_current_user)
):
    """Get all chapters/sections detected in a processed document."""
    import time as _time
    cache_key = f"{current_user.id}:{doc_name}"
    cached = _chapters_cache.get(cache_key)
    if cached and (_time.time() - cached["ts"]) < _EDTECH_CACHE_TTL:
        logger.info(f"🎯 Chapters cache HIT: {doc_name}")
        return cached["data"]
    try:
        from vectorstore import index, get_user_namespaces
        from collections import defaultdict
        import re as _re

        namespaces = get_user_namespaces(current_user.id)
        all_chunks = []
        loop = asyncio.get_event_loop()

        for ns in namespaces:
            try:
                dummy_vec = [0.0] * 1536
                res = await loop.run_in_executor(None, lambda _ns=ns: index.query(
                    vector=dummy_vec,
                    top_k=10000,
                    include_metadata=True,
                    namespace=_ns,
                    filter={"doc_name": {"$eq": doc_name}}
                ))
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

        response = {
            "success": True,
            "chapters": chapters,
            "document": doc_name,
            "total_chunks": len(all_chunks)
        }
        # Cache the result
        _chapters_cache[cache_key] = {"data": response, "ts": _time.time()}
        return response

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
    import time as _time
    topic_cache_key = f"{current_user.id}:{doc_name}:{chapter}:{language}"
    cached = _topics_cache.get(topic_cache_key)
    if cached and (_time.time() - cached["ts"]) < _EDTECH_CACHE_TTL:
        logger.info(f"🎯 Topics cache HIT: {doc_name} / {chapter or 'whole doc'}")
        return cached["data"]
    try:
        from edtech_service import extract_topics
        from vectorstore import index, get_user_namespaces
        import re as _re

        namespaces = get_user_namespaces(current_user.id)
        all_chunks = []
        loop = asyncio.get_event_loop()

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
                res = await loop.run_in_executor(None, lambda _ns=ns: index.query(
                    vector=dummy_vec,
                    top_k=10000,
                    include_metadata=True,
                    namespace=_ns,
                    filter=pinecone_filter
                ))
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

        topics = await loop.run_in_executor(None, lambda: extract_topics(combined, language, [doc_name]))

        response = {
            "success": True,
            "topics": topics,
            "document": doc_name,
            "chapter": chapter,
            "chunks_used": len(content_parts),
            "total_chunks": len(all_chunks)
        }
        # Cache the result
        _topics_cache[topic_cache_key] = {"data": response, "ts": _time.time()}
        return response

    except Exception as e:
        logger.error(f"EdTech topic extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ══════════════════════════════════════════════════════════════════════
# ▸ Lesson Cache Helpers (Supabase DB + Storage + In-Memory LRU)
# ══════════════════════════════════════════════════════════════════════

# In-memory cache: {cache_key: {"data": ..., "ts": time.time()}}
_lesson_mem_cache: dict = {}
_LESSON_CACHE_TTL = 300  # 5 minutes

def _lesson_cache_key(user_id: str, doc_name: str, topic: str, language: str, lesson_type: str) -> str:
    """Generate a deterministic cache key."""
    import hashlib
    raw = f"{user_id}:{doc_name}:{topic}:{language}:{lesson_type}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached_lesson(cache_key: str):
    """Check in-memory cache first, then Supabase. Returns dict or None."""
    import time as _time
    # 1. Check in-memory cache
    mem = _lesson_mem_cache.get(cache_key)
    if mem and (_time.time() - mem["ts"]) < _LESSON_CACHE_TTL:
        return mem["data"]
    # 2. Fallback to Supabase
    try:
        result = supabase.table("lesson_cache").select("*").eq("cache_key", cache_key).limit(1).execute()
        if result.data and len(result.data) > 0:
            # Populate in-memory cache
            _lesson_mem_cache[cache_key] = {"data": result.data[0], "ts": _time.time()}
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
        # Update in-memory cache too
        import time as _time
        _lesson_mem_cache[cache_key] = {
            "data": {"cache_key": cache_key, "lesson_json": lesson_json,
                     "audio_storage_paths": audio_storage_paths or []},
            "ts": _time.time()
        }
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
        loop = asyncio.get_event_loop()

        # Search for relevant chunks about this topic
        query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))
        results = await loop.run_in_executor(None, lambda: search_user_documents(query_vec, current_user.id, top_k=10))

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
        lesson = await loop.run_in_executor(None, lambda: generate_teacher_dialogue(topic, combined, language))

        # ── 3. Generate TTS audio for each dialogue line ──
        audio_urls = []
        audio_storage_paths = []
        voice_map = lesson.get("voice_map", {})
        dialogue = lesson.get("dialogue", [])
        if dialogue and voice_map:
            try:
                from heygen_service import generate_dialogue_audio, TTS_AUDIO_DIR
                audio_files = await loop.run_in_executor(None, lambda: generate_dialogue_audio(
                    dialogue_lines=dialogue,
                    voice_map=voice_map,
                    topic=topic,
                    user_id=current_user.id,
                    doc_name=doc_name
                ))
                # Upload all audio files to Supabase Storage in parallel
                async def _upload_one(f_name):
                    if not f_name:
                        return "", ""
                    local_file = TTS_AUDIO_DIR / f_name
                    storage_path = f"dialogue/{current_user.id}/{f_name}"
                    public_url = await loop.run_in_executor(
                        None, lambda lf=str(local_file), sp=storage_path: _upload_audio_to_storage(lf, sp)
                    )
                    if public_url:
                        return public_url, storage_path
                    else:
                        return f"/static/tts_audio/{f_name}", ""

                upload_results = await asyncio.gather(
                    *[_upload_one(f) for f in audio_files]
                )
                audio_urls = [r[0] for r in upload_results]
                audio_storage_paths = [r[1] for r in upload_results]
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


@app.post("/api/edtech/ask-doubt")
async def edtech_ask_doubt(
    question: str = Form(...),
    topic: str = Form(""),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """Answer a mid-lesson doubt using direct LLM (general knowledge + topic context)."""
    try:
        from openai import OpenAI
        client = OpenAI()
        loop = asyncio.get_event_loop()

        lang_instruction = ""
        if language == "ta":
            lang_instruction = "\nIMPORTANT: Answer in Tamil (தமிழ்). Use simple, conversational Tamil."

        system_msg = (
            "You are a helpful, friendly teacher answering a student's doubt during a lesson. "
            "Use your general knowledge to give a clear, concise answer. "
            "Keep your answer focused and under 150 words unless a longer explanation is truly needed. "
            "Do NOT mention anything about documents, sources, or whether the information comes from uploaded files."
            f"{lang_instruction}"
        )

        user_msg = f"Topic being studied: {topic}\n\nStudent's question: {question}" if topic else question

        def _ask():
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return resp.choices[0].message.content.strip()

        answer = await loop.run_in_executor(None, _ask)
        return {"success": True, "answer": answer}

    except Exception as e:
        logger.error(f"Doubt Q&A failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/edtech/speak-answer")
async def edtech_speak_answer(
    text: str = Form(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_user)
):
    """Convert an LLM answer to TTS audio and return the public URL."""
    try:
        import hashlib
        from openai import OpenAI
        from heygen_service import TTS_AUDIO_DIR
        client = OpenAI()

        loop = asyncio.get_event_loop()

        # Generate a short hash for caching
        text_hash = hashlib.md5(f"{current_user.id}:{text[:200]}".encode()).hexdigest()[:12]
        audio_filename = f"answer_{text_hash}.mp3"
        audio_path = TTS_AUDIO_DIR / audio_filename
        storage_path = f"answers/{current_user.id}/{audio_filename}"

        # Check local cache first
        if not audio_path.exists():
            # Truncate very long answers to keep TTS reasonable
            tts_text = text[:1500] if len(text) > 1500 else text
            voice = "shimmer" if language == "ta" else "nova"

            def _generate():
                resp = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=tts_text,
                    response_format="mp3"
                )
                resp.stream_to_file(str(audio_path))

            await loop.run_in_executor(None, _generate)

        # Upload to Supabase Storage
        public_url = await loop.run_in_executor(
            None, lambda: _upload_audio_to_storage(str(audio_path), storage_path)
        )

        if not public_url:
            # Fallback to local static path
            public_url = f"/static/tts_audio/{audio_filename}"

        return {"success": True, "audio_url": public_url}

    except Exception as e:
        logger.error(f"Speak-answer TTS failed: {e}")
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
        loop = asyncio.get_event_loop()

        # Search for relevant chunks
        query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))
        results = await loop.run_in_executor(None, lambda: search_user_documents(query_vec, current_user.id, top_k=10))

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

        result = await loop.run_in_executor(None, lambda: generate_tts_video_for_topic(
            topic=topic,
            content=combined_content,
            user_id=current_user.id,
            doc_name=doc_name,
            language=language,
            voice=voice
        ))

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

# ══════════════════════════════════════════════════════════════════════
# ▸ CLASSROOM / LMS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

import string, random as _random

def _generate_join_code(length: int = 6) -> str:
    """Generate a random alphanumeric join code."""
    return ''.join(_random.choices(string.ascii_uppercase + string.digits, k=length))


# ── Role Management ──

@app.patch("/api/users/role")
async def update_user_role(
    role: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Switch user role to 'teacher' or 'student'."""
    if role not in ("teacher", "student"):
        raise HTTPException(status_code=400, detail="Role must be 'teacher' or 'student'")
    try:
        supabase.table("profiles").update({"role": role}).eq("id", current_user.id).execute()
        return {"success": True, "role": role}
    except Exception as e:
        logger.error(f"Role update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info including role."""
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role
        }
    }


# ── Classroom CRUD ──

@app.post("/api/classrooms")
async def create_classroom(
    name: str = Form(...),
    description: str = Form(""),
    doc_name: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    """Create a new classroom (teacher only)."""
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create classrooms")
    try:
        join_code = _generate_join_code()
        # Ensure unique join code
        for _ in range(5):
            existing = supabase.table("classrooms").select("id").eq("join_code", join_code).execute()
            if not existing.data:
                break
            join_code = _generate_join_code()

        result = supabase.table("classrooms").insert({
            "teacher_id": current_user.id,
            "name": name,
            "description": description,
            "doc_name": doc_name,
            "join_code": join_code
        }).execute()

        return {"success": True, "classroom": result.data[0] if result.data else None}
    except Exception as e:
        logger.error(f"Classroom creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/classrooms")
async def list_classrooms(current_user: User = Depends(get_current_user)):
    """List classrooms — teacher sees owned, student sees joined."""
    try:
        if current_user.role == "teacher":
            result = supabase.table("classrooms").select("*").eq("teacher_id", current_user.id).order("created_at", desc=True).execute()
            classrooms = result.data or []
            # Attach student count
            for cls in classrooms:
                count = supabase.table("classroom_students").select("id", count="exact").eq("classroom_id", cls["id"]).execute()
                cls["student_count"] = count.count if count.count is not None else 0
        else:
            # Student: get classrooms they've joined
            memberships = supabase.table("classroom_students").select("classroom_id").eq("student_id", current_user.id).execute()
            classroom_ids = [m["classroom_id"] for m in (memberships.data or [])]
            if classroom_ids:
                result = supabase.table("classrooms").select("*").in_("id", classroom_ids).execute()
                classrooms = result.data or []
            else:
                classrooms = []
            # Attach teacher name
            for cls in classrooms:
                teacher = supabase.table("profiles").select("full_name").eq("id", cls["teacher_id"]).limit(1).execute()
                cls["teacher_name"] = teacher.data[0]["full_name"] if teacher.data else "Teacher"

        return {"success": True, "classrooms": classrooms}
    except Exception as e:
        logger.error(f"List classrooms failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/classrooms/join")
async def join_classroom(
    join_code: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Student joins a classroom via join code."""
    try:
        # Find classroom
        result = supabase.table("classrooms").select("*").eq("join_code", join_code.upper().strip()).limit(1).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Invalid join code")
        classroom = result.data[0]

        # Check not already joined
        existing = supabase.table("classroom_students").select("id").eq("classroom_id", classroom["id"]).eq("student_id", current_user.id).execute()
        if existing.data:
            return {"success": True, "message": "Already joined", "classroom": classroom}

        # Add membership
        supabase.table("classroom_students").insert({
            "classroom_id": classroom["id"],
            "student_id": current_user.id
        }).execute()

        return {"success": True, "message": "Joined successfully!", "classroom": classroom}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Join classroom failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/classrooms/{classroom_id}")
async def get_classroom_detail(classroom_id: str, current_user: User = Depends(get_current_user)):
    """Get full classroom details including students and assignments."""
    try:
        # Get classroom
        cls_result = supabase.table("classrooms").select("*").eq("id", classroom_id).limit(1).execute()
        if not cls_result.data:
            raise HTTPException(status_code=404, detail="Classroom not found")
        classroom = cls_result.data[0]

        # Get students
        students_result = supabase.table("classroom_students").select("student_id, joined_at").eq("classroom_id", classroom_id).execute()
        students = []
        for s in (students_result.data or []):
            profile = supabase.table("profiles").select("id, full_name, email").eq("id", s["student_id"]).limit(1).execute()
            if profile.data:
                student_info = profile.data[0]
                student_info["joined_at"] = s["joined_at"]
                students.append(student_info)

        # Get assignments
        assignments_result = supabase.table("assignments").select("*").eq("classroom_id", classroom_id).order("created_at", desc=True).execute()

        classroom["students"] = students
        classroom["assignments"] = assignments_result.data or []

        return {"success": True, "classroom": classroom}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classroom detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Assignments ──

@app.post("/api/classrooms/{classroom_id}/assignments")
async def create_assignment(
    classroom_id: str,
    chapter_title: str = Form(...),
    topics: str = Form("[]"),  # JSON array string
    due_date: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    """Teacher creates an assignment (chapter + topics + optional due date)."""
    if current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can create assignments")
    try:
        import json as _json
        topics_list = _json.loads(topics) if topics else []
        assignment_data = {
            "classroom_id": classroom_id,
            "chapter_title": chapter_title,
            "topics": topics_list,
        }
        if due_date:
            assignment_data["due_date"] = due_date

        result = supabase.table("assignments").insert(assignment_data).execute()
        return {"success": True, "assignment": result.data[0] if result.data else None}
    except Exception as e:
        logger.error(f"Assignment creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Progress Tracking ──

@app.post("/api/progress/update")
async def update_student_progress(
    classroom_id: str = Form(...),
    topic: str = Form(...),
    activity_type: str = Form(...),  # 'conversation', 'video', or 'quiz'
    quiz_score: int = Form(0),
    quiz_answers: str = Form("{}"),  # JSON string
    current_user: User = Depends(get_current_user)
):
    """Record a student's activity completion for a topic."""
    try:
        import json as _json

        # Upsert progress
        existing = supabase.table("student_progress").select("*").eq("student_id", current_user.id).eq("classroom_id", classroom_id).eq("topic", topic).limit(1).execute()

        update_data = {"updated_at": datetime.utcnow().isoformat()}

        if activity_type == "conversation":
            update_data["conversation_completed"] = True
        elif activity_type == "video":
            update_data["video_completed"] = True
        elif activity_type == "quiz":
            update_data["quiz_score"] = quiz_score
            update_data["quiz_answers"] = _json.loads(quiz_answers) if quiz_answers else {}

        if existing.data:
            # Update existing
            progress = existing.data[0]
            supabase.table("student_progress").update(update_data).eq("id", progress["id"]).execute()
            # Check if fully completed
            merged = {**progress, **update_data}
            if merged.get("conversation_completed") and merged.get("video_completed") and merged.get("quiz_score", 0) > 0:
                supabase.table("student_progress").update({"completed_at": datetime.utcnow().isoformat()}).eq("id", progress["id"]).execute()
        else:
            # Insert new
            insert_data = {
                "student_id": current_user.id,
                "classroom_id": classroom_id,
                "topic": topic,
                **update_data
            }
            # Try to find the assignment this topic belongs to
            assignments = supabase.table("assignments").select("id, topics").eq("classroom_id", classroom_id).execute()
            for a in (assignments.data or []):
                if topic in (a.get("topics") or []):
                    insert_data["assignment_id"] = a["id"]
                    break
            supabase.table("student_progress").insert(insert_data).execute()

        return {"success": True, "message": "Progress updated"}
    except Exception as e:
        logger.error(f"Progress update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress/me")
async def get_my_progress(
    classroom_id: str = "",
    current_user: User = Depends(get_current_user)
):
    """Get own progress — optionally filtered by classroom."""
    try:
        query = supabase.table("student_progress").select("*").eq("student_id", current_user.id)
        if classroom_id:
            query = query.eq("classroom_id", classroom_id)
        result = query.execute()
        return {"success": True, "progress": result.data or []}
    except Exception as e:
        logger.error(f"Get progress failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/classrooms/{classroom_id}/progress")
async def get_classroom_progress(
    classroom_id: str,
    current_user: User = Depends(get_current_user)
):
    """Teacher gets all students' progress for a classroom."""
    try:
        # Get all students in classroom
        students_result = supabase.table("classroom_students").select("student_id").eq("classroom_id", classroom_id).execute()
        student_ids = [s["student_id"] for s in (students_result.data or [])]

        if not student_ids:
            return {"success": True, "progress": [], "students": []}

        # Get all progress records for this classroom
        progress_result = supabase.table("student_progress").select("*").eq("classroom_id", classroom_id).execute()

        # Get student names
        students = []
        for sid in student_ids:
            profile = supabase.table("profiles").select("id, full_name, email").eq("id", sid).limit(1).execute()
            if profile.data:
                students.append(profile.data[0])

        # Get assignments for topic list
        assignments = supabase.table("assignments").select("*").eq("classroom_id", classroom_id).execute()

        # Calculate per-student summary
        student_summaries = []
        for student in students:
            student_progress = [p for p in (progress_result.data or []) if p["student_id"] == student["id"]]
            total_topics = sum(len(a.get("topics") or []) for a in (assignments.data or []))
            completed_topics = sum(1 for p in student_progress if p.get("completed_at"))
            pct = round((completed_topics / total_topics * 100)) if total_topics > 0 else 0
            student_summaries.append({
                **student,
                "completed_topics": completed_topics,
                "total_topics": total_topics,
                "progress_percent": pct,
                "details": student_progress
            })

        return {
            "success": True,
            "students": student_summaries,
            "assignments": assignments.data or [],
            "progress": progress_result.data or []
        }
    except Exception as e:
        logger.error(f"Classroom progress failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
