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
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

# Load .env file FIRST so all os.getenv() calls across modules get the values
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

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
import string
import random

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


def _generate_join_code(length: int = 6) -> str:
    """Generate a random uppercase alphanumeric join code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

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
    
    # Start auto-batch video pre-generation scheduler
    global _auto_batch_task
    _auto_batch_task = asyncio.create_task(_auto_batch_video_scheduler())
    logger.info("🎬 Auto-batch video scheduler registered (starts in 60s)")
    
    yield
    
    # Shutdown: stop workers gracefully
    logger.info("Shutting down workers...")
    # Cancel auto-batch scheduler
    if _auto_batch_task:
        _auto_batch_task.cancel()
    from avatar_video_service import cancel_batch_worker
    cancel_batch_worker()
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
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "https://ragsysetm-backendpart.onrender.com",
    "https://zenzeebot.netlify.app",
    "https://zenzeebot1.netlify.app",
    "https://ragsystem-1f65p6bm4-com4globals-projects.vercel.app",
    "https://ragsystem-api1.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*(-zenzeebot|zenzeebot1?)\.netlify\.app",
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

# Mount static files for local video fallback
if os.name == "nt":
    _videos_dir = _pathlib.Path(__file__).parent / "static" / "videos"
else:
    _videos_dir = _pathlib.Path("/tmp") / "videos"
_videos_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/videos", StaticFiles(directory=str(_videos_dir)), name="videos")

# Mount static files for avatar video generation temp files
if os.name == "nt":
    _avatar_video_dir = _pathlib.Path(__file__).parent / "static" / "avatar_video_temp"
else:
    _avatar_video_dir = _pathlib.Path("/tmp") / "avatar_video_temp"
_avatar_video_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/avatar_video_temp", StaticFiles(directory=str(_avatar_video_dir)), name="avatar_video_temp")

# Mount static files for avatar images (thumbnails)
if os.name == "nt":
    _avatars_dir = _pathlib.Path(__file__).parent / "static" / "avatars"
else:
    _avatars_dir = _pathlib.Path("/tmp") / "avatars"
_avatars_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static/avatars", StaticFiles(directory=str(_avatars_dir)), name="avatars")

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
                    # ── FIX 1: Persist chapter topics to lesson_cache so the topics endpoint
                    #           never needs to re-call the LLM (instant retrieval) ──
                    if topics:
                        topics_cache_key = _lesson_cache_key(user_id, filename, chapter or "__all__", "en", "topics")
                        _save_lesson_cache(
                            user_id=user_id, cache_key=topics_cache_key,
                            topic=chapter or "__all__", doc_name=filename,
                            language="en", lesson_type="topics",
                            lesson_json={"topics": topics, "chapter": chapter},
                            audio_storage_paths=[]
                        )
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

        # all_topics is a list of dicts: [{"title": ..., "description": ..., ...}]
        # Extract plain string titles for embed / generate calls
        all_topic_titles = []
        for t in all_topics:
            if isinstance(t, dict):
                title = t.get("title") or t.get("name") or ""
            else:
                title = str(t)
            if title.strip():
                all_topic_titles.append(title.strip())

        logger.info(f"📋 [BG] {len(all_topic_titles)} unique topic titles to pre-generate: {all_topic_titles[:5]}...")

        generated = 0
        for topic_name in all_topic_titles[:20]:  # Cap at 20 topics to avoid overloading
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
                pct = 50 + int((generated / min(len(all_topic_titles), 20)) * 25)
                _update_batch_status(job_id, "generating_lessons", progress=pct, completed_steps=2)
                logger.info(f"📝 [BG] Lesson {generated}/{len(all_topic_titles)}: {topic_name}")

                # Tiny sleep to avoid rate-limiting OpenAI
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f"[BG] Lesson pre-gen failed for '{topic_name}': {e}")

        _update_batch_status(job_id, "generating_videos", progress=80, completed_steps=3)
        logger.info(f"✅ [BG] Step 3 done: {generated} lessons pre-generated")

        # ── Step 4: Pre-generate TTS videos for ALL topics (up to 20) ──
        from heygen_service import generate_tts_video_for_topic
        video_count = 0
        for topic_name in all_topic_titles[:20]:  # Match lesson cap
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
                    pct = 80 + int((video_count / min(len(all_topic_titles), 20)) * 20)
                    _update_batch_status(job_id, "generating_videos", progress=pct, completed_steps=3)
                    logger.info(f"🎬 [BG] Video {video_count}/{len(all_topic_titles)}: {topic_name}")

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
        from billing_service import (
            get_user_subscription as _get_sub,
            check_file_type_allowed,
            check_file_size,
            check_total_storage,
        )
        logger.info(f"📤 Upload started: {file.filename} by user {current_user.id}")

        # ── Plan-based upload enforcement ─────────────────────────────────
        sub_info = _get_sub(current_user.id)
        plan_name = sub_info.get("plan", "free")

        # 0a. File-type check
        type_ok, type_reason = check_file_type_allowed(plan_name, file.filename)
        if not type_ok:
            raise HTTPException(
                status_code=403,
                detail={"upgrade_required": True, "reason": type_reason, "current_plan": plan_name},
            )

        # 0b. Read the file content to get size
        content = await file.read()
        file_size = len(content)

        # 0c. Per-file size check
        size_ok, size_reason = check_file_size(plan_name, file_size)
        if not size_ok:
            raise HTTPException(
                status_code=403,
                detail={"upgrade_required": True, "reason": size_reason, "current_plan": plan_name},
            )

        # 0d. Total storage check — sum existing file sizes for this user
        try:
            user_files_result = supabase.table("user_files") \
                .select("file_size") \
                .eq("user_id", current_user.id) \
                .execute()
            current_used = sum(r.get("file_size", 0) for r in (user_files_result.data or []))
        except Exception:
            current_used = 0  # If query fails, don't block upload

        storage_ok, storage_reason = check_total_storage(plan_name, current_used, file_size)
        if not storage_ok:
            raise HTTPException(
                status_code=403,
                detail={"upgrade_required": True, "reason": storage_reason, "current_plan": plan_name},
            )

        logger.info(f"✅ Plan checks passed ({plan_name}): {file.filename} ({file_size} bytes)")
        # ── End enforcement ───────────────────────────────────────────────
        
        # 1. Save file to local storage (resources directory root)
        # Always write to writable directory
        local_path = WRITE_RESOURCES_DIR / file.filename
        
        with open(local_path, "wb") as buffer:
            buffer.write(content)
        
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


# ── PDF Page Extraction ──

class ExtractPagesRequest(BaseModel):
    start_page: int = 1       # 1-indexed
    end_page: int = -1        # -1 = last page
    info_only: bool = False   # True = just return page count

@app.post("/api/extract-pages")
async def extract_pages(
    file: UploadFile = File(...),
    start_page: int = Form(1),
    end_page: int = Form(-1),
    info_only: str = Form("false"),
    current_user: User = Depends(get_current_user),
):
    """
    Extract a page range from a PDF and return the result.
    If info_only=true, returns only total page count.
    Pages are 1-indexed.
    """
    import io
    from pypdf import PdfReader, PdfWriter

    is_info_only = info_only.lower() in ("true", "1", "yes")

    try:
        content = await file.read()
        pdf_stream = io.BytesIO(content)
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)

        # Info-only mode: just return metadata
        if is_info_only:
            return {
                "success": True,
                "total_pages": total_pages,
                "filename": file.filename,
                "file_size": len(content),
            }

        # Validate range
        start = max(1, start_page)
        end = total_pages if end_page == -1 else min(end_page, total_pages)
        if start > end or start > total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid page range {start}-{end}. File has {total_pages} pages.",
            )

        # Extract pages
        writer = PdfWriter()
        for i in range(start - 1, end):  # convert to 0-indexed
            writer.add_page(reader.pages[i])

        out_buf = io.BytesIO()
        writer.write(out_buf)
        out_buf.seek(0)

        # Build output filename
        base = file.filename.rsplit(".", 1)[0] if "." in file.filename else file.filename
        out_name = f"{base}_pages_{start}-{end}.pdf"

        logger.info(
            f"✂️ Extracted pages {start}-{end} ({end - start + 1} pages) "
            f"from {file.filename} ({total_pages} total) for user {current_user.id}"
        )

        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            out_buf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{out_name}"',
                "X-Total-Pages": str(total_pages),
                "X-Extracted-Pages": f"{start}-{end}",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Page extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Page extraction failed: {e}")


# ── Web URL Ingestion ──

@app.post("/api/ingest-url")
async def ingest_url(
    url: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Extract text from a web page URL and process it through the embedding pipeline."""
    try:
        logger.info(f"🌐 Ingesting URL: {url} for user {current_user.id}")

        # Fetch the web page
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EdTechBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Extract readable text with BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script, style, nav, footer elements
        for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
            tag.decompose()

        # Get page title
        title = soup.title.string.strip() if soup.title and soup.title.string else "Web Page"

        # Extract main text content
        text_parts = []
        for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote", "pre", "article"]):
            text = element.get_text(strip=True)
            if len(text) > 20:  # Skip very short fragments
                text_parts.append(text)

        full_text = f"# {title}\n\nSource: {url}\n\n" + "\n\n".join(text_parts)

        if len(full_text) < 100:
            raise HTTPException(status_code=400, detail="Could not extract enough text from this URL")

        # Save as a .txt file
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", title)[:50]
        filename = f"web_{safe_name}.txt"
        user_dir = WRITE_RESOURCES_DIR / current_user.id
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        file_size = len(full_text.encode("utf-8"))
        logger.info(f"📝 Extracted {len(text_parts)} sections, {file_size} bytes from {url}")

        # Register the file in the database
        try:
            user_db.add_user_file(
                user_id=current_user.id,
                filename=filename,
                file_type="txt",
                file_size=file_size,
                user_token=current_user.access_token
            )
        except Exception as e:
            logger.warning(f"File registration warning: {e}")

        # Queue background processing (chunking + embedding)
        job_id = str(uuid.uuid4())
        try:
            supabase.table("batch_jobs").insert({
                "id": job_id,
                "user_id": current_user.id,
                "doc_name": filename,
                "status": "queued",
                "progress": 0,
                "total_steps": 4,
                "completed_steps": 0
            }).execute()
        except Exception as e:
            logger.warning(f"Batch job creation warning: {e}")
        _enqueue_processing(current_user.id, filename, current_user.access_token, job_id)

        return {
            "success": True,
            "title": title,
            "filename": filename,
            "text_length": len(full_text),
            "sections": len(text_parts),
            "batch_job_id": job_id,
            "message": f"Web page '{title}' extracted! Processing in background."
        }
    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error(f"URL fetch failed: {e}")
        raise HTTPException(status_code=400, detail=f"Could not fetch URL: {str(e)}")
    except Exception as e:
        logger.error(f"URL ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── YouTube Video Processing ──

def _extract_video_id(url: str) -> str:
    """Extract the video ID from various YouTube URL formats."""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    if "youtube.com" in hostname:
        qs = parse_qs(parsed.query)
        if "v" in qs:
            return qs["v"][0]
        # Handle /embed/VIDEO_ID and /v/VIDEO_ID
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] in ("embed", "v"):
            return parts[1]
    elif "youtu.be" in hostname:
        return parsed.path.lstrip("/").split("/")[0]
    raise ValueError(f"Could not extract video ID from URL: {url}")


class YouTubeRequest(BaseModel):
    url: str


@app.post("/api/process-youtube")
async def process_youtube(
    request: YouTubeRequest,
    current_user: User = Depends(get_current_user)
):
    """Fetch YouTube video transcript via captions API, save as text, and process through RAG pipeline."""
    try:
        url = request.url.strip()
        logger.info(f"🎬 Processing YouTube URL: {url} for user {current_user.id}")

        # 1. Extract the video ID
        try:
            video_id = _extract_video_id(url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 2. Fetch transcript using youtube-transcript-api (new instance-based API)
        ytt_api = YouTubeTranscriptApi()
        transcript_segments = None
        try:
            transcript_segments = ytt_api.fetch(
                video_id,
                languages=["en", "en-US", "en-GB", "en-IN"]
            )
        except Exception as e:
            logger.warning(f"English transcript not found, trying any language: {e}")
            try:
                # Fallback: try to get any available transcript
                transcript_list = ytt_api.list(video_id)
                # Try auto-generated first, then manual
                for transcript in transcript_list:
                    try:
                        transcript_segments = transcript.fetch()
                        logger.info(f"Found transcript in language: {transcript.language}")
                        break
                    except Exception:
                        continue
            except Exception as e2:
                logger.error(f"No transcripts available for video {video_id}: {e2}")
                raise HTTPException(
                    status_code=400,
                    detail=f"No captions/transcript available for this video. "
                           f"The video may not have captions enabled."
                )

        if not transcript_segments:
            raise HTTPException(
                status_code=400,
                detail="Could not retrieve transcript for this video. "
                       "The video may not have captions enabled."
            )

        # 3. Build full transcript text with timestamps
        #    New API returns FetchedTranscriptSnippet objects with .text, .start, .duration
        text_parts = []
        for seg in transcript_segments:
            start_sec = int(getattr(seg, 'start', 0))
            minutes = start_sec // 60
            seconds = start_sec % 60
            timestamp = f"[{minutes}:{seconds:02d}]"
            text = getattr(seg, 'text', '').strip()
            if text:
                link = f"https://www.youtube.com/watch?v={video_id}&t={start_sec}s"
                text_parts.append(f"{timestamp} ({link}) {text}")

        if not text_parts:
            raise HTTPException(status_code=400, detail="Transcript was empty")

        # Try to get video title via a lightweight page fetch
        video_title = f"YouTube Video {video_id}"
        try:
            resp = requests.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            if resp.ok:
                soup = BeautifulSoup(resp.text, "html.parser")
                if soup.title and soup.title.string:
                    raw_title = soup.title.string.strip()
                    # Remove " - YouTube" suffix
                    if raw_title.endswith(" - YouTube"):
                        raw_title = raw_title[:-10].strip()
                    if raw_title:
                        video_title = raw_title
        except Exception:
            pass  # Keep default title

        full_text = (
            f"# {video_title}\n\n"
            f"Source: {url}\n"
            f"Video ID: {video_id}\n\n"
            f"## Transcript\n\n" +
            "\n".join(text_parts)
        )

        # 4. Save as .txt file (same approach as ingest_url)
        safe_name = re.sub(r"[^a-zA-Z0-9]", "_", video_title)[:50]
        filename = f"youtube_{safe_name}_{video_id}.txt"
        user_dir = WRITE_RESOURCES_DIR / current_user.id
        user_dir.mkdir(parents=True, exist_ok=True)
        file_path = user_dir / filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        file_size = len(full_text.encode("utf-8"))
        logger.info(f"📝 YouTube transcript saved: {filename} ({file_size} bytes, {len(text_parts)} segments)")

        # 5. Register the file in the database
        try:
            user_db.add_user_file(
                user_id=current_user.id,
                filename=filename,
                file_type="txt",
                file_size=file_size,
                user_token=current_user.access_token
            )
        except Exception as e:
            logger.warning(f"File registration warning: {e}")

        # 6. Queue background processing (chunking + embedding)
        job_id = str(uuid.uuid4())
        try:
            supabase.table("batch_jobs").insert({
                "id": job_id,
                "user_id": current_user.id,
                "doc_name": filename,
                "status": "queued",
                "progress": 0,
                "total_steps": 4,
                "completed_steps": 0
            }).execute()
        except Exception as e:
            logger.warning(f"Batch job creation warning: {e}")
        _enqueue_processing(current_user.id, filename, current_user.access_token, job_id)

        return {
            "success": True,
            "title": video_title,
            "video_id": video_id,
            "filename": filename,
            "transcript_length": len(full_text),
            "segments": len(text_parts),
            "batch_job_id": job_id,
            "message": f"YouTube video '{video_title}' transcript extracted! Processing in background."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YouTube processing failed: {e}")
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
    """Process a file for vectorization.
    - On Vercel: runs chunking+embedding SYNCHRONOUSLY (background tasks get killed by serverless timeout).
    - On regular servers: queues background task for async processing + lesson/video pre-gen.
    """
    try:
        logger.info(f"⚙️ Processing file: {filename} for user {current_user.id} (IS_VERCEL={IS_VERCEL})")

        # Create batch job record
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

        if IS_VERCEL:
            # ── Vercel: run Step 1 (chunking+embedding) synchronously ──
            # Background tasks are killed by Vercel's serverless timeout.
            # We only do vectorization here; lesson/video pre-gen is deferred to
            # the frontend's silent pre-fetch when the user opens AI Teacher.
            try:
                _update_batch_status(batch_job_id, "processing", progress=5, total_steps=4, completed_steps=0)

                # Resolve file — check local paths first, then download from Supabase Storage
                local_path = WRITE_RESOURCES_DIR / filename
                if not local_path.exists():
                    local_path = STATIC_RESOURCES_DIR / filename
                user_temp_dir = WRITE_RESOURCES_DIR / current_user.id
                if not local_path.exists():
                    local_path = user_temp_dir / filename

                if not local_path.exists():
                    # Try fetching blob URL from Supabase metadata
                    s_files = user_db.get_user_files(current_user.id, current_user.access_token)
                    file_meta = next((f for f in s_files if f.get('filename') == filename or f.get('file_name') == filename), None)
                    blob_url = file_meta.get('blob_url') if file_meta else None
                    if blob_url:
                        logger.info(f"⬇️ Downloading from blob: {blob_url}")
                        r = requests.get(blob_url, timeout=60)
                        r.raise_for_status()
                        user_temp_dir.mkdir(exist_ok=True)
                        local_path = user_temp_dir / filename
                        with open(local_path, 'wb') as f:
                            f.write(r.content)

                if not local_path.exists():
                    _update_batch_status(batch_job_id, "failed", error="File not found")
                    raise HTTPException(status_code=404, detail="File not found for processing")

                # Run chunking + embedding synchronously in thread pool
                from dataprocessor import process_file
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: process_file(str(local_path), user_id=current_user.id))
                chunks_created = result.get("chunks_created", 0)

                # Update file metadata in Supabase
                try:
                    user_db.update_file_processed(
                        user_id=current_user.id, filename=filename,
                        chunks_created=chunks_created, user_token=current_user.access_token
                    )
                except Exception as e:
                    logger.warning(f"Metadata update failed: {e}")

                _update_batch_status(batch_job_id, "completed", progress=100, completed_steps=4, total_steps=4)
                logger.info(f"✅ Vercel sync vectorization done: {filename} ({chunks_created} chunks)")

                return {
                    "success": True,
                    "queued": False,
                    "batch_job_id": batch_job_id,
                    "chunks_created": chunks_created,
                    "message": f"File {filename} vectorized ({chunks_created} chunks)"
                }

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Vercel sync processing failed for {filename}: {e}")
                _update_batch_status(batch_job_id, "failed", error=str(e))
                raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

        else:
            # ── Standard server: enqueue background task ──
            _enqueue_processing(current_user.id, filename, current_user.access_token, batch_job_id)
            return {
                "success": True,
                "queued": True,
                "batch_job_id": batch_job_id,
                "message": f"File {filename} queued for processing"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {filename}: {e}")
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


@app.get("/api/prewarm-status")
async def prewarm_status(
    doc_name: str = "",
    current_user: User = Depends(get_current_user)
):
    """
    Convenience endpoint for checking if a document's lessons are pre-warmed.
    Returns status + lesson count so the frontend can show a readiness banner.
    """
    try:
        # Get latest batch job for this doc
        query = supabase.table("batch_jobs").select("*")
        if doc_name:
            query = query.eq("doc_name", doc_name)
        # Look across all users for teacher-uploaded docs too
        result = query.order("created_at", desc=True).limit(1).execute()

        if not result.data:
            return {"success": True, "status": "not_found", "progress": 0, "lessons_ready": 0}

        job = result.data[0]
        status = job.get("status", "unknown")

        # Count pre-generated lessons in cache
        lessons_ready = 0
        try:
            lc = supabase.table("lesson_cache").select("cache_key", count="exact") \
                .eq("doc_name", doc_name).in_("lesson_type", ["conversation", "tts_video"]).execute()
            lessons_ready = lc.count if hasattr(lc, "count") and lc.count else len(lc.data or [])
        except Exception:
            pass

        status_labels = {
            "queued": "⏳ Waiting to start...",
            "processing": "📄 Chunking & embedding document...",
            "extracting_topics": "🔍 Extracting topics...",
            "generating_lessons": "📝 Pre-generating AI lessons...",
            "generating_videos": "🎬 Pre-generating teaching videos...",
            "completed": "✅ All lessons ready!",
            "failed": "❌ Processing failed."
        }

        return {
            "success": True,
            "status": status,
            "label": status_labels.get(status, status),
            "progress": job.get("progress", 0),
            "lessons_ready": lessons_ready,
            "is_ready": status == "completed"
        }
    except Exception as e:
        logger.error(f"Prewarm status error: {e}")
        return {"success": True, "status": "unknown", "progress": 0, "lessons_ready": 0}

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
_EDTECH_CACHE_TTL = 86400    # 24 hours (topics don't change once extracted)

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

        async def _query_ns(ns):
            """Query a single namespace and return matching chunks."""
            chunks = []
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
                        chunks.append({
                            "text": text,
                            "page": page,
                            "chapter": chapter
                        })
            except Exception as e:
                logger.warning(f"Namespace {ns} query failed: {e}")
            return chunks

        # 1. Try student's own namespaces first
        for ns in namespaces:
            all_chunks.extend(await _query_ns(ns))

        # 2. If nothing found (assigned doc likely uploaded by teacher), search ALL namespaces
        if not all_chunks:
            logger.info(f"📚 No chunks in student namespaces for '{doc_name}', searching all namespaces (teacher-uploaded doc)")
            try:
                stats = await loop.run_in_executor(None, index.describe_index_stats)
                all_namespaces = list(stats.namespaces.keys())
                # Skip the ones we already checked
                extra_ns = [ns for ns in all_namespaces if ns not in namespaces]
                for ns in extra_ns:
                    all_chunks.extend(await _query_ns(ns))
            except Exception as e:
                logger.warning(f"Cross-namespace fallback failed: {e}")

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
        logger.info(f"🎯 Topics cache HIT (mem): {doc_name} / {chapter or 'whole doc'}")
        return cached["data"]

    # FIX 3: Check lesson_cache table (populated by background pre-warm at upload time)
    # This makes topics instant on pre-warmed documents — no Pinecone or LLM call needed.
    # IMPORTANT: Normalize "Untitled Section" (UI label for empty-chapter docs) → "__all__"
    # because the background task saves with chapter="" → "__all__", not the display label.
    UNTITLED_DISPLAY = "Untitled Section"
    cache_chapter_key = "__all__" if (not chapter or chapter == UNTITLED_DISPLAY) else chapter
    try:
        lc_key = _lesson_cache_key(current_user.id, doc_name, cache_chapter_key, language, "topics")
        lc_row = _get_cached_lesson(lc_key)
        if not lc_row:
            # Also check any user's pre-warm (teacher uploaded, student accesses)
            cross = supabase.table("lesson_cache").select("*") \
                .eq("doc_name", doc_name).eq("lesson_type", "topics") \
                .eq("topic", cache_chapter_key).eq("language", language).limit(1).execute()
            if cross.data:
                lc_row = cross.data[0]
        if lc_row and lc_row.get("lesson_json", {}).get("topics"):
            result = {"success": True, "topics": lc_row["lesson_json"]["topics"], "cached": True}
            _topics_cache[topic_cache_key] = {"data": result, "ts": _time.time()}
            logger.info(f"🎯 Topics cache HIT (db): {doc_name} / {cache_chapter_key}")
            return result
    except Exception as _e:
        logger.warning(f"Topics lesson_cache lookup failed (non-fatal): {_e}")
    try:
        from edtech_service import extract_topics
        from vectorstore import index, get_user_namespaces
        import re as _re

        namespaces = get_user_namespaces(current_user.id)
        all_chunks = []
        loop = asyncio.get_event_loop()

        # Build Pinecone filter — optionally filter by chapter.
        # IMPORTANT: "Untitled Section" is only a display label assigned in the
        # chapter-listing endpoint for chunks that have chapter="" (empty) in Pinecone.
        # When the frontend sends chapter="Untitled Section" we must query
        # for chunks with chapter="" (or missing chapter), NOT the literal string.
        UNTITLED_DISPLAY = "Untitled Section"
        raw_chapter = chapter  # actual value stored in Pinecone

        if chapter == UNTITLED_DISPLAY:
            # Web pages / undivided docs → stored with empty or absent chapter field
            raw_chapter = ""

        if raw_chapter:
            # Named chapter: exact match
            pinecone_filter = {
                "$and": [
                    {"doc_name": {"$eq": doc_name}},
                    {"chapter": {"$eq": raw_chapter}}
                ]
            }
        elif chapter:
            # "Untitled Section" case: match chunks with chapter="" or chapter absent
            pinecone_filter = {
                "$and": [
                    {"doc_name": {"$eq": doc_name}},
                    {"$or": [
                        {"chapter": {"$eq": ""}},
                        {"chapter": {"$exists": False}}
                    ]}
                ]
            }
        else:
            # No chapter filter — full document
            pinecone_filter = {"doc_name": {"$eq": doc_name}}

        async def _query_ns_topics(ns):
            """Query a single namespace for topics and return matching chunks."""
            chunks = []
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
                        chunks.append({
                            "text": text,
                            "page": page,
                            "chapter": ch
                        })
            except Exception as e:
                logger.warning(f"Namespace {ns} query failed: {e}")
            return chunks

        # 1. Try student's own namespaces first
        for ns in namespaces:
            all_chunks.extend(await _query_ns_topics(ns))

        # 2. If nothing found (teacher-uploaded doc), search ALL namespaces
        if not all_chunks:
            logger.info(f"📚 No chunks in student namespaces for '{doc_name}' topics, searching all namespaces")
            try:
                stats = await loop.run_in_executor(None, index.describe_index_stats)
                all_namespaces = list(stats.namespaces.keys())
                extra_ns = [ns for ns in all_namespaces if ns not in namespaces]
                for ns in extra_ns:
                    all_chunks.extend(await _query_ns_topics(ns))
            except Exception as e:
                logger.warning(f"Cross-namespace fallback failed for topics: {e}")

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

        topics = await loop.run_in_executor(None, lambda: extract_topics(
            combined,
            language,
            [doc_name],
            min_topics=1 if len(all_chunks) <= 3 else 3,
            max_topics=3 if len(all_chunks) <= 3 else 8
        ))

        response = {
            "success": True,
            "topics": topics,
            "document": doc_name,
            "chapter": chapter,
            "chunks_used": len(content_parts),
            "total_chunks": len(all_chunks)
        }
        # Cache the result in memory
        _topics_cache[topic_cache_key] = {"data": response, "ts": _time.time()}

        # Persist to lesson_cache DB so topics survive server restarts
        try:
            persist_chapter = "__all__" if (not chapter or chapter == UNTITLED_DISPLAY) else chapter
            db_cache_key = _lesson_cache_key(current_user.id, doc_name, persist_chapter, language, "topics")
            _save_lesson_cache(
                user_id=current_user.id, cache_key=db_cache_key,
                doc_name=doc_name, topic=persist_chapter,
                language=language, lesson_type="topics",
                lesson_json={"topics": topics, "chapter": chapter},
            )
            logger.info(f"💾 Topics saved to DB cache: {doc_name} / {persist_chapter}")
        except Exception as db_err:
            logger.warning(f"Could not persist topics to DB (non-fatal): {db_err}")

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
    doc_name: str = Form(""),
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
        # Cross-user fallback — reuse teacher's pre-warmed lesson for students
        if not cached and doc_name:
            try:
                cross = supabase.table("lesson_cache").select("*") \
                    .eq("topic", topic).eq("lesson_type", "conversation").eq("language", language).limit(1).execute()
                if cross.data:
                    cached = cross.data[0]
                    import time as _t
                    _lesson_mem_cache[cache_key] = {"data": cached, "ts": _t.time()}
            except Exception:
                pass
        if cached:
            cached_lesson = cached.get("lesson_json", {})
            cached_audio = cached_lesson.get("audio_urls", [])
            # Always return cached lesson if it has dialogue content
            if cached_lesson.get("dialogue"):
                if cached_audio and any(u for u in cached_audio):
                    logger.info(f"🎯 Lesson cache HIT (with audio): {topic}")
                else:
                    logger.info(f"🎯 Lesson cache HIT (no audio yet — will try background TTS): {topic}")
                    # Fire-and-forget: try generating audio in background
                    async def _bg_audio():
                        try:
                            from heygen_service import generate_dialogue_audio, TTS_AUDIO_DIR as _TD
                            _loop = asyncio.get_event_loop()
                            _dialogue = cached_lesson.get("dialogue", [])
                            _voice_map = cached_lesson.get("voice_map", {})
                            if _dialogue and _voice_map:
                                _vm = {**_voice_map, "__language__": language}
                                _af = await _loop.run_in_executor(None, lambda: generate_dialogue_audio(
                                    dialogue_lines=_dialogue, voice_map=_vm,
                                    topic=topic, user_id=current_user.id, doc_name=doc_name
                                ))
                                _urls = []
                                _paths = []
                                for _fn in _af:
                                    if _fn:
                                        _lf = _TD / _fn
                                        _sp = f"dialogue/{current_user.id}/{_fn}"
                                        _pu = _upload_audio_to_storage(str(_lf), _sp)
                                        _urls.append(_pu or f"/static/tts_audio/{_fn}")
                                        _paths.append(_sp if _pu else "")
                                    else:
                                        _urls.append("")
                                        _paths.append("")
                                cached_lesson["audio_urls"] = _urls
                                _save_lesson_cache(
                                    user_id=current_user.id, cache_key=cache_key,
                                    topic=topic, doc_name=doc_name,
                                    language=language, lesson_type="conversation",
                                    lesson_json=cached_lesson, audio_storage_paths=_paths
                                )
                                logger.info(f"✅ Background audio generated for cached lesson: {topic}")
                        except Exception as _e:
                            logger.warning(f"Background audio gen failed (non-fatal): {_e}")
                    asyncio.create_task(_bg_audio())
                return {"success": True, "lesson": cached_lesson, "cached": True}

        # ── 2. Cache miss — generate dialogue text only (fast GPT call) ──
        logger.info(f"🔄 Lesson cache MISS: {topic}")
        loop = asyncio.get_event_loop()

        query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))

        if doc_name:
            from vectorstore import search_by_doc_name
            results = await loop.run_in_executor(
                None, lambda: search_by_doc_name(query_vec, doc_name, top_k=10)
            )
            if not results:
                logger.warning(f"search_by_doc_name found no results for '{doc_name}', falling back to user docs")
                results = await loop.run_in_executor(
                    None, lambda: search_user_documents(query_vec, current_user.id, top_k=10)
                )
        else:
            results = await loop.run_in_executor(
                None, lambda: search_user_documents(query_vec, current_user.id, top_k=10)
            )

        if not results:
            return {"success": False, "detail": "No relevant content found for this topic. Please process more documents."}

        chunks_with_refs = []
        for r in results:
            text = r.get("text", "")
            d = r.get("doc_name", "Unknown")
            page = r.get("page", "")
            if text:
                chunks_with_refs.append(f"[From: {d}, Page: {page}]\n{text}")

        if not chunks_with_refs:
            return {"success": False, "detail": "No relevant content found for this topic."}

        combined = "\n\n---\n\n".join(chunks_with_refs)
        lesson = await loop.run_in_executor(None, lambda: generate_teacher_dialogue(topic, combined, language))

        # ── 3. Generate TTS audio BEFORE returning ──
        from heygen_service import generate_dialogue_audio, TTS_AUDIO_DIR, enrich_sentences_with_images
        dialogue = lesson.get("dialogue", [])
        voice_map = lesson.get("voice_map", {})

        audio_urls = []
        audio_storage_paths = []
        if dialogue and voice_map:
            voice_map_with_lang = {**voice_map, "__language__": language}
            audio_files = await loop.run_in_executor(None, lambda: generate_dialogue_audio(
                dialogue_lines=dialogue,
                voice_map=voice_map_with_lang,
                topic=topic,
                user_id=current_user.id,
                doc_name=doc_name
            ))
            for f_name in audio_files:
                if f_name:
                    local_file = TTS_AUDIO_DIR / f_name
                    storage_path = f"dialogue/{current_user.id}/{f_name}"
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

        lesson["audio_urls"] = audio_urls

        # ── 4. Save lesson WITH audio to cache ──
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

        # ── 5. Fire-and-forget: enrich with images (non-critical) ──
        async def _enrich_lesson_images():
            try:
                dialogue_texts = [line.get("text", "") for line in dialogue]
                enriched = await loop.run_in_executor(
                    None, lambda: enrich_sentences_with_images(dialogue_texts, topic, language)
                )
                for i, line in enumerate(dialogue):
                    if i < len(enriched):
                        line["image_url"] = enriched[i].get("image_url", "")
                        line["image_caption"] = enriched[i].get("image_caption", "")
                lesson["dialogue"] = dialogue
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
                logger.info(f"✅ Background images enriched for lesson: {topic}")
            except Exception as img_err:
                logger.warning(f"Background image enrichment failed (non-fatal): {img_err}")

        asyncio.create_task(_enrich_lesson_images())

        return {"success": True, "lesson": lesson}

    except Exception as e:
        logger.error(f"EdTech lesson generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/edtech/lesson-audio-status")
async def edtech_lesson_audio_status(
    topic: str,
    doc_name: str = "",
    language: str = "en",
    current_user: User = Depends(get_current_user)
):
    """
    Poll endpoint: check if background TTS audio generation is done for a lesson.
    Returns { audio_urls: [...], audio_generating: bool }.
    Frontend polls this every 3 seconds until audio_generating is False.
    """
    try:
        cache_key = _lesson_cache_key(current_user.id, doc_name, topic, language, "conversation")
        cached = _get_cached_lesson(cache_key)
        if not cached:
            return {"audio_urls": [], "audio_generating": False}

        lesson_json = cached.get("lesson_json", {})
        return {
            "audio_urls": lesson_json.get("audio_urls", []),
            "audio_generating": lesson_json.get("audio_generating", False),
        }
    except Exception as e:
        logger.warning(f"Lesson audio status check failed: {e}")
        return {"audio_urls": [], "audio_generating": False}


@app.get("/api/edtech/did-presenters")
async def edtech_did_presenters(current_user: User = Depends(get_current_user)):
    """Return available D-ID presenter avatars for the frontend picker."""
    from did_service import get_presenters
    return {"success": True, "presenters": get_presenters()}


@app.post("/api/edtech/generate-did-video")
async def edtech_generate_did_video(
    request: Request,
    topic: str = Form(...),
    language: str = Form("en"),
    doc_name: str = Form(""),
    presenter_id: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    """
    Return a pre-generated AI Teacher video from the database cache.

    D-ID API calls are DISABLED to save cost.  This endpoint now only
    looks up videos that were previously generated and stored in the
    Supabase `ai_videos` table.  If no cached video is found for the
    requested topic, a user-friendly message is returned instead.
    """
    try:
        from did_service import get_cached_did_video
        from local_video_service import get_supabase_cached_video

        logger.info(f"🎬 Video request (DB-only, D-ID disabled): topic='{topic}', "
                     f"lang={language}, presenter={presenter_id}")

        # ── 1. Check D-ID cache (memory → Supabase ai_videos) ──
        cached = get_cached_did_video(topic, doc_name, language, presenter_id)

        # ── 2. Fallback: check local/generic video cache ──
        if not cached or not cached.get("video_url"):
            cached_local = get_supabase_cached_video(topic, doc_name, language)
            if cached_local and cached_local.get("video_url"):
                logger.info(f"🎯 Local video cache HIT: {topic}")
                video_url = cached_local["video_url"]
                if video_url and video_url.startswith("/"):
                    base = str(request.base_url).rstrip("/")
                    video_url = f"{base}{video_url}"
                return {
                    "success": True,
                    "video_url": video_url,
                    "video_id": cached_local.get("video_id", ""),
                    "presenter": cached_local.get("presenter", "AI Teacher"),
                    "script": cached_local.get("script", ""),
                    "cached": True,
                    "lip_sync": False,
                }

        # ── 3. Return D-ID cached video if found ──
        if cached and cached.get("video_url"):
            logger.info(f"🎯 D-ID cache HIT: {topic}")
            video_url = cached["video_url"]
            if video_url and video_url.startswith("/"):
                base = str(request.base_url).rstrip("/")
                video_url = f"{base}{video_url}"
            return {
                "success": True,
                "video_url": video_url,
                "video_id": cached.get("talk_id", ""),
                "presenter": cached.get("presenter", "AI Teacher"),
                "script": cached.get("script", ""),
                "cached": True,
                "lip_sync": True,
            }

        # ── 4. No cached video available — do NOT call D-ID API ──
        logger.info(f"📋 No cached video found for '{topic}' — D-ID API disabled")
        return {
            "success": False,
            "detail": (
                "No pre-generated video is available for this topic yet. "
                "Please try the Conversation mode or TTS Video mode instead."
            ),
        }

    except Exception as e:
        logger.error(f"Video lookup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video lookup failed: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════
# Professional HeyGen Avatar Video — premium AI presenter with subtitles
# ════════════════════════════════════════════════════════════════════════════
@app.post("/api/edtech/generate-heygen-video")
async def edtech_generate_heygen_video(
    request: Request,
    topic: str = Form(...),
    language: str = Form("en"),
    doc_name: str = Form(""),
    avatar_type: str = Form("public"),
    avatar_id: str = Form(""),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a PROFESSIONAL HeyGen avatar video.
    Uses HeyGen API with language selection (English / Tamil Thanglish)
    and always-on English subtitles.

    Steps:
      1. Check Supabase ai_videos cache → return instantly if already done
      2. Retrieve RAG context (Pinecone) for the requested topic
      3. Generate a narration script (Thanglish or English) via GPT
      4. Submit to HeyGen v2 → poll until completed
      5. Cache in Supabase → return video URL
    """
    try:
        from heygen_service import (
            generate_heygen_video_sync,
            generate_heygen_script,
            get_supabase_cached_video,
            list_available_avatars,
        )
        from embedder import embed_User_query
        from vectorstore import search_user_documents

        # ── 1. Check Supabase cache (keyed by language + "heygen" prefix) ──
        cache_topic = f"heygen_{topic}"
        cached = get_supabase_cached_video(cache_topic, doc_name, language)
        if cached and cached.get("video_url"):
            logger.info(f"🎯 HeyGen video cache HIT: {topic} ({language})")
            return {
                "success": True,
                "video_url": cached["video_url"],
                "video_id": cached.get("video_id", ""),
                "presenter": cached.get("presenter", "HeyGen Avatar"),
                "script": cached.get("script", ""),
                "cached": True,
            }

        # ── 2. Retrieve relevant RAG context ──
        loop = asyncio.get_event_loop()
        query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))

        if doc_name:
            from vectorstore import search_by_doc_name
            results = await loop.run_in_executor(
                None, lambda: search_by_doc_name(query_vec, doc_name, top_k=8)
            )
            if not results:
                results = await loop.run_in_executor(
                    None, lambda: search_user_documents(query_vec, current_user.id, top_k=8)
                )
        else:
            results = await loop.run_in_executor(
                None, lambda: search_user_documents(query_vec, current_user.id, top_k=8)
            )

        if not results:
            raise HTTPException(status_code=404, detail="No relevant content found for this topic.")

        context_chunks = [r.get("text", "") for r in results if r.get("text")]
        combined = "\n\n".join(context_chunks[:6])

        # ── 3. Generate concise HeyGen script (under 1 minute, complete summary) ──
        script = await loop.run_in_executor(
            None, lambda: generate_heygen_script(topic, combined, language)
        )
        logger.info(f"📝 HeyGen script generated ({len(script)} chars, ~{len(script.split())} words) for '{topic}' [{language}]")

        # ── 4. HeyGen video pipeline (runs in thread pool) ──
        result = await loop.run_in_executor(
            None,
            lambda: generate_heygen_video_sync(
                script, cache_topic, doc_name, language, avatar_type, avatar_id
            )
        )

        return {
            "success": True,
            "video_url": result["video_url"],
            "video_id": result.get("video_id", ""),
            "presenter": result.get("presenter", "HeyGen Avatar"),
            "script": script,
            "cached": result.get("cached", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HeyGen video generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Professional video generation failed: {str(e)}")


# ════════════════════════════════════════════════════════════════════════════
# List HeyGen Avatars & Talking Photos for the frontend selector
# ════════════════════════════════════════════════════════════════════════════
@app.get("/api/edtech/heygen-avatars")
async def edtech_list_heygen_avatars(
    current_user: User = Depends(get_current_user)
):
    """Return available public avatars and talking photos from HeyGen."""
    try:
        from heygen_service import list_available_avatars
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, list_available_avatars)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"Failed to list HeyGen avatars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# Upload a Talking Photo to HeyGen
# ════════════════════════════════════════════════════════════════════════════
@app.post("/api/edtech/heygen-upload-photo")
async def edtech_upload_talking_photo(
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a user photo to HeyGen as a talking photo avatar."""
    try:
        from heygen_service import upload_talking_photo
        image_bytes = await photo.read()
        if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB limit
            raise HTTPException(status_code=400, detail="Image must be under 10 MB")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: upload_talking_photo(image_bytes, photo.filename or "photo.jpg")
        )
        if result.get("success"):
            return {"success": True, "id": result["id"], "image_url": result["image_url"]}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Upload failed"))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload talking photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ════════════════════════════════════════════════════════════════════════════
# DEAD CODE — HeyGen backup (kept for reference; not active)
# Restore by replacing the endpoint above with this block.
# Note: requires HEYGEN_API_KEY with an active HeyGen *API* plan ($99/mo).
# ════════════════════════════════════════════════════════════════════════════
# @app.post("/api/edtech/generate-did-video")
# async def edtech_generate_heygen_video(
#     topic: str = Form(...),
#     language: str = Form("en"),
#     doc_name: str = Form(""),
#     current_user: User = Depends(get_current_user)
# ):
#     try:
#         from heygen_service import generate_heygen_video_sync, get_supabase_cached_video
#         from embedder import embed_User_query
#         from vectorstore import search_user_documents
#         cached = get_supabase_cached_video(topic, doc_name, language)
#         if cached and cached.get("video_url"):
#             return {"success": True, **cached, "cached": True}
#         loop = asyncio.get_event_loop()
#         query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))
#         results = await loop.run_in_executor(
#             None, lambda: search_user_documents(query_vec, current_user.id, top_k=8))
#         if not results:
#             raise HTTPException(status_code=404, detail="No content found.")
#         combined = "\n\n".join([r.get("text","") for r in results[:6]])
#         from openai import OpenAI
#         script_resp = OpenAI().chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[{"role":"user","content":f"Educational script about {topic}:\n{combined}"}],
#             max_tokens=800)
#         script = script_resp.choices[0].message.content.strip()
#         result = await loop.run_in_executor(
#             None, lambda: generate_heygen_video_sync(script, topic, doc_name, language))
#         return {"success": True, "video_url": result["video_url"],
#                 "video_id": result.get("video_id",""), "presenter":"HeyGen Avatar",
#                 "script": script, "cached": result.get("cached", False)}
#     except HTTPException: raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"HeyGen failed: {str(e)}")


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
            lang_instruction = (
                "\nIMPORTANT: Answer in THANGLISH style — "
                "Use Tamil script (தமிழ்) as the primary language, "
                "but mix in English words naturally for technical terms, greetings, and common phrases. "
                "Use everyday conversational Tamil, NOT formal literary Tamil. "
                "Example: 'இது oru important concept. இதை நாம் simple-ஆ புரிஞ்சுக்கலாம்.' "
                "Keep it friendly and easy to understand like daily Tamil conversation."
            )

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

            if language == "ta":
                # ── Sarvam AI — natural Tamil voice for Q&A answers ──
                from heygen_service import generate_sarvam_tts, TTS_AUDIO_DIR as _TTS_DIR
                def _generate():
                    generate_sarvam_tts(tts_text, audio_path, language="ta")
            else:
                # ── OpenAI TTS — English ──
                voice = "nova"
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

        # 2. Search for relevant chunks:
        # - If doc_name is provided (classroom assignment), search across ALL namespaces
        #   filtered by that document name (teacher may own it).
        # - Otherwise fall back to the student's own uploaded documents.
        query_vec = embed_User_query(topic)

        if doc_name:
            from vectorstore import search_by_doc_name
            results = search_by_doc_name(query_vec, doc_name, top_k=10)
            if not results:
                logger.warning(f"search_by_doc_name found no results for '{doc_name}', falling back to user docs")
                results = search_user_documents(query_vec, current_user.id, top_k=10)
        else:
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
        # FIX 2: Cross-user fallback — student hits teacher pre-generated TTS video
        if not cached and doc_name:
            try:
                cross = supabase.table("lesson_cache").select("*") \
                    .eq("doc_name", doc_name).eq("topic", topic) \
                    .eq("lesson_type", "tts_video").eq("language", language).limit(1).execute()
                if cross.data:
                    cached = cross.data[0]
                    import time as _t
                    _lesson_mem_cache[cache_key] = {"data": cached, "ts": _t.time()}
            except Exception:
                pass
        if cached:
            cached_lesson = cached.get("lesson_json", {})
            cached_audio = cached_lesson.get("audio_url", "")
            if cached_audio:
                logger.info(f"🎯 TTS video cache HIT (with audio): {topic}")
                return {"success": True, **cached_lesson, "cached": True}
            else:
                logger.info(f"🔄 TTS video cache HIT but NO audio — regenerating: {topic}")

        # ── 2. Cache miss — generate from scratch ──
        logger.info(f"🔄 TTS video cache MISS: {topic}")
        loop = asyncio.get_event_loop()

        # Search for relevant chunks:
        # - If doc_name is provided (classroom assignment), search across ALL namespaces
        #   filtered by that document name (teacher may own it).
        # - Otherwise fall back to the student's own uploaded documents.
        query_vec = await loop.run_in_executor(None, lambda: embed_User_query(topic))

        if doc_name:
            from vectorstore import search_by_doc_name
            results = await loop.run_in_executor(
                None, lambda: search_by_doc_name(query_vec, doc_name, top_k=10)
            )
            if not results:
                logger.warning(f"search_by_doc_name found no results for '{doc_name}', falling back to user docs")
                results = await loop.run_in_executor(
                    None, lambda: search_user_documents(query_vec, current_user.id, top_k=10)
                )
        else:
            results = await loop.run_in_executor(
                None, lambda: search_user_documents(query_vec, current_user.id, top_k=10)
            )

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

        # Always ensure audio_url exists in the response (prevent frontend crash)
        if "audio_url" not in result:
            result["audio_url"] = ""
        response = {"success": result.get("status") != "failed", **result}

        # ── 3b. Enrich TTS sentences with Wikipedia images ──
        try:
            from heygen_service import enrich_sentences_with_images
            raw_sentences = result.get("sentences", [])
            if raw_sentences:
                enriched = await loop.run_in_executor(
                    None, lambda: enrich_sentences_with_images(raw_sentences, topic, language)
                )
                response["sentences"] = enriched  # Replace plain strings with enriched dicts
        except Exception as img_err:
            logger.warning(f"TTS image enrichment failed (non-fatal): {img_err}")

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
    """Switch user role: teacher | student | individual | other."""
    VALID_ROLES = {"teacher", "student", "individual", "other"}
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(sorted(VALID_ROLES))}")
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
    chapter_name: str = Form(""),
    topics: str = Form(""),   # JSON-encoded list sent by the frontend
    current_user: User = Depends(get_current_user)
):
    """Create a new classroom (teacher only)."""
    allowed_roles = {"teacher", "admin"}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Only teachers can create classrooms. Your current role is '{current_user.role}'. "
                   f"Please update your role from the profile settings."
        )
    try:
        join_code = _generate_join_code()
        # Ensure unique join code
        for _ in range(5):
            existing = supabase.table("classrooms").select("id").eq("join_code", join_code).execute()
            if not existing.data:
                break
            join_code = _generate_join_code()

        import json as _json
        row = {
            "teacher_id": current_user.id,
            "name": name,
            "description": description,
            "doc_name": doc_name,
            "join_code": join_code
        }
        if chapter_name:
            row["chapter_name"] = chapter_name
        if topics:
            try:
                row["topics"] = _json.dumps(_json.loads(topics))
            except Exception:
                pass

        # Try inserting with all extra columns; fall back stripping them if DB doesn't have them
        try:
            result = supabase.table("classrooms").insert(row).execute()
        except Exception:
            row.pop("chapter_name", None)
            row.pop("topics", None)
            result = supabase.table("classrooms").insert(row).execute()

        return {"success": True, "classroom": result.data[0] if result.data else None}
    except Exception as e:
        logger.error(f"Classroom creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.delete("/api/classrooms/{classroom_id}")
async def delete_classroom(classroom_id: str, current_user: User = Depends(get_current_user)):
    """Delete a classroom (owner teacher only)."""
    try:
        # Verify ownership
        existing = supabase.table("classrooms").select("teacher_id").eq("id", classroom_id).single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Classroom not found")
        if existing.data["teacher_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Only the classroom owner can delete it")
        # Delete child rows first (ignore if table doesn't exist)
        try:
            supabase.table("classroom_students").delete().eq("classroom_id", classroom_id).execute()
        except Exception:
            pass
        supabase.table("classrooms").delete().eq("id", classroom_id).execute()
        return {"success": True, "message": "Classroom deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete classroom failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/classrooms")
async def list_classrooms(current_user: User = Depends(get_current_user)):
    """List classrooms — teacher sees owned, student sees joined."""
    try:
        if current_user.role in ("teacher", "admin"):
            result = supabase.table("classrooms").select("*").eq("teacher_id", current_user.id).order("created_at", desc=True).execute()
            classrooms = result.data or []
            # Attach student count — gracefully skip if table doesn't exist yet
            for cls in classrooms:
                try:
                    count = supabase.table("classroom_students").select("id", count="exact").eq("classroom_id", cls["id"]).execute()
                    cls["student_count"] = count.count if count.count is not None else 0
                except Exception:
                    cls["student_count"] = 0
        else:
            # Student: get classrooms they've joined
            try:
                memberships = supabase.table("classroom_students").select("classroom_id").eq("student_id", current_user.id).execute()
                classroom_ids = [m["classroom_id"] for m in (memberships.data or [])]
            except Exception:
                classroom_ids = []
            if classroom_ids:
                result = supabase.table("classrooms").select("*").in_("id", classroom_ids).execute()
                classrooms = result.data or []
            else:
                classrooms = []
            # Attach teacher name
            for cls in classrooms:
                try:
                    teacher = supabase.table("profiles").select("full_name").eq("id", cls["teacher_id"]).limit(1).execute()
                    cls["teacher_name"] = teacher.data[0]["full_name"] if teacher.data else "Teacher"
                except Exception:
                    cls["teacher_name"] = "Teacher"

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

@app.get("/api/documents")
async def list_processed_documents(current_user: User = Depends(get_current_user)):
    """Return all processed documents for the current user (for assignment book-picker)."""
    try:
        # Try Supabase user_files table first
        result = supabase.table("user_files").select("id, filename, file_type, chunks_created, processed, uploaded_at") \
            .eq("user_id", current_user.id).eq("processed", True).order("uploaded_at", desc=True).execute()
        if result.data:
            return {"success": True, "documents": result.data}

        # Fallback: read from local .file_metadata.json
        import json as _json, os as _os
        meta_path = _os.path.join(_os.path.dirname(__file__), "resources", ".file_metadata.json")
        if _os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = _json.load(f)
            docs = [d for d in (meta.get("files") or []) if d.get("processed")]
            return {"success": True, "documents": docs}

        return {"success": True, "documents": []}
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{filename}/structure")
async def get_document_structure(filename: str, current_user: User = Depends(get_current_user)):
    """
    Extract chapters and topics from a processed document by scanning its Pinecone chunks.
    Uses heuristic heading detection — lines that look like chapters/section titles.
    """
    try:
        import hashlib as _hashlib, re as _re
        from vectorstore import index

        user_hash = _hashlib.md5(current_user.id.encode()).hexdigest()[:8]
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
        namespace = f"{ext}-user-{user_hash}"

        # We don't have a text-level heading API from Pinecone, so we'll
        # do a broad zero-vector query to collect all chunks for this file.
        try:
            stats = index.describe_index_stats()
            dim = stats.dimension
        except Exception:
            dim = 1536
        dummy = [0.0] * dim

        try:
            res = index.query(
                vector=dummy,
                top_k=1000,
                include_metadata=True,
                filter={"doc_name": {"$eq": filename}},
                namespace=namespace,
            )
            chunks = [m.metadata.get("text", "") for m in (res.matches or []) if m.metadata.get("text")]
        except Exception:
            chunks = []

        # If no chunks found, try all user namespaces
        if not chunks:
            file_types = ["pdf", "xlsx", "xls", "csv", "txt", "docx", "doc", "xml"]
            for ft in file_types:
                ns = f"{ft}-user-{user_hash}"
                try:
                    res = index.query(
                        vector=dummy,
                        top_k=1000,
                        include_metadata=True,
                        filter={"doc_name": {"$eq": filename}},
                        namespace=ns,
                    )
                    chunks = [m.metadata.get("text", "") for m in (res.matches or []) if m.metadata.get("text")]
                    if chunks:
                        break
                except Exception:
                    continue

        # ── Heuristic heading extraction ──────────────────────────────────
        chapter_pattern = _re.compile(
            r'^(chapter\s+[\divxlc]+[:\.\s]|unit\s+[\divxlc]+[:\.\s]|section\s+[\d\.]+|lesson\s+\d+|module\s+\d+|part\s+[\divxlc]+)',
            _re.IGNORECASE
        )
        topic_patterns = [
            _re.compile(r'^\d+[\.\)]\s+[A-Z].{5,80}$'),   # numbered items
            _re.compile(r'^[A-Z][A-Z\s]{4,50}$'),           # ALL CAPS headings
            _re.compile(r'^[A-Z][a-zA-Z\s\-]{5,60}:?\s*$'), # Title Case lines
        ]

        chapters_found = {}
        current_chapter = None

        for chunk in chunks:
            for line in chunk.split("\n"):
                line = line.strip()
                if not line or len(line) < 4:
                    continue

                # Is it a chapter/unit heading?
                if chapter_pattern.match(line):
                    title = line[:120]
                    if title not in chapters_found:
                        chapters_found[title] = []
                    current_chapter = title
                    continue

                # Is it a topic/subtopic heading?
                if current_chapter:
                    for pat in topic_patterns:
                        if pat.match(line) and len(chapters_found[current_chapter]) < 20:
                            topic = line.rstrip(":").strip()[:80]
                            if topic not in chapters_found[current_chapter]:
                                chapters_found[current_chapter].append(topic)
                            break

        # If no chapters detected, create a generic structure from distinct text segments
        if not chapters_found:
            # Offer page-level grouping as fallback
            chapters_found["Full Document"] = []
            all_lines = []
            for chunk in chunks[:30]:
                for line in chunk.split("\n"):
                    line = line.strip()
                    if 10 < len(line) < 80 and line[0].isupper():
                        all_lines.append(line.rstrip(":"))
            # Deduplicate
            seen = set()
            for l in all_lines:
                if l not in seen:
                    seen.add(l)
                    chapters_found["Full Document"].append(l)
                    if len(chapters_found["Full Document"]) >= 15:
                        break

        chapters = [{"title": k, "topics": v} for k, v in chapters_found.items()]
        return {"success": True, "filename": filename, "chapters": chapters}

    except Exception as e:
        logger.error(f"Document structure extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/classrooms/{classroom_id}/assignments")
async def create_assignment(
    classroom_id: str,
    chapter_title: str = Form(...),
    topics: str = Form("[]"),       # JSON array string
    due_date: str = Form(""),
    doc_name: str = Form(""),       # which book this assignment is from
    student_id: str = Form(""),     # empty = whole class, UUID = individual student
    current_user: User = Depends(get_current_user)
):
    """Teacher creates an assignment (chapter + topics + optional due date + optional per-student)."""
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
        if doc_name:
            assignment_data["doc_name"] = doc_name
        if student_id:
            assignment_data["student_id"] = student_id

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
            parsed_answers = _json.loads(quiz_answers) if quiz_answers else {}
            update_data["quiz_answers"] = parsed_answers

        if existing.data:
            # Update existing
            progress = existing.data[0]
            supabase.table("student_progress").update(update_data).eq("id", progress["id"]).execute()
            # Check if fully completed — quiz done = score was explicitly set (not None)
            merged = {**progress, **update_data}
            quiz_done = merged.get("quiz_score") is not None
            if merged.get("conversation_completed") and merged.get("video_completed") and quiz_done:
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


# ══════════════════════════════════════════════════════════════════════════════
# BILLING / SUBSCRIPTION ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

from billing_service import (
    PLANS,
    get_user_subscription,
    create_checkout_session,
    create_portal_session,
    handle_webhook_event,
)


class CheckoutRequest(BaseModel):
    plan: str           # pro | plus | corporate
    currency: str = "usd"   # usd | inr
    success_url: str
    cancel_url: str


class PortalRequest(BaseModel):
    return_url: str


@app.get("/api/billing/plans")
async def billing_plans():
    """Return all subscription plans with pricing."""
    plans_out = {}
    for key, p in PLANS.items():
        plans_out[key] = {
            "name": p["name"],
            "price_usd": p["price_usd"],
            "price_inr": p["price_inr"],
            "upload_limit_mb": p["upload_limit_mb"],
            "chunk_limit": p["chunk_limit"],
            "description": p["description"],
            "features": p["features"],
        }
    return {"success": True, "plans": plans_out}


@app.get("/api/billing/status")
async def billing_status(current_user: User = Depends(get_current_user)):
    """Return the calling user's current plan and limits."""
    info = get_user_subscription(current_user.id)
    plan_name = info.get("plan", "free")
    plan_config = PLANS.get(plan_name, PLANS["free"])
    # Include the new fields for frontend enforcement
    info["max_file_size_mb"] = plan_config.get("max_file_size_mb", -1)
    info["max_total_storage_mb"] = plan_config.get("max_total_storage_mb", -1)
    info["allowed_file_types"] = plan_config.get("allowed_file_types", "all")
    # Calculate current storage usage
    try:
        user_files_result = supabase.table("user_files") \
            .select("file_size") \
            .eq("user_id", current_user.id) \
            .execute()
        info["storage_used_mb"] = round(
            sum(r.get("file_size", 0) for r in (user_files_result.data or [])) / (1024 * 1024), 2
        )
    except Exception:
        info["storage_used_mb"] = 0
    return {"success": True, **info}


@app.post("/api/billing/create-checkout")
async def billing_create_checkout(
    body: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a Stripe Checkout session for a paid plan."""
    if body.plan == "free":
        # Just mark user as free in DB — no Stripe needed
        try:
            supabase.table("subscriptions").upsert(
                {"user_id": current_user.id, "plan": "free", "status": "active"},
                on_conflict="user_id"
            ).execute()
            supabase.table("profiles").update({"plan": "free"}).eq("id", current_user.id).execute()
        except Exception as e:
            logger.warning(f"Free plan save failed: {e}")
        return {"success": True, "url": body.success_url, "plan": "free"}

    if body.currency.lower() not in ("usd", "inr"):
        raise HTTPException(status_code=400, detail="Currency must be 'usd' or 'inr'")

    try:
        url = create_checkout_session(
            user_id=current_user.id,
            email=current_user.email,
            plan=body.plan,
            currency=body.currency.lower(),
            success_url=body.success_url,
            cancel_url=body.cancel_url,
        )
        return {"success": True, "url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout session creation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    """
    Stripe webhook endpoint.
    Stripe sends events here when subscriptions change.
    Register this URL in your Stripe Dashboard → Webhooks.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        result = handle_webhook_event(payload, sig_header)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/portal")
async def billing_portal(
    body: PortalRequest,
    current_user: User = Depends(get_current_user),
):
    """Return a Stripe Customer Portal URL so users can manage their subscription."""
    try:
        url = create_portal_session(current_user.id, body.return_url)
        return {"success": True, "url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Portal session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/verify-session")
async def billing_verify_session(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    After Stripe Checkout redirects back to the app, call this with the
    session_id to verify payment and update the user's plan immediately.
    This bypasses the need for a running webhook listener in local dev.
    """
    from billing_service import verify_checkout_session
    body = await request.json()
    session_id = body.get("session_id", "")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    try:
        result = verify_checkout_session(session_id, current_user.id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"verify-session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/billing/sync-subscription")
async def billing_sync_subscription(current_user: User = Depends(get_current_user)):
    """
    Sync the user's plan from their active Stripe subscription.
    Call this if payment went through on Stripe but the app still shows FREE.
    """
    from billing_service import sync_active_subscription
    try:
        result = sync_active_subscription(current_user.id)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"sync-subscription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════
# ▸  AVATAR VIDEO ENGINE  — Standalone AI video generation endpoints
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/avatar-video/generate")
async def avatar_video_generate(
    topic: str = Form(...),
    script: str = Form(""),
    doc_name: str = Form(""),
    language: str = Form("en"),
    voice: str = Form("nova"),
    avatar_id: str = Form("teacher_female_1"),
    style: str = Form("educational"),
    aspect_ratio: str = Form("16:9"),
    include_captions: bool = Form(True),
    include_broll: bool = Form(True),
    video_style: str = Form("educational_diagram"),
    video_mode: str = Form("avatar"),
    current_user: User = Depends(get_current_user),
):
    """
    Start avatar video generation (runs as a background task).
    Returns a job_id to poll for status.
    """
    from avatar_video_service import generate_avatar_video, update_job_status
    import threading
    import hashlib
    import time

    # User-provided script takes priority
    content = script.strip() if script else ""
    if not content and doc_name:
        try:
            import vectorstore as vs
            chunks = vs.vector_search(topic, doc_name=doc_name, top_k=8)
            content = "\n\n".join([c.get("text", "") for c in chunks])
        except Exception:
            pass

    # Create a unique job ID
    job_id = hashlib.md5(
        f"{current_user.id}:{topic}:{language}:{time.time()}".encode()
    ).hexdigest()[:12]

    update_job_status(job_id, status="queued", progress=0, stage="Queued for processing...")

    def _run_pipeline():
        try:
            logger.info(f"🚀 [{job_id}] Background pipeline thread started for topic='{topic}'")
            result = generate_avatar_video(
                topic=topic,
                content=content,
                user_id=current_user.id,
                avatar_id=avatar_id,
                language=language,
                voice=voice,
                style=style,
                aspect_ratio=aspect_ratio,
                include_captions=include_captions,
                include_broll=include_broll,
                job_id=job_id,
                video_style=video_style,
                video_mode=video_mode,
            )

            logger.info(f"📋 [{job_id}] Pipeline returned: status={result.get('status')}, error={result.get('error', 'none')}")

            # Update final status from result
            if result.get("status") == "completed":
                update_job_status(
                    job_id,
                    status="completed",
                    progress=100,
                    stage="Complete!",
                    video_url=result.get("video_url", ""),
                    video_path=result.get("video_path", ""),
                    scenes=result.get("scenes", []),
                    scene_timings=result.get("scene_timings", []),
                )

            # Upload to Supabase Storage if video was generated
            if result.get("status") == "completed" and result.get("video_path"):
                try:
                    video_path = result["video_path"]
                    storage_key = f"avatar-videos/{current_user.id}/{job_id}.mp4"
                    with open(video_path, "rb") as f:
                        video_bytes = f.read()
                    supabase.storage.from_("tts-cache").upload(
                        path=storage_key,
                        file=video_bytes,
                        file_options={"content-type": "video/mp4", "upsert": "true"},
                    )
                    sb_url = os.getenv("SUPABASE_URL", "")
                    video_url = f"{sb_url}/storage/v1/object/public/tts-cache/{storage_key}"
                    result["video_url"] = video_url
                    update_job_status(job_id, video_url=video_url)
                    logger.info(f"✅ [{job_id}] Avatar video uploaded: {video_url}")
                except Exception as e:
                    logger.warning(f"⚠️ [{job_id}] Avatar video upload failed: {e}")
                    # Still mark as completed — video was generated, just upload failed
                    # Serve it locally instead
                    video_path = result.get("video_path", "")
                    if video_path:
                        local_url = f"/static/avatar_video_temp/{os.path.basename(video_path)}"
                        update_job_status(job_id, video_url=local_url)
                        logger.info(f"📁 [{job_id}] Serving video locally: {local_url}")

        except Exception as e:
            import traceback
            logger.error(f"❌ [{job_id}] Avatar video pipeline CRASHED: {e}")
            logger.error(traceback.format_exc())
            update_job_status(job_id, status="failed", error=str(e))

    # Run in a background thread
    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    return {"success": True, "job_id": job_id, "status": "queued"}


@app.get("/api/avatar-video/status/{job_id}")
async def avatar_video_status(job_id: str, current_user: User = Depends(get_current_user)):
    """Poll the status of an avatar video generation job."""
    from avatar_video_service import get_job_status, WORK_DIR
    status = get_job_status(job_id)
    if status:
        return {"success": True, **status}

    # Fallback: read from .meta.json (persisted scene data survives restarts)
    import json as _json
    meta_path = WORK_DIR / f"{job_id}_final.meta.json"
    script_path = WORK_DIR / f"{job_id}_script.json"
    scene_timings = []
    scenes = []
    script_text = ""
    found = False

    # Try .meta.json first (has scene_timings with real durations)
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text())
            scene_timings = meta.get("scene_timings", [])
            scenes = meta.get("scenes", [])
            script_text = meta.get("script", "")
            found = True
        except Exception:
            pass

    # Try _script.json for scene text (always has narration even if meta is old)
    if not scenes and script_path.exists():
        try:
            sdata = _json.loads(script_path.read_text())
            scenes = sdata.get("scenes", [])
            script_text = sdata.get("script", "") or script_text
            found = True
        except Exception:
            pass

    if found:
        # Read video_mode from meta file  
        _video_mode = "presentation"
        if meta_path.exists():
            try:
                meta_data = _json.loads(meta_path.read_text())
                _video_mode = meta_data.get("video_mode", "presentation")
            except Exception:
                pass
        # Build video_url from job_id
        _video_url = f"/static/avatar_video_temp/{job_id}_final.mp4"
        return {
            "success": True,
            "status": "completed",
            "progress": 100,
            "video_url": _video_url,
            "video_mode": _video_mode,
            "scene_timings": scene_timings,
            "scenes": scenes,
            "script": script_text,
            "scene_count": len(scene_timings) or len(scenes),
        }

    raise HTTPException(status_code=404, detail="Job not found")


@app.get("/api/avatar-video/avatars")
async def avatar_video_list_avatars(current_user: User = Depends(get_current_user)):
    """List all available avatar images."""
    from avatar_video_service import list_available_avatars
    avatars = list_available_avatars()
    return {"success": True, "avatars": avatars}


@app.post("/api/avatar-video/migrate-scripts")
async def avatar_video_migrate_scripts(current_user: User = Depends(get_current_user)):
    """One-time migration: persist scene data from memory to disk for all completed jobs."""
    from avatar_video_service import _jobs, WORK_DIR
    import json as _json
    count = 0
    for jid, jdata in _jobs.items():
        if jdata.get("status") == "completed" and jdata.get("scene_timings"):
            script_path = WORK_DIR / f"{jid}_script.json"
            if not script_path.exists():
                try:
                    _json.dump({
                        "scenes": [{"narration": st.get("narration", ""), "text_overlay": st.get("text_overlay", "")}
                                   for st in jdata.get("scene_timings", [])],
                        "scene_count": jdata.get("scene_count", 0),
                    }, script_path.open("w"))
                    count += 1
                except Exception:
                    pass
            # Also update .meta.json with scene data if it exists but is missing scenes
            meta_path = WORK_DIR / f"{jid}_final.meta.json"
            if meta_path.exists():
                try:
                    meta = _json.loads(meta_path.read_text())
                    if not meta.get("scene_timings"):
                        meta["scene_timings"] = jdata.get("scene_timings", [])
                        meta["scenes"] = [{"narration": st.get("narration", ""), "text_overlay": st.get("text_overlay", "")}
                                         for st in jdata.get("scene_timings", [])]
                        meta["status"] = "completed"
                        _json.dump(meta, meta_path.open("w"))
                except Exception:
                    pass
    return {"success": True, "migrated": count, "total_jobs": len(_jobs)}

@app.post("/api/avatar-video/avatar/upload")
async def avatar_video_upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a custom avatar photo."""
    from avatar_video_service import AVATAR_DIR
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    import hashlib
    import time
    avatar_id = hashlib.md5(f"{current_user.id}:{file.filename}:{time.time()}".encode()).hexdigest()[:8]
    save_path = AVATAR_DIR / f"custom_{avatar_id}.png"

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    return {
        "success": True,
        "avatar_id": f"custom_{avatar_id}",
        "message": "Avatar uploaded successfully",
    }


@app.get("/api/avatar-video/find-by-topic")
async def avatar_video_find_by_topic(
    topic: str,
    current_user: User = Depends(get_current_user),
):
    """Find an already-generated video for a specific topic. Returns URL + scene data if found."""
    from avatar_video_service import find_video_by_topic
    result = find_video_by_topic(topic)
    if result and result.get("url"):
        return {"success": True, "has_video": True, **result}
    return {"success": True, "has_video": False}


@app.get("/api/avatar-video/list")
async def avatar_video_list(current_user: User = Depends(get_current_user)):
    """List all avatar videos generated by the current user."""
    videos = []

    # Try Supabase Storage first
    try:
        sb_url = os.getenv("SUPABASE_URL", "")
        prefix = f"avatar-videos/{current_user.id}/"
        files = supabase.storage.from_("tts-cache").list(prefix)
        for f in (files or []):
            name = f.get("name", "")
            if name.endswith(".mp4"):
                videos.append({
                    "name": name.replace(".mp4", "").replace("_", " ").title(),
                    "url": f"{sb_url}/storage/v1/object/public/tts-cache/{prefix}{name}",
                    "created_at": f.get("created_at", ""),
                    "source": "cloud",
                })
    except Exception as e:
        logger.warning(f"Supabase list failed: {e}")

    # Always also scan local files (fallback / primary for local dev)
    try:
        import pathlib
        local_dir = pathlib.Path(__file__).parent / "static" / "avatar_video_temp"
        if local_dir.exists():
            for mp4 in sorted(local_dir.glob("*_final.mp4"), key=lambda p: p.stat().st_mtime, reverse=True):
                local_url = f"/static/avatar_video_temp/{mp4.name}"
                # Avoid duplicates if already listed from Supabase
                if not any(v.get("url", "").endswith(mp4.name) for v in videos):
                    import datetime, json as _json
                    mtime = datetime.datetime.fromtimestamp(mp4.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    size_mb = mp4.stat().st_size / (1024 * 1024)
                    job_id = mp4.stem.replace("_final", "")
                    # Read topic metadata if available
                    vid_topic = ""
                    vid_mode = "presentation"
                    meta_path = mp4.parent / f"{job_id}_final.meta.json"
                    if meta_path.exists():
                        try:
                            meta = _json.loads(meta_path.read_text())
                            vid_topic = meta.get("topic", "")
                            vid_mode = meta.get("video_mode", "presentation")
                        except Exception:
                            pass
                    videos.append({
                        "name": vid_topic or f"Video {job_id[:8]}",
                        "topic": vid_topic,
                        "url": local_url,
                        "video_mode": vid_mode,
                        "created_at": mtime,
                        "size": f"{size_mb:.1f} MB",
                        "source": "local",
                    })
    except Exception as e:
        logger.warning(f"Local video scan failed: {e}")

    return {"success": True, "videos": videos}


@app.get("/api/avatar-video/dashboard")
async def avatar_video_dashboard(current_user: User = Depends(get_current_user)):
    """
    Dashboard endpoint: returns all documents with their topics,
    each annotated with video generation status (has_video, video_url).
    Also includes batch worker status for real-time progress display.
    """
    from avatar_video_service import (
        _load_topic_map, get_batch_worker_status, WORK_DIR
    )

    # 1. Get all topics from lesson_cache grouped by document
    documents = {}  # doc_name -> { topics: [...], ... }
    try:
        result = supabase.table("lesson_cache").select("doc_name, lesson_json, topic") \
            .eq("lesson_type", "topics").execute()
        for row in (result.data or []):
            doc_name = row.get("doc_name", "Unknown")
            lesson_json = row.get("lesson_json", {})
            if isinstance(lesson_json, str):
                import json as _j
                try:
                    lesson_json = _j.loads(lesson_json)
                except Exception:
                    continue
            topics_list = lesson_json.get("topics", [])
            if doc_name not in documents:
                documents[doc_name] = {"doc_name": doc_name, "topics": []}
            for t in topics_list:
                if isinstance(t, dict):
                    title = t.get("title") or t.get("name") or ""
                    desc = t.get("description", "")
                    difficulty = t.get("difficulty", "")
                    key_concepts = t.get("key_concepts", [])
                else:
                    title = str(t)
                    desc = ""
                    difficulty = ""
                    key_concepts = []
                if title.strip():
                    # Skip duplicate topics within same document
                    existing_titles = [tp["title"].lower() for tp in documents[doc_name]["topics"]]
                    if title.strip().lower() not in existing_titles:
                        documents[doc_name]["topics"].append({
                            "title": title.strip(),
                            "description": desc,
                            "difficulty": difficulty,
                            "key_concepts": key_concepts,
                        })
    except Exception as e:
        logger.warning(f"Dashboard: lesson_cache query failed: {e}")

    # 2. Load video topic map and check which topics have videos
    topic_map = _load_topic_map()
    total_topics = 0
    total_with_video = 0

    for doc_name, doc_data in documents.items():
        for topic_entry in doc_data["topics"]:
            total_topics += 1
            key = topic_entry["title"].strip().lower()
            if key in topic_map:
                entry = topic_map[key]
                video_file = entry.get("filename", "")
                if video_file and (WORK_DIR / video_file).exists():
                    topic_entry["has_video"] = True
                    topic_entry["video_url"] = f"/static/avatar_video_temp/{video_file}"
                    topic_entry["video_mode"] = entry.get("video_mode", "presentation")
                    total_with_video += 1
                else:
                    topic_entry["has_video"] = False
                    topic_entry["video_url"] = None
            else:
                topic_entry["has_video"] = False
                topic_entry["video_url"] = None

    # 3. Get batch worker status
    batch_status = get_batch_worker_status()

    # 4. Sort documents by name
    doc_list = sorted(documents.values(), key=lambda d: d["doc_name"])

    return {
        "success": True,
        "documents": doc_list,
        "summary": {
            "total_documents": len(doc_list),
            "total_topics": total_topics,
            "topics_with_video": total_with_video,
            "topics_without_video": total_topics - total_with_video,
            "completion_percent": round((total_with_video / total_topics * 100) if total_topics > 0 else 0, 1),
        },
        "batch_status": batch_status,
    }


# ═══════════════════════════════════════════════════════════════════════
# ▸  BATCH VIDEO PRE-GENERATION — Auto-generate videos for all topics
# ═══════════════════════════════════════════════════════════════════════

_batch_video_thread = None  # Track the background thread


def _discover_all_topics_from_db() -> list:
    """
    Discover all unique topic titles from Supabase lesson_cache
    (lesson_type = 'topics') so we know what content exists.
    """
    all_topics = set()
    try:
        # Query lesson_cache for all 'topics' entries
        result = supabase.table("lesson_cache").select("lesson_json") \
            .eq("lesson_type", "topics").execute()
        for row in (result.data or []):
            lesson_json = row.get("lesson_json", {})
            if isinstance(lesson_json, str):
                import json as _j
                try:
                    lesson_json = _j.loads(lesson_json)
                except Exception:
                    continue
            topics_list = lesson_json.get("topics", [])
            for t in topics_list:
                if isinstance(t, dict):
                    title = t.get("title") or t.get("name") or ""
                else:
                    title = str(t)
                if title.strip():
                    all_topics.add(title.strip())
    except Exception as e:
        logger.warning(f"Could not discover topics from DB: {e}")

    return list(all_topics)


@app.post("/api/avatar-video/batch-generate")
async def avatar_video_batch_generate(
    current_user: User = Depends(get_current_user),
):
    """
    Start batch generation of avatar videos for ALL topics that don't have videos.
    Runs in a background thread. Returns immediately with status.
    """
    global _batch_video_thread
    from avatar_video_service import (
        batch_generate_videos, get_batch_worker_status,
        get_all_topics_without_videos
    )
    import threading

    status = get_batch_worker_status()
    if status.get("running"):
        return {
            "success": False,
            "message": "Batch worker is already running",
            "status": status,
        }

    # Discover topics from DB + local files
    db_topics = _discover_all_topics_from_db()
    local_missing = get_all_topics_without_videos()

    # Combine: all DB topics + locally-discovered topics
    all_topic_set = set(t.strip().lower() for t in db_topics)
    all_topic_set.update(t.strip().lower() for t in local_missing)

    # Check which ones need videos (using the service function)
    from avatar_video_service import _load_topic_map, WORK_DIR
    existing = _load_topic_map()
    topics_to_generate = []
    for topic in sorted(all_topic_set):
        if topic in existing:
            entry = existing[topic]
            video_file = entry.get("filename", "")
            if video_file and (WORK_DIR / video_file).exists():
                continue
        # Find the original-case version
        original = next((t for t in db_topics if t.strip().lower() == topic), None)
        if not original:
            original = next((t for t in local_missing if t.strip().lower() == topic), None)
        topics_to_generate.append(original or topic)

    if not topics_to_generate:
        return {
            "success": True,
            "message": "All topics already have avatar videos!",
            "total_topics": len(all_topic_set),
            "videos_exist": len(all_topic_set),
        }

    def _run_batch():
        batch_generate_videos(
            topics=topics_to_generate,
            user_id=current_user.id,
            voice="nova",
            avatar_id="teacher_female_1",
            video_mode="presentation",
        )

    _batch_video_thread = threading.Thread(target=_run_batch, daemon=True)
    _batch_video_thread.start()

    return {
        "success": True,
        "message": f"Batch generation started for {len(topics_to_generate)} topics",
        "topics": topics_to_generate,
        "total_topics": len(all_topic_set),
        "already_exist": len(all_topic_set) - len(topics_to_generate),
    }


@app.get("/api/avatar-video/batch-status")
async def avatar_video_batch_status(current_user: User = Depends(get_current_user)):
    """Get the current status of the batch video generation worker."""
    from avatar_video_service import get_batch_worker_status, get_all_topics_without_videos
    status = get_batch_worker_status()
    status["pending_topics"] = len(get_all_topics_without_videos())
    return {"success": True, **status}


@app.post("/api/avatar-video/batch-cancel")
async def avatar_video_batch_cancel(current_user: User = Depends(get_current_user)):
    """Cancel the running batch video generation worker.
    Sets persistent user_cancelled flag — batch will NOT auto-restart."""
    from avatar_video_service import cancel_batch_worker, get_batch_worker_status
    cancel_batch_worker()  # Always set the persistent flag, even if not running
    updated = get_batch_worker_status()
    return {
        "success": True,
        "message": "Batch cancelled — will NOT auto-restart until you click Resume",
        "status": updated,
    }


@app.post("/api/avatar-video/batch-resume")
async def avatar_video_batch_resume(current_user: User = Depends(get_current_user)):
    """Clear the persistent user_cancelled flag and restart batch generation."""
    from avatar_video_service import (
        resume_batch_worker, get_batch_worker_status,
        batch_generate_videos, get_all_topics_without_videos,
        _load_topic_map, WORK_DIR,
    )

    # Clear persistent cancel flag
    resume_batch_worker()

    status = get_batch_worker_status()
    if status.get("running"):
        return {"success": True, "message": "Batch is already running"}

    # Discover topics and start batch
    db_topics = _discover_all_topics_from_db()
    local_missing = get_all_topics_without_videos()
    all_topic_set = set(t.strip().lower() for t in db_topics)
    all_topic_set.update(t.strip().lower() for t in local_missing)

    existing = _load_topic_map()
    topics_to_generate = []
    for topic_key in sorted(all_topic_set):
        if topic_key in existing:
            entry = existing[topic_key]
            video_file = entry.get("filename", "")
            if video_file and (WORK_DIR / video_file).exists():
                continue
        original = next((t for t in db_topics if t.strip().lower() == topic_key), None)
        if not original:
            original = next((t for t in local_missing if t.strip().lower() == topic_key), None)
        topics_to_generate.append(original or topic_key)

    if not topics_to_generate:
        return {"success": True, "message": "All topics already have videos"}

    import threading
    def _run():
        batch_generate_videos(
            topics=topics_to_generate,
            user_id=str(current_user.id),
            voice="nova",
            avatar_id="teacher_female_1",
            video_mode="presentation",
        )

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    return {
        "success": True,
        "message": f"Batch resumed — generating {len(topics_to_generate)} topics",
        "topics_count": len(topics_to_generate),
    }


@app.get("/api/avatar-video/topics-without-videos")
async def avatar_video_topics_without_videos(current_user: User = Depends(get_current_user)):
    """List all topics that don't have avatar videos yet."""
    from avatar_video_service import get_all_topics_without_videos, _load_topic_map
    missing = get_all_topics_without_videos()
    db_topics = _discover_all_topics_from_db()
    existing_map = _load_topic_map()
    return {
        "success": True,
        "topics_without_videos": missing,
        "total_topics_discovered": len(set(t.strip().lower() for t in db_topics) |
                                       set(t.strip().lower() for t in missing) |
                                       set(existing_map.keys())),
        "videos_exist": len(existing_map),
        "videos_missing": len(missing),
    }


# ── Auto-start background video pre-generation on server startup ──
_auto_batch_task = None


async def _auto_batch_video_scheduler():
    """
    Background scheduler that automatically generates videos for topics
    that don't have them yet. Runs every 5 minutes when idle.
    Respects the persistent user_cancelled flag — will NOT auto-start if the user cancelled.
    """
    import asyncio
    import threading

    # Wait 60 seconds after startup to let the server stabilize
    await asyncio.sleep(60)
    logger.info("🔄 Auto batch video scheduler started (checks every 5 min)")

    while True:
        try:
            from avatar_video_service import (
                get_batch_worker_status, batch_generate_videos,
                get_all_topics_without_videos, _load_topic_map, WORK_DIR,
                _load_batch_control,
            )

            # Check persistent user_cancelled flag FIRST
            control = _load_batch_control()
            if control.get("user_cancelled", False):
                logger.debug("⏸️ User cancelled batch — auto-scheduler will not start. Waiting for resume.")
                await asyncio.sleep(300)
                continue

            status = get_batch_worker_status()
            if status.get("running"):
                logger.debug("⏳ Batch worker already running, skipping auto-check")
                await asyncio.sleep(300)
                continue

            # Discover all topics
            db_topics = _discover_all_topics_from_db()
            local_missing = get_all_topics_without_videos()

            all_topic_set = set(t.strip().lower() for t in db_topics)
            all_topic_set.update(t.strip().lower() for t in local_missing)

            existing = _load_topic_map()
            topics_to_generate = []
            for topic_key in sorted(all_topic_set):
                if topic_key in existing:
                    entry = existing[topic_key]
                    video_file = entry.get("filename", "")
                    if video_file and (WORK_DIR / video_file).exists():
                        continue
                original = next((t for t in db_topics if t.strip().lower() == topic_key), None)
                if not original:
                    original = next((t for t in local_missing if t.strip().lower() == topic_key), None)
                topics_to_generate.append(original or topic_key)

            if topics_to_generate:
                logger.info(
                    f"🎬 Auto-batch: {len(topics_to_generate)} topics need videos — starting generation"
                )

                def _run():
                    batch_generate_videos(
                        topics=topics_to_generate,
                        user_id="system",
                        voice="nova",
                        avatar_id="teacher_female_1",
                        video_mode="presentation",
                    )

                t = threading.Thread(target=_run, daemon=True)
                t.start()

                # Wait for batch to finish before next check
                while t.is_alive():
                    await asyncio.sleep(10)
            else:
                logger.debug("✅ All topics have videos — nothing to generate")

        except Exception as e:
            logger.error(f"Auto-batch scheduler error: {e}")

        # Wait 5 minutes before next check
        await asyncio.sleep(300)

