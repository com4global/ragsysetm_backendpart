"""
HeyGen Video Generation Service
Generates AI teaching videos from document content.

Pipeline (Individual Learner — synchronous, w/ Supabase persistence):
  1. Check Supabase `ai_videos` table — return instantly if cached
  2. PDF chunks (from Pinecone) → LLM generates a teaching script
  3. Script → HeyGen Video Agent API → video_id
  4. Poll HeyGen until done → video_url (mp4)
  5. Persist to Supabase so the same topic is NEVER regenerated across restarts

Uses v1/video_agent/generate for fastest text-to-video path.
"""

import os
import json
import time
import logging
import hashlib
import requests
from typing import Optional, Dict
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────
HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY", "")
HEYGEN_BASE_URL = "https://api.heygen.com"
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

logger = logging.getLogger(__name__)

# ── Video Cache (JSON file — fallback when Supabase unavailable) ────
CACHE_DIR = Path("/tmp") if os.name != "nt" else Path(os.environ.get("TEMP", "."))
CACHE_FILE = CACHE_DIR / "heygen_video_cache.json"


# ═══════════════════════════════════════════════════════════════════
# ▸ Supabase Persistent Video Cache — ai_videos table
# ═══════════════════════════════════════════════════════════════════

def _heygen_cache_key(topic: str, doc_name: str, language: str) -> str:
    """Cache key shared across ALL users — same topic/doc/language = same video."""
    raw = f"{topic.strip().lower()}|{doc_name.strip().lower()}|{language.strip().lower()}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_supabase_cached_video(topic: str, doc_name: str, language: str) -> Optional[Dict]:
    """
    Check Supabase ai_videos table for an already-generated video.
    Returns the row dict (with video_url) or None.
    """
    try:
        from database import get_supabase_client
        sb = get_supabase_client()
        key = _heygen_cache_key(topic, doc_name, language)
        result = sb.table("ai_videos").select("*").eq("cache_key", key).eq("status", "completed").limit(1).execute()
        if result.data:
            logger.info(f"🎯 Supabase ai_videos cache HIT: {topic}")
            return result.data[0]
    except Exception as e:
        logger.warning(f"Supabase video cache lookup failed (non-fatal): {e}")
    return None


def save_supabase_video(topic: str, doc_name: str, language: str, video_id: str,
                        video_url: str, thumbnail_url: str = "", script: str = "",
                        presenter: str = "") -> None:
    """Upsert a completed video into Supabase ai_videos for permanent caching."""
    try:
        from database import get_supabase_client
        sb = get_supabase_client()
        key = _heygen_cache_key(topic, doc_name, language)
        sb.table("ai_videos").upsert({
            "cache_key": key,
            "topic": topic,
            "doc_name": doc_name,
            "language": language,
            "video_id": video_id,
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "script": script[:500],
            "presenter": presenter,
            "status": "completed",
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, on_conflict="cache_key").execute()
        logger.info(f"✅ Supabase ai_videos saved: {topic} → {video_url[:60]}...")
    except Exception as e:
        logger.warning(f"Supabase video cache save failed (non-fatal): {e}")


# ═══════════════════════════════════════════════════════════════════
# ▸ HeyGen Synchronous Pipeline (for Individual Learner role)
# ═══════════════════════════════════════════════════════════════════

def poll_heygen_video(video_id: str, max_wait: int = 300, interval: int = 5) -> Dict:
    """
    Poll HeyGen v1/video_status.get until status is 'completed' or 'failed'.
    Returns the full status dict including video_url when ready.
    Raises TimeoutError if max_wait (seconds) is exceeded.
    """
    if not HEYGEN_API_KEY:
        raise ValueError("HEYGEN_API_KEY not configured")

    headers = {"X-Api-Key": HEYGEN_API_KEY, "Accept": "application/json"}
    deadline = time.time() + max_wait

    while time.time() < deadline:
        resp = requests.get(
            f"{HEYGEN_BASE_URL}/v1/video_status.get",
            headers=headers,
            params={"video_id": video_id},
            timeout=15,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"HeyGen status check failed ({resp.status_code}): {resp.text[:200]}")

        data = resp.json().get("data", {})
        status = data.get("status", "")
        logger.info(f"🔄 HeyGen poll {video_id}: status={status}")

        if status == "completed":
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"HeyGen video failed: {data.get('error', 'unknown error')}")

        time.sleep(interval)

    raise TimeoutError(f"HeyGen video {video_id} did not finish within {max_wait}s")


def generate_heygen_video_sync(script: str, topic: str, doc_name: str = "",
                               language: str = "en") -> Dict:
    """
    Full synchronous pipeline for Individual Learner role:
      1. Check Supabase cache → return immediately if already generated
      2. Submit to HeyGen video agent
      3. Poll until completed (up to 5 minutes)
      4. Save to Supabase for permanent caching
      5. Return {video_url, video_id, presenter, cached}

    This runs in a thread pool (asyncio.run_in_executor) from main.py.
    """
    if not HEYGEN_API_KEY:
        raise ValueError("HEYGEN_API_KEY environment variable is not set.")

    # ── 1. Check Supabase cache ──
    cached = get_supabase_cached_video(topic, doc_name, language)
    if cached and cached.get("video_url"):
        return {
            "video_url": cached["video_url"],
            "video_id": cached.get("video_id", ""),
            "thumbnail_url": cached.get("thumbnail_url", ""),
            "presenter": cached.get("presenter", "HeyGen Avatar"),
            "cached": True,
        }

    # ── 2. Check file-based fallback cache ──
    file_cache = _load_cache()
    file_key = _heygen_cache_key(topic, doc_name, language)
    if file_key in file_cache and file_cache[file_key].get("video_url"):
        entry = file_cache[file_key]
        # Promote to Supabase
        save_supabase_video(
            topic, doc_name, language,
            entry.get("video_id", ""), entry["video_url"],
            entry.get("thumbnail_url", ""), script
        )
        return {
            "video_url": entry["video_url"],
            "video_id": entry.get("video_id", ""),
            "presenter": "HeyGen Avatar",
            "cached": True,
        }

    # ── 3. Submit to HeyGen v2/video/generate (uses subscription minutes, not API credits) ──
    # v1/video_agent costs API credits → 402. v2/video/generate uses plan video minutes.
    script_truncated = script[:1500].strip()  # ~90-120 seconds of speech

    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Pick avatar + voice — IDs verified against /v2/voices on this account
    # Female: M2WosQ2Ju3f2b7jdddsj  |  Male fallback: a50b2b18a4bf49109caf46a3a6c6a08a
    avatar_id = "Anna_public_3_20240108"   # Professional female educator preset
    voice_id = "M2WosQ2Ju3f2b7jdddsj"     # en female (verified from /v2/voices)
    _ = language  # reserved for future multilingual support

    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": script_truncated,
                    "voice_id": voice_id,
                    "speed": 1.0,
                },
                "background": {
                    "type": "color",
                    "value": "#f0f4f8",
                },
            }
        ],
        "aspect_ratio": "16:9",
        "test": False,
    }

    logger.info(f"🎬 HeyGen v2: submitting video for '{topic}' ({len(script_truncated)} chars)")
    resp = requests.post(
        f"{HEYGEN_BASE_URL}/v2/video/generate",
        json=payload, headers=headers, timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"HeyGen API error ({resp.status_code}): {resp.text[:400]}")

    resp_data = resp.json()
    video_id = (
        resp_data.get("data", {}).get("video_id")
        or resp_data.get("video_id")
    )
    if not video_id:
        raise RuntimeError(f"HeyGen v2 returned no video_id: {resp_data}")

    logger.info(f"✅ HeyGen v2 video submitted: {video_id}")


    # ── 4. Poll until done ──
    result = poll_heygen_video(video_id, max_wait=300, interval=5)
    video_url = result.get("video_url", "")
    thumbnail_url = result.get("thumbnail_url", "")

    if not video_url:
        raise RuntimeError("HeyGen returned no video_url after completion")

    # ── 5. Persist to Supabase + file cache ──
    save_supabase_video(topic, doc_name, language, video_id, video_url, thumbnail_url, script)

    file_cache[file_key] = {
        "video_id": video_id, "video_url": video_url,
        "thumbnail_url": thumbnail_url, "topic": topic,
        "doc_name": doc_name, "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_cache(file_cache)

    logger.info(f"✅ HeyGen video ready: {video_url}")
    return {
        "video_url": video_url,
        "video_id": video_id,
        "thumbnail_url": thumbnail_url,
        "presenter": "HeyGen Avatar",
        "cached": False,
    }




def _load_cache() -> Dict:
    """Load the video cache from disk."""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Cache load failed: {e}")
    return {}


def _save_cache(cache: Dict):
    """Persist the video cache to disk."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")


def _cache_key(user_id: str, doc_name: str, topic: str, language: str = "en") -> str:
    """Generate a deterministic cache key for a video (language-aware)."""
    raw = f"{user_id}|{doc_name}|{topic}|{language}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


# ── Step 1: Script Generation ───────────────────────────────────────

def generate_teaching_script(
    topic: str,
    content: str,
    language: str = "en"
) -> str:
    """
    Use LLM to craft a narration script for a teaching video.
    The script is a monologue suitable for a single AI avatar speaker.
    
    Args:
        topic:    The topic title to teach
        content:  Relevant document chunks (from Pinecone)
        language: 'en' or 'ta'
    
    Returns:
        A narration script string (plain text, 1-3 minutes when spoken)
    """
    lang_instruction = ""
    if language == "ta":
        lang_instruction = "\nIMPORTANT: Write the ENTIRE script in Tamil (தமிழ்). Use simple, conversational Tamil."

    prompt = f"""You are an expert educational content scriptwriter. 
Create a clear, engaging VIDEO NARRATION SCRIPT for a teaching video about the topic below.

TOPIC: {topic}

REFERENCE CONTENT (from the student's textbook):
{content[:8000]}

SCRIPT RULES:
1. Write a MONOLOGUE — one teacher speaking directly to the student.
2. The script MUST be based ONLY on the reference content above. Do NOT invent facts.
3. Start with a warm greeting and topic introduction.
4. Explain the key concepts step by step, using simple language.
5. Use real-world analogies to make complex ideas accessible.
6. Include 1-2 "Did you know?" moments to keep it interesting.
7. End with a brief summary of the key takeaways.
8. Target length: 1-2 minutes of spoken content (approximately 150-300 words).
9. Do NOT include stage directions, camera cues, or visual descriptions.
10. Write in a natural, conversational tone — as if talking face-to-face with a student.
{lang_instruction}

Write the script now (plain text, no formatting markers):"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write concise, engaging educational video scripts. "
                        "Your scripts are based strictly on provided document content. "
                        "You speak naturally, as a friendly teacher."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=1000
        )
        script = response.choices[0].message.content.strip()
        logger.info(f"✅ Teaching script generated: {len(script)} chars for topic '{topic}'")
        return script

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        raise RuntimeError(f"Failed to generate teaching script: {e}")


# ── Step 2: HeyGen Video Creation ───────────────────────────────────

def create_heygen_video(script: str, title: str = "AI Teacher Lesson") -> Dict:
    """
    Send a teaching script to HeyGen's Video Agent API to generate a video.
    
    This uses the simplest endpoint:
      POST https://api.heygen.com/v1/video_agent/generate
    
    Args:
        script: The narration text for the video
        title:  Video title for reference
    
    Returns:
        Dict with 'video_id' on success, or 'error' on failure
    """
    if not HEYGEN_API_KEY:
        return {"error": "HEYGEN_API_KEY is not configured. Add it to your .env file."}

    url = f"{HEYGEN_BASE_URL}/v1/video_agent/generate"
    
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # The Video Agent accepts a simple prompt
    # It automatically selects an avatar and voice
    payload = {
        "prompt": (
            f"Create a professional educational video for the topic: {title}. "
            f"The teacher should explain the following content clearly and engagingly:\n\n"
            f"{script}"
        )
    }

    try:
        logger.info(f"🎬 Sending video generation request to HeyGen for: '{title}'")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        logger.info(f"HeyGen response status: {response.status_code}")
        logger.info(f"HeyGen response body: {response.text[:500]}")

        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            # HeyGen may return the video_id in different structures
            video_id = (
                data.get("data", {}).get("video_id") or
                data.get("video_id") or
                data.get("data", {}).get("id")
            )
            if video_id:
                logger.info(f"✅ HeyGen video created: video_id={video_id}")
                return {"video_id": video_id, "status": "processing"}
            else:
                logger.error(f"HeyGen response missing video_id: {data}")
                return {"error": f"Unexpected HeyGen response: {data}"}
        else:
            error_msg = response.text[:300]
            logger.error(f"HeyGen API error ({response.status_code}): {error_msg}")
            return {"error": f"HeyGen API error ({response.status_code}): {error_msg}"}

    except requests.Timeout:
        logger.error("HeyGen API request timed out")
        return {"error": "HeyGen API request timed out. Please try again."}
    except Exception as e:
        logger.error(f"HeyGen API call failed: {e}")
        return {"error": f"HeyGen API call failed: {str(e)}"}


# ── Step 3: Check Video Status ──────────────────────────────────────

def check_video_status(video_id: str) -> Dict:
    """
    Poll HeyGen to check if a video has finished rendering.
    
    Returns:
        Dict with keys: status, video_url (if completed), error (if failed)
        Possible statuses: 'processing', 'completed', 'failed'
    """
    if not HEYGEN_API_KEY:
        return {"status": "failed", "error": "HEYGEN_API_KEY not configured"}

    url = f"{HEYGEN_BASE_URL}/v1/video_status.get"
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Accept": "application/json"
    }
    params = {"video_id": video_id}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            video_data = data.get("data", {})
            status = video_data.get("status", "unknown")
            
            result = {"status": status, "video_id": video_id}
            
            if status == "completed":
                video_url = video_data.get("video_url", "")
                result["video_url"] = video_url
                result["duration"] = video_data.get("duration")
                result["thumbnail_url"] = video_data.get("thumbnail_url")
                logger.info(f"✅ Video completed: {video_url[:80]}...")
                
            elif status == "failed":
                result["error"] = video_data.get("error", "Video generation failed")
                logger.error(f"❌ Video failed: {result['error']}")
                
            else:
                logger.info(f"⏳ Video still processing: {video_id} (status={status})")
            
            return result
        else:
            logger.error(f"Status check failed ({response.status_code}): {response.text[:200]}")
            return {
                "status": "error",
                "error": f"Status check failed ({response.status_code})"
            }

    except Exception as e:
        logger.error(f"Video status check failed: {e}")
        return {"status": "error", "error": str(e)}


# ── Step 4: Full Pipeline (with caching) ────────────────────────────

def generate_video_for_topic(
    topic: str,
    content: str,
    user_id: str,
    doc_name: str = "",
    language: str = "en"
) -> Dict:
    """
    Full pipeline: check cache → generate script → call HeyGen → return result.
    
    This does NOT wait for video completion (that's async).
    The frontend will poll /api/edtech/video-status for updates.
    
    Args:
        topic:      Topic title
        content:    Relevant document chunks text
        user_id:    Current user ID
        doc_name:   Source document name
        language:   'en' or 'ta'
    
    Returns:
        Dict with video_id, status, and optionally video_url (if cached)
    """
    # ── Check cache first ──
    key = _cache_key(user_id, doc_name, topic)
    cache = _load_cache()
    
    if key in cache:
        cached = cache[key]
        # If we have a completed video URL, return it immediately
        if cached.get("video_url"):
            logger.info(f"🎯 Cache hit for topic '{topic}' → {cached['video_url'][:60]}...")
            return {
                "status": "completed",
                "video_url": cached["video_url"],
                "video_id": cached.get("video_id", ""),
                "cached": True,
                "thumbnail_url": cached.get("thumbnail_url", "")
            }
        
        # If we have a video_id but no URL yet, it might still be processing
        if cached.get("video_id"):
            logger.info(f"⏳ Cache has pending video_id for '{topic}': {cached['video_id']}")
            return {
                "status": "processing",
                "video_id": cached["video_id"],
                "cached": True
            }

    # ── Generate teaching script ──
    logger.info(f"📝 Generating teaching script for: '{topic}'")
    script = generate_teaching_script(topic, content, language)
    
    if not script:
        return {"status": "failed", "error": "Failed to generate teaching script"}

    # ── Call HeyGen API ──
    result = create_heygen_video(script, title=topic)
    
    if "error" in result:
        return {"status": "failed", "error": result["error"], "script": script}

    video_id = result.get("video_id", "")
    
    # ── Save to cache (pending state) ──
    cache[key] = {
        "video_id": video_id,
        "topic": topic,
        "doc_name": doc_name,
        "user_id": user_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "script": script[:500],  # Save partial script for reference
        "video_url": None
    }
    _save_cache(cache)

    return {
        "status": "processing",
        "video_id": video_id,
        "message": "Video is being generated. This typically takes 2-5 minutes."
    }


def update_video_cache(user_id: str, doc_name: str, topic: str, video_url: str, 
                       video_id: str = "", thumbnail_url: str = ""):
    """
    Update the cache with a completed video URL.
    Called after polling confirms the video is ready.
    """
    key = _cache_key(user_id, doc_name, topic)
    cache = _load_cache()
    
    if key in cache:
        cache[key]["video_url"] = video_url
        cache[key]["video_id"] = video_id
        cache[key]["thumbnail_url"] = thumbnail_url
        cache[key]["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        cache[key] = {
            "video_id": video_id,
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "topic": topic,
            "doc_name": doc_name,
            "user_id": user_id,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    
    _save_cache(cache)
    logger.info(f"✅ Cache updated for topic '{topic}' → {video_url[:60]}...")


def get_cached_video(user_id: str, doc_name: str, topic: str) -> Optional[Dict]:
    """
    Check if a completed video exists in cache for this topic.
    Returns the cached entry or None.
    """
    key = _cache_key(user_id, doc_name, topic)
    cache = _load_cache()
    entry = cache.get(key)
    
    if entry and entry.get("video_url"):
        return entry
    return None


# ══════════════════════════════════════════════════════════════════════
# OPENAI TTS — Self-hosted alternative to HeyGen
# ══════════════════════════════════════════════════════════════════════

import re

# Directory for cached TTS audio files
# On production (Linux), the app dir is read-only — use /tmp instead
if os.name == "nt":
    TTS_AUDIO_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "static" / "tts_audio"
else:
    TTS_AUDIO_DIR = Path("/tmp") / "tts_audio"
TTS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# TTS Cache file (separate from HeyGen cache)
TTS_CACHE_FILE = CACHE_DIR / "tts_audio_cache.json"


def _load_tts_cache() -> Dict:
    try:
        if TTS_CACHE_FILE.exists():
            with open(TTS_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"TTS cache load failed: {e}")
    return {}


def _save_tts_cache(cache: Dict):
    try:
        TTS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TTS_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.warning(f"TTS cache save failed: {e}")


def _split_into_sentences(text: str) -> list:
    """
    Split script text into sentences for subtitle synchronization.
    Returns a list of sentence strings.
    """
    # Split on sentence-ending punctuation, keeping the punctuation
    raw = re.split(r'(?<=[.!?])\s+', text.strip())
    # Filter out empty strings and strip whitespace
    sentences = [s.strip() for s in raw if s.strip()]
    return sentences


def generate_sarvam_tts(text: str, audio_path: Path, language: str = "ta") -> None:
    """
    Generate Tamil TTS audio using Sarvam AI bulbul:v3.
    v3 accepts long-form text in a single request — no chunking needed.
    Returns WAV audio as base64.
    """
    if not SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY not set in environment")

    import base64, io, wave, shutil

    # Sarvam v3 REST API — correct payload format
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    # ── Text chunking ──
    # Sarvam bulbul:v2 silently truncates requests over ~450 characters.
    # The comment about "2000 chars" was wrong (that was for an older v3 doc).
    # Safe limit: 400 characters per API call.
    # We split on sentence boundaries (। . ! ?) so sentences aren't cut mid-word.
    CHUNK_SIZE = 400

    import re as _re
    # Split into sentences first
    sentence_list = _re.split(r'(?<=[.!?।])\s+', text.strip())
    sentence_list = [s.strip() for s in sentence_list if s.strip()]

    chunks = []
    current_chunk = ""
    for sentence in sentence_list:
        # If a single sentence exceeds CHUNK_SIZE, break it by words
        if len(sentence) > CHUNK_SIZE:
            words = sentence.split()
            for word in words:
                if len(current_chunk) + len(word) + 1 > CHUNK_SIZE:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = word
                else:
                    current_chunk = (current_chunk + " " + word).strip()
        else:
            if len(current_chunk) + len(sentence) + 1 > CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk:
        chunks.append(current_chunk.strip())

    logger.info(f"🔢 Sarvam TTS: splitting {len(text)} chars into {len(chunks)} chunks of ≤{CHUNK_SIZE} chars")
    for i, ch in enumerate(chunks):
        logger.info(f"   Chunk {i+1}/{len(chunks)}: {len(ch)} chars — '{ch[:60]}...'")


    audio_segments = []

    # Pick a random Tamil female speaker for this call (varies per lesson/Q&A)
    import random as _rnd
    _TAMIL_SPEAKERS = ["anushka", "manisha", "vidya", "arya"]
    chosen_speaker = _rnd.choice(_TAMIL_SPEAKERS)
    logger.info(f"🎙️ Sarvam TTS speaker: {chosen_speaker}")

    for chunk in chunks:
        # ── Correct payload for bulbul:v2 ──
        # bulbul:v2 uses "text" (string) + target_language_code
        # bulbul:v1 would need "inputs": [text] — different format entirely
        payload = {
            "text": chunk,
            "target_language_code": "ta-IN",
            "speaker": chosen_speaker,         # Random Tamil female voice, chosen once per call
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2"               # ← MUST be v2 for text field + these speakers
        }

        try:
            resp = requests.post(SARVAM_TTS_URL, json=payload, headers=headers, timeout=30)
            if not resp.ok:
                # Log the error body for easier debugging
                logger.error(f"Sarvam TTS error {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()

            data = resp.json()
            audio_b64 = data.get("audios", [None])[0]
            if audio_b64:
                audio_segments.append(base64.b64decode(audio_b64))
        except Exception as e:
            logger.error(f"Sarvam TTS chunk failed: {e}")
            raise


    if not audio_segments:
        raise RuntimeError("Sarvam TTS returned no audio")

    # Merge WAV chunks into a single file
    merged_frames = b""
    first_params = None
    for seg in audio_segments:
        with wave.open(io.BytesIO(seg), 'rb') as wf:
            if first_params is None:
                first_params = wf.getparams()
            merged_frames += wf.readframes(wf.getnframes())

    if not first_params:
        raise RuntimeError("Sarvam TTS: no valid WAV params from audio chunks")

    wav_path = audio_path.with_suffix(".wav")
    with wave.open(str(wav_path), 'wb') as out:
        out.setparams(first_params)
        out.writeframes(merged_frames)

    # Convert WAV → MP3 using pydub if available, else keep WAV (browsers handle it fine)
    try:
        from pydub import AudioSegment
        AudioSegment.from_wav(str(wav_path)).export(str(audio_path), format="mp3", bitrate="128k")
        wav_path.unlink(missing_ok=True)
        logger.info(f"✅ Sarvam Tamil TTS saved (MP3): {audio_path}")
    except Exception:
        shutil.move(str(wav_path), str(audio_path))
        logger.info(f"✅ Sarvam Tamil TTS saved (WAV renamed to MP3): {audio_path}")



def generate_tts_audio(
    script: str,
    topic: str,
    user_id: str = "",
    doc_name: str = "",
    voice: str = "nova",
    language: str = "en"
) -> Dict:
    """
    Generate TTS audio from a teaching script using OpenAI's TTS API.
    
    Args:
        script:   The narration text
        topic:    Topic title (for caching)
        user_id:  User ID (for caching)
        doc_name: Document name (for caching)
        voice:    OpenAI TTS voice — 'alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'
    
    Returns:
        Dict with: audio_filename, sentences[], script, duration_estimate
    """
    # ── Check TTS cache ──
    cache_key = _cache_key(user_id, doc_name, topic, language)
    tts_cache = _load_tts_cache()
    
    if cache_key in tts_cache:
        cached = tts_cache[cache_key]
        audio_path = TTS_AUDIO_DIR / cached.get("audio_filename", "")
        if audio_path.exists():
            logger.info(f"🎯 TTS cache hit for '{topic}'")
            return cached
    
    # ── Generate audio ──
    audio_filename = f"tts_{cache_key}.mp3"
    audio_path = TTS_AUDIO_DIR / audio_filename

    try:
        if language == "ta" and SARVAM_API_KEY:
            # ── Sarvam AI — natural Tamil teacher voice ──
            logger.info(f"🔊 Generating Tamil TTS via Sarvam AI for: '{topic}'")
            generate_sarvam_tts(script, audio_path, language="ta")
        else:
            # ── OpenAI TTS — English and other languages ──
            logger.info(f"🔊 Generating TTS audio for: '{topic}' (voice={voice})")
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=script,
                response_format="mp3"
            )
            response.stream_to_file(str(audio_path))

        logger.info(f"✅ TTS audio saved: {audio_path} ({audio_path.stat().st_size} bytes)")

    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise RuntimeError(f"Failed to generate TTS audio: {e}")
    
    # ── Split script into sentences for subtitle sync ──
    sentences = _split_into_sentences(script)
    
    # Estimate duration: ~150 words per minute for TTS
    word_count = len(script.split())
    duration_estimate = max(10, int((word_count / 150) * 60))
    
    result = {
        "audio_filename": audio_filename,
        "script": script,
        "sentences": sentences,
        "sentence_count": len(sentences),
        "word_count": word_count,
        "duration_estimate": duration_estimate,
        "voice": voice,
        "topic": topic,
        "doc_name": doc_name,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    
    # ── Save to TTS cache ──
    tts_cache[cache_key] = result
    _save_tts_cache(tts_cache)
    
    return result


def generate_tts_video_for_topic(
    topic: str,
    content: str,
    user_id: str,
    doc_name: str = "",
    language: str = "en",
    voice: str = ""
) -> Dict:
    """
    Full TTS pipeline: generate script → generate audio → return result.
    This is synchronous and fast (no polling needed).
    If no voice specified, picks one randomly based on topic hash.
    """
    # Pick a random voice if none specified
    if not voice:
        available_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        topic_hash = int(hashlib.md5(topic.lower().strip().encode()).hexdigest(), 16)
        voice = available_voices[topic_hash % len(available_voices)]

    # ── Check if already cached ──
    cache_key = _cache_key(user_id, doc_name, topic, language)
    tts_cache = _load_tts_cache()
    
    if cache_key in tts_cache:
        cached = tts_cache[cache_key]
        audio_path = TTS_AUDIO_DIR / cached.get("audio_filename", "")
        if audio_path.exists():
            logger.info(f"🎯 TTS cache hit for '{topic}'")
            return {"status": "completed", **cached}
    
    # ── Step 1: Generate teaching script ──
    logger.info(f"📝 Generating teaching script for TTS: '{topic}'")
    script = generate_teaching_script(topic, content, language)
    
    if not script:
        return {"status": "failed", "error": "Failed to generate teaching script"}
    
    # ── Step 2: Generate TTS audio ──
    try:
        result = generate_tts_audio(
            script=script,
            topic=topic,
            user_id=user_id,
            doc_name=doc_name,
            voice=voice,
            language=language
        )
        return {"status": "completed", **result}
    except Exception as e:
        logger.error(f"TTS pipeline failed: {e}")
        return {"status": "failed", "error": str(e), "script": script}


# ══════════════════════════════════════════════════════════════════════
# ▸ Dialogue TTS — Per-line Audio for Conversation Mode
# ══════════════════════════════════════════════════════════════════════

def generate_dialogue_audio(
    dialogue_lines: list,
    voice_map: dict,
    topic: str,
    user_id: str = "",
    doc_name: str = ""
) -> list:
    """
    Generate individual TTS audio files for each dialogue line.
    Uses parallel threads for faster generation.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    topic_slug = hashlib.md5(f"{user_id}:{doc_name}:{topic}".encode()).hexdigest()[:10]
    audio_files = [""] * len(dialogue_lines)  # Pre-size list to maintain order

    # Detect language from dialogue_lines metadata (passed via voice_map extra key)
    lang = voice_map.get("__language__", "en")
    # Include language in slug so Tamil and English never share cached files
    lang_topic_slug = hashlib.md5(f"{user_id}:{doc_name}:{topic}:{lang}".encode()).hexdigest()[:10]

    def _generate_one(idx, line):
        speaker = line.get("speaker", "")
        text = line.get("text", "")
        voice = voice_map.get(speaker, "nova")

        if not text.strip():
            return idx, ""

        audio_filename = f"dialogue_{lang_topic_slug}_{idx}.mp3"
        audio_path = TTS_AUDIO_DIR / audio_filename

        if audio_path.exists():
            logger.info(f"🎯 Dialogue audio cache hit: line {idx} ({speaker})")
            return idx, audio_filename

        try:
            if lang == "ta" and SARVAM_API_KEY:
                # ── Sarvam AI — natural Tamil voice ──
                logger.info(f"🔊 Tamil dialogue TTS via Sarvam: line {idx} ({speaker})")
                generate_sarvam_tts(text, audio_path, language="ta")
            else:
                # ── OpenAI TTS — English ──
                logger.info(f"🔊 Generating dialogue audio: line {idx} ({speaker}, voice={voice})")
                response = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                    response_format="mp3"
                )
                response.stream_to_file(str(audio_path))
            return idx, audio_filename
        except Exception as e:
            logger.error(f"Dialogue TTS line {idx} failed: {e}")
            return idx, ""

    # Run all TTS calls in parallel (max 5 concurrent)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_generate_one, i, line) for i, line in enumerate(dialogue_lines)]
        for fut in as_completed(futures):
            idx, filename = fut.result()
            audio_files[idx] = filename

    logger.info(f"✅ Generated {sum(1 for f in audio_files if f)} / {len(dialogue_lines)} dialogue audio files")
    return audio_files


# ══════════════════════════════════════════════════════════════════════
# ▸ Wikipedia Image Enrichment — Free, CDN-cached, No API Key Needed
# ══════════════════════════════════════════════════════════════════════

from concurrent.futures import ThreadPoolExecutor, as_completed as _as_completed

def fetch_wikipedia_image(concept: str, language: str = "en") -> dict:
    """
    Fetch a Wikipedia thumbnail image URL for a given concept keyword.
    Uses the Wikipedia REST API — free, no key needed, globally CDN-cached.

    Returns: { "url": str, "caption": str } or empty dict if not found.
    """
    if not concept or not concept.strip():
        return {}

    # Use English Wikipedia for images even for Tamil lessons (better coverage)
    wiki_lang = "en"
    concept_encoded = concept.strip().replace(" ", "_")

    try:
        url = f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{concept_encoded}"
        resp = requests.get(url, timeout=5, headers={"User-Agent": "ZenzeeEdTech/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            thumbnail = data.get("thumbnail", {})
            img_url = thumbnail.get("source", "")
            if img_url:
                # Upscale to ~400px for better quality
                img_url = img_url.replace("/100px-", "/400px-").replace("/150px-", "/400px-").replace("/200px-", "/400px-")
                caption = data.get("title", concept)
                return {"url": img_url, "caption": caption}
    except Exception as e:
        logger.debug(f"Wikipedia image fetch failed for '{concept}': {e}")

    return {}


def extract_visual_concepts(sentences: list, topic: str, language: str = "en") -> list:
    """
    Use GPT to extract one search keyword per sentence for image lookup.
    Returns a list of concept strings, one per sentence.
    Groups them into a single GPT call for efficiency.
    """
    if not sentences:
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(sentences))
    prompt = f"""You are helping an educational platform find relevant images for each sentence in a lesson about "{topic}".

For each numbered sentence below, output ONE short, specific English search keyword (1-3 words) that best represents the VISUAL concept in that sentence. This keyword will be used to find a Wikipedia image.

Rules:
- Output ONLY the keyword, one per line, numbered to match
- Use clear, concrete nouns (e.g. "mitochondria", "water cycle", "Eiffel Tower")
- If a sentence is a greeting or transition with no visual concept, output: none
- Always output exactly {len(sentences)} lines

Sentences:
{numbered}

Keywords (one per line):"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=len(sentences) * 10  # ~10 tokens per concept
        )
        raw = response.choices[0].message.content.strip().split("\n")
        concepts = []
        for line in raw:
            line = line.strip()
            # Strip leading number and punctuation: "1. mitochondria" → "mitochondria"
            if line and line[0].isdigit():
                line = line.split(".", 1)[-1].strip()
            concepts.append(line if line.lower() != "none" else "")
        # Pad or trim to match sentence count
        while len(concepts) < len(sentences):
            concepts.append("")
        return concepts[:len(sentences)]
    except Exception as e:
        logger.warning(f"Concept extraction failed: {e}")
        return [""] * len(sentences)


def enrich_sentences_with_images(sentences: list, topic: str, language: str = "en") -> list:
    """
    Enrich a list of sentence strings with Wikipedia image URLs.
    Each sentence dict (or string) gets an `image_url` and `image_caption` field.

    Input:  ["sentence 1", "sentence 2", ...]  OR  [{"text": ..., ...}, ...]
    Output: [{"text": ..., "image_url": ..., "image_caption": ...}, ...]
    """
    if not sentences:
        return []

    # Normalize to list of dicts
    normalized = []
    for s in sentences:
        if isinstance(s, dict):
            normalized.append(dict(s))
        else:
            normalized.append({"text": str(s)})

    # 1. Extract one concept keyword per sentence (single GPT call)
    texts = [item["text"] for item in normalized]
    concepts = extract_visual_concepts(texts, topic, language)

    # 2. Deduplicate concepts for parallel Wikipedia lookups
    unique_concepts = list(set(c for c in concepts if c))
    concept_image_map = {}

    def _fetch_one(concept):
        result = fetch_wikipedia_image(concept, language)
        return concept, result

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, c): c for c in unique_concepts}
        for fut in _as_completed(futures):
            concept, result = fut.result()
            if result:
                concept_image_map[concept] = result

    # 3. Attach image data to each sentence
    for i, item in enumerate(normalized):
        concept = concepts[i] if i < len(concepts) else ""
        img = concept_image_map.get(concept, {})
        item["image_url"] = img.get("url", "")
        item["image_caption"] = img.get("caption", "")

    logger.info(f"✅ Image enrichment: {sum(1 for s in normalized if s.get('image_url'))} / {len(normalized)} sentences got images")
    return normalized
