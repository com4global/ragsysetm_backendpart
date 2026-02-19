"""
HeyGen Video Generation Service
Generates AI teaching videos from document content.

Pipeline:
  1. PDF chunks (from Pinecone) → LLM generates a teaching script
  2. Script → HeyGen Video Agent API → video_id
  3. Poll HeyGen for video status → completed → video_url
  4. Cache video_url so the same topic is never re-generated

Uses the simple Video Agent endpoint (v1/video_agent/generate)
which is the fastest path from text to video.
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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

logger = logging.getLogger(__name__)

# ── Video Cache (JSON file) ─────────────────────────────────────────
CACHE_DIR = Path("/tmp") if os.name != "nt" else Path(os.environ.get("TEMP", "."))
CACHE_FILE = CACHE_DIR / "heygen_video_cache.json"


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


def _cache_key(user_id: str, doc_name: str, topic: str) -> str:
    """Generate a deterministic cache key for a video."""
    raw = f"{user_id}|{doc_name}|{topic}".lower().strip()
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


def generate_tts_audio(
    script: str,
    topic: str,
    user_id: str = "",
    doc_name: str = "",
    voice: str = "nova"
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
    cache_key = _cache_key(user_id, doc_name, topic)
    tts_cache = _load_tts_cache()
    
    if cache_key in tts_cache:
        cached = tts_cache[cache_key]
        audio_path = TTS_AUDIO_DIR / cached.get("audio_filename", "")
        if audio_path.exists():
            logger.info(f"🎯 TTS cache hit for '{topic}'")
            return cached
    
    # ── Generate audio via OpenAI TTS ──
    audio_filename = f"tts_{cache_key}.mp3"
    audio_path = TTS_AUDIO_DIR / audio_filename
    
    try:
        logger.info(f"🔊 Generating TTS audio for: '{topic}' (voice={voice})")
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=script,
            response_format="mp3"
        )
        
        # Save the audio file
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
    cache_key = _cache_key(user_id, doc_name, topic)
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
            voice=voice
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

    def _generate_one(idx, line):
        speaker = line.get("speaker", "")
        text = line.get("text", "")
        voice = voice_map.get(speaker, "nova")

        if not text.strip():
            return idx, ""

        audio_filename = f"dialogue_{topic_slug}_{idx}.mp3"
        audio_path = TTS_AUDIO_DIR / audio_filename

        if audio_path.exists():
            logger.info(f"🎯 Dialogue audio cache hit: line {idx} ({speaker})")
            return idx, audio_filename

        try:
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
