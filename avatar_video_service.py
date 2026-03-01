"""
AI Avatar Video Engine
======================
Standalone service that generates polished teaching videos with:
  - AI talking head avatar (via Replicate SadTalker)
  - B-roll stock footage (via Pexels API)
  - Animated text overlays & captions
  - Smooth transitions
  - Background music (optional)

Pipeline:
  1. Script Generation (GPT-4o)
  2. Scene Planning (GPT-4o)
  3. TTS Audio per scene (OpenAI / Sarvam)
  4. Talking Head avatar (Replicate SadTalker)
  5. B-Roll footage search (Pexels)
  6. Video Composition (MoviePy + FFmpeg)
  7. Upload final MP4 to Supabase Storage
"""

import os
import json
import time
import uuid
import hashlib
import logging
import asyncio
import tempfile
import requests
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
DID_API_KEY = os.getenv("DID_API_KEY", "")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

# Thread-local storage for tracking which user triggers Replicate calls
import threading as _threading
_tls = _threading.local()

# ── Directories ─────────────────────────────────────────────────────
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# Temp dirs for processing (use /tmp on Linux/Vercel — /var/task is read-only)
if os.name == "nt":
    AVATAR_DIR = BASE_DIR / "static" / "avatars"
else:
    AVATAR_DIR = Path("/tmp") / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# Temp dirs for processing (use /tmp on Linux/Vercel)
if os.name == "nt":
    WORK_DIR = BASE_DIR / "static" / "avatar_video_temp"
else:
    WORK_DIR = Path("/tmp") / "avatar_video_temp"
WORK_DIR.mkdir(parents=True, exist_ok=True)

# ── Pre-made Avatars ────────────────────────────────────────────────
DEFAULT_AVATARS = [
    {
        "id": "avatar_priya",
        "name": "Priya",
        "description": "Corporate professional, warm and confident",
        "image": "avatar_priya.png",
        "style": "professional",
        "gender": "female",
    },
    {
        "id": "avatar_james",
        "name": "Dr. James",
        "description": "Senior academic, clear and authoritative",
        "image": "avatar_james.png",
        "style": "academic",
        "gender": "male",
    },
    {
        "id": "avatar_mei",
        "name": "Mei",
        "description": "Approachable educator, warm and friendly",
        "image": "avatar_mei.png",
        "style": "casual",
        "gender": "female",
    },
    {
        "id": "avatar_marcus",
        "name": "Marcus",
        "description": "Dynamic presenter, confident and engaging",
        "image": "avatar_marcus.png",
        "style": "modern",
        "gender": "male",
    },
    {
        "id": "avatar_sofia",
        "name": "Sofia",
        "description": "Friendly instructor, natural and expressive",
        "image": "avatar_sofia.png",
        "style": "casual",
        "gender": "female",
    },
    {
        "id": "avatar_omar",
        "name": "Omar",
        "description": "Knowledgeable educator, genuine and warm",
        "image": "avatar_omar.png",
        "style": "academic",
        "gender": "male",
    },
]

# ── Avatar type detection ───────────────────────────────────────────
_FACE_STYLES = {"professional", "academic", "casual", "modern", "corporate", "custom"}


def _is_face_avatar(avatar_id: str) -> bool:
    """
    Return True if the avatar is a human face (suitable for lip-sync).
    Returns False for fun objects (banana, car, robot, etc.) that have no face.
    Custom uploads are assumed to be face images.
    """
    if avatar_id.startswith("custom_"):
        return True
    for av in DEFAULT_AVATARS:
        if av["id"] == avatar_id:
            return av.get("style", "") in _FACE_STYLES
    # Unknown avatar — assume face
    return True


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 1: Script Generation
# ═══════════════════════════════════════════════════════════════════

def generate_video_script(
    topic: str,
    content: str = "",
    language: str = "en",
    style: str = "educational",
    duration_target: str = "2-3 minutes",
) -> str:
    """Generate a teaching video script from topic and optional content."""
    style_prompts = {
        "educational": "an engaging educational video that explains concepts clearly with examples",
        "presentation": "a professional presentation with key points, data, and takeaways",
        "story": "a storytelling narrative that makes the topic memorable and relatable",
    }
    style_desc = style_prompts.get(style, style_prompts["educational"])

    lang_rule = f"- Write in {language} language"
    if language == "ta":
        lang_rule = (
            "- Write the ENTIRE script in THANGLISH style:\n"
            "  - Use Tamil script (தமிழ்) as the primary language.\n"
            "  - Mix in English words naturally for technical terms, greetings, and common phrases.\n"
            "  - Use everyday conversational Tamil, NOT formal literary Tamil.\n"
            "  - Example: 'Hello friends! இன்று நாம் AI technology பற்றி learn பண்ணலாம்.'\n"
            "  - Keep the tone friendly, casual, and easy to understand."
        )

    system_prompt = f"""You are an expert video script writer. Write a script for {style_desc}.

Rules:
- Target duration: {duration_target}
{lang_rule}
- Use a conversational, engaging tone
- Include natural pauses (marked as [PAUSE])
- Structure: Opening hook → Main content → Summary/CTA
- Do NOT include stage directions or camera notes
- Write ONLY the narration text the speaker will say
- Use short paragraphs (2-3 sentences each) for natural speech rhythm"""

    user_prompt = f"Topic: {topic}"
    if content:
        user_prompt += f"\n\nReference material:\n{content[:4000]}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        script = response.choices[0].message.content.strip()
        logger.info(f"📝 Generated video script ({len(script)} chars) for '{topic}'")
        return script
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 2: Scene Planning
# ═══════════════════════════════════════════════════════════════════

def plan_video_scenes(
    script: str,
    style: str = "educational",
    language: str = "en",
    video_style: str = "educational_diagram",
) -> List[Dict]:
    """Split script into scenes with visual descriptions for B-roll search.

    video_style: "educational_diagram" (default), "animated_explainer", or "photorealistic"
    """

    if video_style == "educational_diagram":
        visual_query_instructions = """2. "visual_queries" — a LIST of 3 visual descriptions for AI-generated EDUCATIONAL DIAGRAMS and TECHNICAL ILLUSTRATIONS:
   - Query 1: A specific technical diagram (e.g. "flowchart showing data preprocessing pipeline with arrows: raw data → cleaning → feature extraction → model")
   - Query 2: An architecture or concept map (e.g. "neural network architecture diagram with input layer, two hidden layers, and output layer, labeled nodes")
   - Query 3: A comparison or summary visual (e.g. "comparison table of supervised vs unsupervised learning with icons and key differences")
   IMPORTANT: Describe EDUCATIONAL DIAGRAMS, not photographs.
   Think like a textbook illustrator or whiteboard presenter.
   Use concepts like: flowcharts, architecture diagrams, mind maps, process flows,
   labeled component diagrams, step-by-step workflows, comparison charts.
   Always include SPECIFIC LABELS and ARROWS in your description.
   Do NOT describe people, faces, or stock photography scenes."""
    elif video_style == "animated_explainer":
        visual_query_instructions = """2. "visual_queries" — a LIST of 3 visual descriptions for AI-generated 2D ILLUSTRATIONS (not photos):
   - Query 1: A specific illustration concept (e.g. "person sitting at desk using laptop with AI chatbot on screen")
   - Query 2: A broader related illustration (e.g. "robot character surrounded by holographic data dashboards")
   - Query 3: A safe generic fallback (e.g. "colorful technology icons and devices")
   IMPORTANT: Describe scenes as if you were art-directing a flat-design illustration or cartoon.
   Think about CHARACTERS, OBJECTS, and SCENES that would work as 2D vector art.
   Include visual elements like: people, robots, devices, icons, charts, speech bubbles.
   Do NOT use abstract concepts that can't be illustrated."""
    else:
        visual_query_instructions = """2. "visual_queries" — a LIST of 3 search queries for stock footage, ranked from most to least specific:
   - Query 1: The most relevant, specific visual concept (e.g. "team using AI dashboard")
   - Query 2: A broader related visual (e.g. "business technology office")
   - Query 3: A safe generic fallback (e.g. "modern office workspace")
   IMPORTANT: Queries must describe VISUALS that actually exist as stock footage.
   Do NOT use brand names, product names, or abstract concepts.
   Think: "What would I actually SEE on screen that represents this concept?"""

    style_labels = {
        'educational_diagram': 'educational diagrams and technical illustrations',
        'animated_explainer': '2D illustration scenes',
        'photorealistic': 'B-roll footage',
    }
    director_role = style_labels.get(video_style, 'educational diagrams')
    system_prompt = (
        f"You are a professional video director planning {director_role} for a narrated video.\n\n"
        f"Split the narration into 3-6 scenes. For each scene, provide:\n\n"
        f"1. \"narration\" — the exact text the speaker says\n"
        f"{visual_query_instructions}\n"
        f"3. \"text_overlay\" — a key phrase (5-8 words max) to display on screen\n"
        f"4. \"duration_estimate\" — estimated speaking duration in seconds (based on ~150 words/minute)\n"
        f"5. \"transition\" — transition type: \"fade\", \"slide_left\", \"slide_up\", or \"crossfade\"\n\n"
        "Return ONLY a JSON array. Example:\n"
        "[\n"
        '  {\n'
        '    "narration": "Our platform empowers teams to build AI agents...",\n'
        '    "visual_queries": [\n'
        '      "team collaborating on computer dashboard",\n'
        '      "software development team working",\n'
        '      "modern technology office"\n'
        '    ],\n'
        '    "visual_query": "team collaborating on computer dashboard",\n'
        '    "text_overlay": "Build AI Agents Effortlessly",\n'
        '    "duration_estimate": 15,\n'
        '    "transition": "fade"\n'
        '  }\n'
        "]"
    )

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Script:\n{script}"},
            ],
            temperature=0.3,
            max_tokens=3000,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # Handle both {"scenes": [...]} and direct [...]
        if isinstance(parsed, dict):
            scenes = parsed.get("scenes", parsed.get("data", []))
        elif isinstance(parsed, list):
            scenes = parsed
        else:
            scenes = []

        # Ensure backward compatibility: if visual_queries exists, set visual_query to first
        for scene in scenes:
            if "visual_queries" in scene and isinstance(scene["visual_queries"], list):
                if not scene.get("visual_query") and scene["visual_queries"]:
                    scene["visual_query"] = scene["visual_queries"][0]
            elif "visual_query" in scene and "visual_queries" not in scene:
                # Old format — wrap single query into list
                scene["visual_queries"] = [
                    scene["visual_query"],
                    "technology innovation",
                    "modern workspace",
                ]

        logger.info(f"🎬 Planned {len(scenes)} scenes")
        return scenes
    except Exception as e:
        logger.error(f"Scene planning failed: {e}")
        # Fallback: single scene with entire script
        return [
            {
                "narration": script,
                "visual_query": "education learning",
                "visual_queries": ["education learning", "classroom teaching", "students studying"],
                "text_overlay": "Learning",
                "duration_estimate": 60,
                "transition": "fade",
            }
        ]


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 3: TTS Audio Generation
# ═══════════════════════════════════════════════════════════════════

def generate_scene_audio(
    text: str,
    scene_index: int,
    job_id: str,
    voice: str = "nova",
    language: str = "en",
) -> Optional[str]:
    """Generate TTS audio for a single scene. Returns path to MP3 file."""
    if not text.strip():
        return None

    # Remove [PAUSE] markers cleanly — avoid "..." which confuses TTS timing
    clean_text = text.replace("[PAUSE]", " ").strip()
    # Collapse multiple spaces
    import re as _re
    clean_text = _re.sub(r'\s+', ' ', clean_text)
    audio_path = WORK_DIR / f"{job_id}_scene_{scene_index}.mp3"

    # Return cached if exists
    if audio_path.exists():
        logger.info(f"🎯 Scene {scene_index} audio cached")
        return str(audio_path)

    try:
        if language == "ta" and SARVAM_API_KEY:
            # Tamil TTS via Sarvam
            _generate_sarvam_tts(clean_text, audio_path, language="ta")
        else:
            # OpenAI TTS
            response = client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=clean_text,
                response_format="mp3",
            )
            response.stream_to_file(str(audio_path))

        logger.info(f"🔊 Generated audio for scene {scene_index} ({len(clean_text)} chars)")
        return str(audio_path)
    except Exception as e:
        logger.error(f"Scene {scene_index} TTS failed: {e}")
        return None


def _generate_sarvam_tts(text: str, output_path: Path, language: str = "ta"):
    """Generate TTS using Sarvam AI bulbul:v2 for Indian languages.
    Handles long text by chunking at sentence boundaries (400 char limit).
    Uses the same correct approach as heygen_service.generate_sarvam_tts."""
    import base64, io, wave, re as _re, random as _rnd

    headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}

    # ── Chunk text at sentence boundaries (Sarvam v2 limit: ~400 chars) ──
    CHUNK_SIZE = 400
    sentence_list = _re.split(r'(?<=[.!?।])\s+', text.strip())
    sentence_list = [s.strip() for s in sentence_list if s.strip()]

    chunks = []
    current_chunk = ""
    for sentence in sentence_list:
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

    # Pick a random Tamil speaker for consistency within this call
    _TAMIL_SPEAKERS = ["anushka", "manisha", "vidya", "arya"]
    chosen_speaker = _rnd.choice(_TAMIL_SPEAKERS)
    logger.info(f"🔢 Sarvam TTS (avatar): {len(text)} chars → {len(chunks)} chunks, speaker={chosen_speaker}")

    audio_segments = []
    for chunk in chunks:
        payload = {
            "text": chunk,
            "target_language_code": "ta-IN",
            "speaker": chosen_speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2",
        }
        try:
            resp = requests.post("https://api.sarvam.ai/text-to-speech", json=payload, headers=headers, timeout=30)
            if not resp.ok:
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

    # Merge WAV chunks into single file, then convert to MP3
    merged_frames = b""
    first_params = None
    for seg in audio_segments:
        with wave.open(io.BytesIO(seg), 'rb') as wf:
            if first_params is None:
                first_params = wf.getparams()
            merged_frames += wf.readframes(wf.getnframes())

    if not first_params:
        raise RuntimeError("Sarvam TTS: no valid WAV params")

    wav_path = output_path.with_suffix(".wav")
    with wave.open(str(wav_path), 'wb') as out:
        out.setparams(first_params)
        out.writeframes(merged_frames)

    # Convert WAV → MP3 using pydub if available
    try:
        from pydub import AudioSegment
        AudioSegment.from_wav(str(wav_path)).export(str(output_path), format="mp3", bitrate="128k")
        wav_path.unlink(missing_ok=True)
        logger.info(f"✅ Sarvam Tamil TTS saved (MP3): {output_path}")
    except Exception:
        import shutil
        shutil.move(str(wav_path), str(output_path))
        logger.info(f"✅ Sarvam Tamil TTS saved (WAV→MP3 rename): {output_path}")


def generate_all_scene_audio(
    scenes: List[Dict],
    job_id: str,
    voice: str = "nova",
    language: str = "en",
) -> List[Optional[str]]:
    """Generate TTS audio for all scenes in parallel."""
    audio_paths = [None] * len(scenes)

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {}
        for i, scene in enumerate(scenes):
            fut = pool.submit(
                generate_scene_audio,
                scene.get("narration", ""),
                i,
                job_id,
                voice,
                language,
            )
            futures[fut] = i

        for fut in futures:
            idx = futures[fut]
            try:
                audio_paths[idx] = fut.result()
            except Exception as e:
                logger.error(f"Audio generation failed for scene {idx}: {e}")

    generated = sum(1 for p in audio_paths if p)
    logger.info(f"✅ Generated {generated}/{len(scenes)} scene audio files")
    return audio_paths


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 4: Talking Head Avatar (Replicate Wav2Lip via HTTP API)
# ═══════════════════════════════════════════════════════════════════

FONT_PATH = str(BASE_DIR / "static" / "fonts" / "Inter.ttf")
MUSIC_DIR = BASE_DIR / "static" / "music"


def _log_replicate_usage(status_data: dict, model_ref: str):
    """Log Replicate prediction usage to usage_logs table."""
    try:
        user_id = getattr(_tls, 'current_user_id', None) or 'system'
        metrics = status_data.get('metrics', {})
        predict_time = metrics.get('predict_time', 0) or 0
        # Replicate GPU cost is ~$0.000225/s for standard GPU
        estimated_cost = predict_time * 0.000225

        from database import supabase as sb
        if sb:
            sb.table("usage_logs").insert({
                "user_id": user_id,
                "service": "replicate",
                "action": "prediction",
                "tokens_used": 0,
                "cost_usd": round(estimated_cost, 6),
                "metadata": {
                    "model": model_ref,
                    "predict_time_seconds": round(predict_time, 2),
                    "prediction_id": status_data.get("id", ""),
                }
            }).execute()
            logger.info(f"   📊 Replicate usage logged: {predict_time:.1f}s, ~${estimated_cost:.4f} for user {user_id}")
    except Exception as e:
        logger.warning(f"   Replicate usage logging failed (non-fatal): {e}")

def _replicate_api(model_version: str, input_data: dict, timeout: int = 300) -> dict:
    """Call Replicate API via direct HTTP (avoids pip dependency conflicts)."""
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Create prediction
    resp = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers=headers,
        json={"version": model_version, "input": input_data},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Replicate API error {resp.status_code}: {resp.text[:300]}")

    prediction = resp.json()
    pred_id = prediction["id"]
    logger.info(f"   Replicate prediction started: {pred_id}")

    # Poll for completion
    poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        poll_resp = requests.get(poll_url, headers=headers, timeout=15)
        status_data = poll_resp.json()
        status = status_data.get("status", "")

        if status == "succeeded":
            _log_replicate_usage(status_data, model_version)
            return status_data
        elif status == "failed":
            raise RuntimeError(f"Replicate prediction failed: {status_data.get('error', 'unknown')}")
        elif status == "canceled":
            raise RuntimeError("Replicate prediction was canceled")

    raise RuntimeError(f"Replicate prediction timed out after {timeout}s")


def _replicate_model_api(model_owner: str, model_name: str, input_data: dict, timeout: int = 300) -> dict:
    """Call Replicate API using model name (auto-selects latest version).
    Includes automatic retry with backoff for rate-limit (429) errors.
    """
    headers = {
        "Authorization": f"Bearer {REPLICATE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Create prediction via model endpoint (no version hash needed)
    url = f"https://api.replicate.com/v1/models/{model_owner}/{model_name}/predictions"

    # Retry with backoff for rate-limit errors
    max_retries = 3
    for attempt in range(max_retries):
        resp = requests.post(
            url,
            headers=headers,
            json={"input": input_data},
            timeout=30,
        )
        if resp.status_code == 429:
            wait = (attempt + 1) * 8  # 8s, 16s, 24s backoff
            logger.warning(f"   Rate limited (429), waiting {wait}s before retry {attempt+1}/{max_retries}")
            time.sleep(wait)
            continue
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Replicate model API error {resp.status_code}: {resp.text[:300]}")
        break
    else:
        raise RuntimeError(f"Replicate rate-limited after {max_retries} retries")

    prediction = resp.json()
    pred_id = prediction["id"]
    logger.info(f"   Replicate prediction started: {pred_id} ({model_owner}/{model_name})")

    # Poll for completion
    poll_url = f"https://api.replicate.com/v1/predictions/{pred_id}"
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        poll_resp = requests.get(poll_url, headers=headers, timeout=15)
        status_data = poll_resp.json()
        status = status_data.get("status", "")

        if status == "succeeded":
            _log_replicate_usage(status_data, f"{model_owner}/{model_name}")
            return status_data
        elif status == "failed":
            raise RuntimeError(f"Replicate prediction failed: {status_data.get('error', 'unknown')}")
        elif status == "canceled":
            raise RuntimeError("Replicate prediction was canceled")

    raise RuntimeError(f"Replicate prediction timed out after {timeout}s")



def _upload_file_to_replicate(file_path: str) -> str:
    """Upload a file to Replicate and return a URL for use as input."""
    headers = {"Authorization": f"Bearer {REPLICATE_API_TOKEN}"}

    # Create file upload
    resp = requests.post(
        "https://api.replicate.com/v1/files",
        headers=headers,
        files={"content": (Path(file_path).name, open(file_path, "rb"))},
        timeout=60,
    )
    if resp.status_code in (200, 201):
        file_data = resp.json()
        url = file_data.get("urls", {}).get("get", "")
        if url:
            return url

    # Fallback: use data URI for small files, or a public URL trick
    # For now, use the serving URL directly
    logger.warning(f"File upload returned {resp.status_code}, trying direct serve")
    return ""


def generate_avatar_face(avatar_id: str, description: str = "") -> Optional[str]:
    """
    Auto-generate a professional avatar face image using Replicate FLUX Schnell.
    Returns path to generated PNG file.
    """
    if not REPLICATE_API_TOKEN:
        return None

    output_path = AVATAR_DIR / f"{avatar_id}.png"
    if output_path.exists():
        return str(output_path)

    # Find avatar description from defaults
    avatar_desc = description
    if not avatar_desc:
        for av in DEFAULT_AVATARS:
            if av["id"] == avatar_id:
                avatar_desc = av.get("description", "professional teacher")
                break
    if not avatar_desc:
        avatar_desc = "professional presenter"

    prompt = (
        f"Professional headshot portrait photo of a {avatar_desc}, "
        f"looking at camera, friendly smile, clean studio background, "
        f"broadcast quality, photorealistic, 4K, sharp focus, "
        f"professional lighting, upper body shot"
    )

    try:
        logger.info(f"🧑 Generating avatar face for '{avatar_id}': {prompt[:80]}...")
        result = _replicate_api(
            # FLUX Schnell - fast, high quality
            "39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            {
                "prompt": prompt,
                "width": 768,
                "height": 768,
                "num_outputs": 1,
                "num_inference_steps": 4,
                "output_format": "png",
            },
            timeout=120,
        )

        output = result.get("output", [])
        if output:
            img_url = output[0] if isinstance(output, list) else str(output)
            img_resp = requests.get(img_url, timeout=30)
            if img_resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                logger.info(f"✅ Avatar face generated: {output_path} ({len(img_resp.content)} bytes)")
                return str(output_path)

        logger.warning(f"Avatar face generation returned no output for '{avatar_id}'")
        return None

    except Exception as e:
        logger.error(f"Avatar face generation failed for '{avatar_id}': {e}")
        return None


def generate_talking_head(
    avatar_image_path: str,
    audio_path: str,
    scene_index: int,
    job_id: str,
) -> Optional[str]:
    """
    Generate a talking head video using SadTalker (single-step, fast).
    SadTalker produces natural head movement + lip sync from still image + audio.
    MuseTalk refinement step removed for ~3-4min speed gain per video — the
    difference is negligible at PiP sizes used in presentation mode.
    """
    if not REPLICATE_API_TOKEN:
        logger.warning("REPLICATE_API_TOKEN not set — skipping talking head generation")
        return None

    output_path = WORK_DIR / f"{job_id}_avatar_{scene_index}.mp4"
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"🎯 Avatar clip {scene_index} cached")
        return str(output_path)

    try:
        logger.info(f"🤖 Generating lip-sync talking head for scene {scene_index}...")

        # Upload files to Replicate
        face_url = _upload_file_to_replicate(avatar_image_path)
        audio_url = _upload_file_to_replicate(audio_path)
        logger.info(f"   Face URL: {'set' if face_url else 'EMPTY'}, Audio URL: {'set' if audio_url else 'EMPTY'}")

        if not face_url or not audio_url:
            import base64
            if not face_url:
                with open(avatar_image_path, "rb") as f:
                    face_b64 = base64.b64encode(f.read()).decode()
                face_url = f"data:image/png;base64,{face_b64}"
            if not audio_url:
                with open(audio_path, "rb") as f:
                    audio_b64 = base64.b64encode(f.read()).decode()
                audio_url = f"data:audio/mp3;base64,{audio_b64}"

        # ═══════════════════════════════════════════════════════════════
        # SadTalker — head animation + lip-sync (image + audio → video)
        # Single-step pipeline: natural head movement + mouth animation
        # ═══════════════════════════════════════════════════════════════
        sadtalker_result = None
        try:
            logger.info(f"   [{job_id}] SadTalker lip-sync for scene {scene_index}...")
            st_input = {
                    "source_image": face_url,
                    "driven_audio": audio_url,
                    "pose_style": 0,
                    "facerender": "facevid2vid",
                    "expression_scale": 1.5,
                    "still": False,
                    "preprocess": "full",
            }
            try:
                # Primary: lucataco/sadtalker (verified working)
                sadtalker_result = _replicate_api(
                    "85c698db7c0a66d5011435d0191db323034e1da04b912a6d365833141b6a285b",
                    st_input,
                    timeout=300,
                )
            except Exception as primary_err:
                logger.warning(f"   [{job_id}] Primary SadTalker failed: {primary_err}, trying fallback...")
                # Fallback: cjwbw/sadtalker (original)
                sadtalker_result = _replicate_api(
                    "a519cc0cfebaaeade068b23899165a11ec76aaa1d2b313d40d214f204ec957a3",
                    st_input,
                    timeout=300,
                )
        except Exception as st_err:
            logger.error(f"   [{job_id}] SadTalker failed for scene {scene_index}: {st_err}")

        # Download SadTalker output directly as final avatar clip
        st_output = sadtalker_result.get("output") if sadtalker_result else None
        if st_output:
            st_video_url = str(st_output)
            resp = requests.get(st_video_url, stream=True, timeout=120)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"✅ [{job_id}] SadTalker lip-sync done for scene {scene_index} ({output_path.stat().st_size} bytes)")
                return str(output_path)
            else:
                logger.error(f"   [{job_id}] SadTalker download failed: {resp.status_code}")
                return None
        else:
            logger.error(f"   [{job_id}] SadTalker returned no output for scene {scene_index}")
            return None

    except Exception as e:
        import traceback as _tb_mod
        logger.error(f"Talking head generation failed for scene {scene_index}: {e}\n{_tb_mod.format_exc()}")
        return None


def generate_all_talking_heads(
    avatar_image_path: str,
    audio_paths: List[Optional[str]],
    job_id: str,
) -> List[Optional[str]]:
    """Generate talking head clips for all scenes in PARALLEL for speed."""
    n = len(audio_paths)
    clips: List[Optional[str]] = [None] * n

    # Build list of (index, audio_path) for scenes that have audio
    tasks = [(idx, ap) for idx, ap in enumerate(audio_paths) if ap]

    if not tasks:
        return clips

    logger.info(f"🚀 [{job_id}] Generating {len(tasks)} lip-sync clips in parallel...")

    def _gen(idx_ap):
        idx, ap = idx_ap
        return idx, generate_talking_head(avatar_image_path, ap, idx, job_id)

    # Max 3 parallel for speed (Replicate handles concurrent requests)
    # OPT: Increased from 3→5 workers for faster parallel lip-sync
    with ThreadPoolExecutor(max_workers=min(5, len(tasks))) as pool:
        for idx, clip in pool.map(_gen, tasks):
            clips[idx] = clip

    done = sum(1 for c in clips if c)
    logger.info(f"✅ [{job_id}] Parallel lip-sync complete: {done}/{n} clips generated")
    return clips


def generate_did_talking_head(
    scene_text: str,
    scene_index: int,
    job_id: str,
    avatar_image_url: str = "",
    language: str = "en",
) -> Optional[str]:
    """
    Generate a talking head clip for a single scene using D-ID.
    D-ID handles TTS + lip-sync in one call.
    Returns local path to downloaded MP4 clip, or None on failure.
    """
    try:
        from did_service import create_did_talk_with_source, poll_did_talk, download_did_video

        logger.info(f"🎬 [{job_id}] D-ID scene {scene_index}: submitting ({len(scene_text)} chars)")

        # Submit talk to D-ID
        result = create_did_talk_with_source(
            script_text=scene_text,
            source_url=avatar_image_url,
            language=language,
        )
        talk_id = result["id"]

        # Poll until done
        talk_data = poll_did_talk(talk_id, max_wait=180, interval=5)
        video_url = talk_data.get("result_url", "")

        if not video_url:
            logger.error(f"❌ [{job_id}] D-ID scene {scene_index}: no result_url")
            return None

        # Download to local file
        output_path = str(WORK_DIR / f"{job_id}_did_scene{scene_index}.mp4")
        download_did_video(video_url, output_path)
        logger.info(f"✅ [{job_id}] D-ID scene {scene_index}: ready → {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"❌ [{job_id}] D-ID scene {scene_index} failed: {e}")
        return None


def generate_all_did_talking_heads(
    scenes: List[Dict],
    job_id: str,
    avatar_image_url: str = "",
    language: str = "en",
) -> List[Optional[str]]:
    """
    Generate D-ID talking head clips for all scenes sequentially.
    D-ID handles TTS internally — audio_paths not needed.
    """
    clips: List[Optional[str]] = []
    for idx, scene in enumerate(scenes):
        narration = scene.get("narration", scene.get("text", ""))
        if narration:
            clip = generate_did_talking_head(
                scene_text=narration,
                scene_index=idx,
                job_id=job_id,
                avatar_image_url=avatar_image_url,
                language=language,
            )
            clips.append(clip)
        else:
            clips.append(None)
    return clips


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 5: Scene Visuals (AI-Generated via FLUX Schnell + Pexels Fallback)
# ═══════════════════════════════════════════════════════════════════

def generate_ai_scene_image(
    visual_query: str,
    scene_index: int,
    job_id: str,
    narration: str = "",
    aspect_ratio: str = "16:9",
    video_style: str = "educational_diagram",
    image_only: bool = False,
) -> Optional[str]:
    """
    Generate a custom AI scene image using Replicate FLUX Schnell.
    When image_only=False: returns the path to a video clip with Ken Burns zoom.
    When image_only=True: saves the PNG and returns the image path (skips video conversion).
    """
    if not REPLICATE_API_TOKEN:
        logger.info(f"   [{job_id}] REPLICATE_API_TOKEN not set — skipping AI image for scene {scene_index}")
        return None

    # In image_only mode, check if the PNG already exists
    img_path = WORK_DIR / f"{job_id}_ai_img_{scene_index}.png"
    if image_only:
        if img_path.exists() and img_path.stat().st_size > 1000:
            logger.info(f"🎯 AI image {scene_index} cached (image_only mode)")
            return str(img_path)
    else:
        output_path = WORK_DIR / f"{job_id}_ai_broll_{scene_index}.mp4"
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"🎯 AI B-roll {scene_index} cached")
            return str(output_path)

    if img_path.exists() and img_path.stat().st_size > 1000:
        logger.info(f"🎯 AI image {scene_index} cached, converting to video...")
    else:
        try:
            # Build prompt based on video style
            if video_style == "educational_diagram":
                cinematic_prompt = (
                    f"Clean professional educational diagram on white background, {visual_query}, "
                    f"technical illustration style with labeled components and directional arrows, "
                    f"infographic layout, professional textbook quality, "
                    f"minimal color palette using navy blue and dark gray with orange accents, "
                    f"vector-style clean lines, no photographs, no human faces, no people, "
                    f"sharp geometric shapes, boxes connected by arrows, clear visual hierarchy"
                )
            elif video_style == "animated_explainer":
                cinematic_prompt = (
                    f"Modern flat design 2D illustration, {visual_query}, "
                    f"vector art style, clean minimalist design, solid color background, "
                    f"cartoon characters, vibrant colors, digital art, "
                    f"no text, no watermarks, no labels"
                )
            else:
                cinematic_prompt = (
                    f"Cinematic high-quality photograph, {visual_query}, "
                    f"professional lighting, sharp focus, 8K resolution, "
                    f"commercial quality, no text, no watermarks"
                )
            logger.info(f"🎨 [{job_id}] Generating AI image for scene {scene_index}: '{visual_query}'")

            # FLUX Schnell — fast, high-quality image generation
            result = _replicate_model_api(
                "black-forest-labs", "flux-schnell",
                {
                    "prompt": cinematic_prompt,
                    "num_outputs": 1,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "png",
                    "output_quality": 90,
                },
                timeout=120,
            )

            output = result.get("output")
            if output:
                # Output is a list of URLs
                img_url = output[0] if isinstance(output, list) else str(output)
                resp = requests.get(img_url, stream=True, timeout=60)
                if resp.status_code == 200:
                    with open(img_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"✅ [{job_id}] AI image generated for scene {scene_index} ({img_path.stat().st_size} bytes)")
                else:
                    logger.warning(f"   [{job_id}] Failed to download AI image: HTTP {resp.status_code}")
                    return None
            else:
                logger.warning(f"   [{job_id}] FLUX returned no output for scene {scene_index}")
                return None

        except Exception as e:
            logger.warning(f"   [{job_id}] AI image generation failed for scene {scene_index}: {e}")
            return None

    # OPT: In image_only mode (presentation), skip Ken Burns video conversion
    if image_only:
        if img_path.exists():
            logger.info(f"✅ [{job_id}] AI image saved for scene {scene_index} ({img_path.stat().st_size} bytes) [image_only]")
            return str(img_path)
        return None

    # Convert the AI-generated image to video with Ken Burns zoom
    if img_path.exists():
        try:
            import subprocess
            zoom_cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-i", str(img_path),
                "-vf", (
                    "scale=3840:2160,zoompan=z='min(zoom+0.0008,1.12)':"
                    "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    "d=300:s=1920x1080:fps=30"
                ),
                "-t", "10",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-pix_fmt", "yuv420p",
                str(output_path)
            ]
            result = subprocess.run(zoom_cmd, capture_output=True, timeout=60)
            if result.returncode == 0 and output_path.exists():
                logger.info(f"🎬 [{job_id}] AI scene video created for scene {scene_index} ({output_path.stat().st_size} bytes)")
                return str(output_path)
            else:
                logger.warning(f"   [{job_id}] Ken Burns zoom failed: {result.stderr[-200:] if result.stderr else 'unknown'}")
        except Exception as e:
            logger.warning(f"   [{job_id}] Ken Burns conversion failed for scene {scene_index}: {e}")

    return None


def search_broll_footage(
    query: str,
    scene_index: int,
    job_id: str,
    min_duration: int = 5,
    max_duration: int = 30,
    fallback_queries: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Search and download B-roll footage from Pexels API.
    Tries a cascade of queries: primary → fallback_queries → Pexels image search.
    """
    if not PEXELS_API_KEY:
        logger.warning("PEXELS_API_KEY not set — skipping B-roll search")
        return None

    output_path = WORK_DIR / f"{job_id}_broll_{scene_index}.mp4"
    if output_path.exists():
        logger.info(f"🎯 B-roll {scene_index} cached")
        return str(output_path)

    # Build the ordered list of queries to try
    queries_to_try = [query]
    if fallback_queries:
        for fq in fallback_queries:
            if fq and fq != query and fq not in queries_to_try:
                queries_to_try.append(fq)

    headers = {"Authorization": PEXELS_API_KEY}

    # ── Phase 1: Try VIDEO search with cascading queries ──
    for q_idx, search_query in enumerate(queries_to_try):
        try:
            params = {
                "query": search_query,
                "per_page": 5,
                "min_duration": min_duration,
                "max_duration": max_duration,
                "orientation": "landscape",
            }
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params=params,
            )

            if resp.status_code != 200:
                logger.warning(f"Pexels video API returned {resp.status_code} for '{search_query}'")
                continue

            data = resp.json()
            videos = data.get("videos", [])
            if not videos:
                logger.info(f"   [{job_id}] No video B-roll for query [{q_idx+1}/{len(queries_to_try)}]: '{search_query}'")
                continue

            # Pick best video (HD quality preferred)
            video = videos[0]
            video_files = video.get("video_files", [])

            best_file = None
            for vf in video_files:
                if vf.get("height", 0) >= 720 and vf.get("quality") in ["hd", "sd"]:
                    best_file = vf
                    break
            if not best_file and video_files:
                best_file = video_files[0]

            if not best_file:
                continue

            dl_url = best_file.get("link", "")
            if dl_url:
                dl_resp = requests.get(dl_url, stream=True, timeout=60)
                if dl_resp.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in dl_resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"📹 Downloaded video B-roll for scene {scene_index}: '{search_query}' (query {q_idx+1})")
                    return str(output_path)

        except Exception as e:
            logger.warning(f"Video search failed for '{search_query}': {e}")
            continue

    # ── Phase 2: Try PHOTO search and convert to video ──
    logger.info(f"   [{job_id}] No video found — trying Pexels photo search...")
    for q_idx, search_query in enumerate(queries_to_try[:2]):  # Only try first 2 queries for photos
        try:
            params = {
                "query": search_query,
                "per_page": 3,
                "orientation": "landscape",
                "size": "large",
            }
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params=params,
            )

            if resp.status_code != 200:
                continue

            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                continue

            # Download the best photo
            photo = photos[0]
            photo_url = photo.get("src", {}).get("large2x") or photo.get("src", {}).get("large", "")
            if not photo_url:
                continue

            img_path = WORK_DIR / f"{job_id}_broll_img_{scene_index}.jpg"
            dl_resp = requests.get(photo_url, stream=True, timeout=30)
            if dl_resp.status_code == 200:
                with open(img_path, "wb") as f:
                    for chunk in dl_resp.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Convert image to video with slow Ken Burns zoom effect (1080p)
                import subprocess
                zoom_cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1", "-i", str(img_path),
                    "-vf", (
                        "scale=3840:2160,zoompan=z='min(zoom+0.0008,1.12)':"
                        "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                        "d=300:s=1920x1080:fps=30"
                    ),
                    "-t", "10",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    str(output_path)
                ]
                result = subprocess.run(zoom_cmd, capture_output=True, timeout=30)
                if result.returncode == 0 and output_path.exists():
                    logger.info(f"🖼️ Created B-roll from photo for scene {scene_index}: '{search_query}'")
                    # Clean up temp image
                    try:
                        img_path.unlink()
                    except Exception:
                        pass
                    return str(output_path)

        except Exception as e:
            logger.warning(f"Photo search failed for '{search_query}': {e}")
            continue

    logger.warning(f"❌ No B-roll found for scene {scene_index} after trying {len(queries_to_try)} queries")
    return None


def search_all_broll(
    scenes: List[Dict],
    job_id: str,
    video_style: str = "educational_diagram",
    video_mode: str = "avatar",
) -> List[Optional[str]]:
    """
    Get scene visuals for all scenes.
    In presentation mode: generates AI images only (PNG) — frontend shows them as slides.
    In avatar mode: generates full Ken Burns videos + Pexels fallback.
    """
    broll_paths: List[Optional[str]] = [None] * len(scenes)
    # OPT: In presentation mode, frontend displays _ai_img_X.png directly as slides.
    # Skip Ken Burns video conversion and Pexels search entirely (~60s saved).
    is_presentation = video_mode == "presentation"

    # ── Phase 1: AI-Generated Scene Images (FLUX Schnell) ──
    # OPT: Parallelized with 3 workers instead of sequential loop (~2x faster)
    if REPLICATE_API_TOKEN:
        mode_label = "image-only" if is_presentation else "full video"
        logger.info(f"🎨 [{job_id}] Phase 1: Generating AI scene images ({mode_label}, parallel)...")

        def _gen_scene_img(args):
            i, scene = args
            visual_queries = scene.get("visual_queries", [])
            primary_query = scene.get("visual_query", "")
            narration = scene.get("narration", "")
            if not primary_query and visual_queries:
                primary_query = visual_queries[0]
            if primary_query:
                return i, generate_ai_scene_image(
                    primary_query, i, job_id, narration=narration,
                    video_style=video_style,
                    image_only=is_presentation,
                )
            return i, None

        with ThreadPoolExecutor(max_workers=3) as pool:
            for i, result in pool.map(_gen_scene_img, enumerate(scenes)):
                if result:
                    broll_paths[i] = result

        ai_count = sum(1 for p in broll_paths if p)
        logger.info(f"🎨 [{job_id}] AI images generated: {ai_count}/{len(scenes)}")
    else:
        logger.info(f"   [{job_id}] No REPLICATE_API_TOKEN — skipping AI image generation")

    # ── Phase 2: Pexels Fallback for missing scenes ──
    # OPT: Skip Pexels entirely in presentation mode — images are sufficient for slides
    if is_presentation:
        logger.info(f"📊 [{job_id}] Presentation mode — skipping Pexels B-roll (slides use PNG images)")
    else:
        missing = [i for i in range(len(scenes)) if not broll_paths[i]]
        if missing:
            logger.info(f"📹 [{job_id}] Phase 2: Searching Pexels for {len(missing)} remaining scenes...")
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {}
                for i in missing:
                    scene = scenes[i]
                    visual_queries = scene.get("visual_queries", [])
                    primary_query = scene.get("visual_query", "")

                    if not primary_query and visual_queries:
                        primary_query = visual_queries[0]

                    fallbacks = [q for q in visual_queries if q and q != primary_query]

                    if primary_query:
                        fut = pool.submit(
                            search_broll_footage, primary_query, i, job_id,
                            5, 30, fallbacks
                        )
                        futures[fut] = i

                for fut in futures:
                    idx = futures[fut]
                    try:
                        broll_paths[idx] = fut.result()
                    except Exception as e:
                        logger.error(f"B-roll failed for scene {idx}: {e}")

    found = sum(1 for p in broll_paths if p)
    logger.info(f"🎬 [{job_id}] Total scene visuals: {found}/{len(scenes)}")
    return broll_paths


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 6: Professional Video Composition (FFmpeg)
#   PiP avatar overlay, animated captions, transitions, music mixing
# ═══════════════════════════════════════════════════════════════════

def compose_final_video(
    scenes: List[Dict],
    audio_paths: List[Optional[str]],
    avatar_clips: List[Optional[str]],
    broll_paths: List[Optional[str]],
    job_id: str,
    aspect_ratio: str = "16:9",
    include_captions: bool = True,
    avatar_image_path: str = "",
) -> Optional[str]:
    """
    Professional video composition engine (reference-quality output).
    Features:
      - Picture-in-Picture: avatar talking head overlaid on B-roll
      - Animated captions at bottom of frame
      - Smooth scene transitions (fade/dissolve)
      - Background music mixed under narration
    """
    import subprocess
    import traceback as _tb

    logger.info(f"🎬 [{job_id}] compose_final_video (PRO) called: {len(scenes)} scenes")

    output_path = WORK_DIR / f"{job_id}_final.mp4"

    # Resolution
    resolutions = {
        "16:9": (1920, 1080),
        "9:16": (1080, 1920),
        "1:1": (1080, 1080),
    }
    width, height = resolutions.get(aspect_ratio, (1920, 1080))
    FPS = 30
    TRANSITION_DURATION = 0.8  # seconds of crossfade between scenes
    logger.info(f"🖥️ [{job_id}] Resolution: {width}x{height}, FPS: {FPS}")

    # Check ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except Exception as e:
        err = f"ffmpeg not found: {e}"
        logger.error(f"❌ [{job_id}] {err}")
        update_job_status(job_id, status="failed", error=err)
        return None

    # Choose font path — use Inter if available, else system default
    font_file = FONT_PATH if Path(FONT_PATH).exists() else ""
    if font_file:
        escaped_font = font_file.replace(chr(92), '/').replace(':', '\\:')
        font_opt = f"fontfile='{escaped_font}'"
    else:
        font_opt = ""

    scene_files = []

    for i, scene in enumerate(scenes):
        try:
            duration = scene.get("duration_estimate", 10)
            audio_path = audio_paths[i] if i < len(audio_paths) else None
            broll_path = broll_paths[i] if i < len(broll_paths) else None
            avatar_clip = avatar_clips[i] if i < len(avatar_clips) else None

            scene_out = WORK_DIR / f"{job_id}_scene_{i}.mp4"
            logger.info(f"🎬 [{job_id}] Scene {i}/{len(scenes)}: dur={duration}s, "
                        f"audio={'yes' if audio_path else 'no'}, "
                        f"broll={'yes' if broll_path else 'no'}, "
                        f"avatar={'yes' if avatar_clip else 'no'}")
            update_job_status(job_id, progress=82 + int(i / len(scenes) * 10),
                              stage=f"Composing scene {i+1}/{len(scenes)}...")

            # ── Detect if avatar clip has its own audio (SadTalker bakes it in) ──
            avatar_has_audio = False
            avatar_native_fps = FPS
            if avatar_clip and Path(avatar_clip).exists():
                try:
                    # Probe avatar clip for audio streams and native FPS
                    probe_json = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-print_format", "json",
                         "-show_streams", str(avatar_clip)],
                        capture_output=True, text=True, timeout=10
                    )
                    import json as _json
                    probe_data = _json.loads(probe_json.stdout)
                    for stream in probe_data.get("streams", []):
                        if stream.get("codec_type") == "audio":
                            avatar_has_audio = True
                        if stream.get("codec_type") == "video":
                            # Extract native FPS (e.g. "25/1" -> 25.0)
                            fps_str = stream.get("r_frame_rate", "25/1")
                            if "/" in fps_str:
                                num, den = fps_str.split("/")
                                avatar_native_fps = float(num) / float(den) if float(den) > 0 else FPS
                            else:
                                avatar_native_fps = float(fps_str)
                    logger.info(f"   [{job_id}] Scene {i}: Avatar native FPS={avatar_native_fps:.1f}, has_audio={avatar_has_audio}")
                except Exception as probe_err:
                    logger.warning(f"   [{job_id}] Scene {i}: Avatar probe failed: {probe_err}")

            # Determine actual duration from audio if available
            actual_duration = duration
            if audio_path and Path(audio_path).exists():
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
                        capture_output=True, text=True, timeout=10
                    )
                    actual_duration = float(probe.stdout.strip())
                    logger.info(f"   [{job_id}] Scene {i}: Audio duration = {actual_duration:.1f}s")
                except Exception:
                    pass

            # ═══════════════════════════════════════════════════════════
            # FAST PATH: Lip-sync avatar clip exists
            # SadTalker output already has audio+video perfectly synced.
            # Just scale the video to fit our frame — do NOT re-encode
            # the timing, do NOT force a different FPS, do NOT use
            # separate audio. This preserves exact lip-sync.
            # ═══════════════════════════════════════════════════════════
            if avatar_clip and Path(avatar_clip).exists():
                # Use avatar's native FPS for output to avoid frame duplication
                scene_fps = int(round(avatar_native_fps)) if avatar_native_fps > 0 else FPS

                cmd = ["ffmpeg", "-y"]

                # Input 0: avatar clip (video + synced audio from SadTalker)
                cmd += ["-i", str(avatar_clip)]

                # Build filter: scale to frame, keep native FPS
                vf_filter = (
                    f"[0:v]scale={width}:{height}:"
                    f"force_original_aspect_ratio=decrease:flags=lanczos,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0f0f2e,"
                    f"setsar=1[outv]"
                )

                cmd += ["-filter_complex", vf_filter, "-map", "[outv]"]

                # Audio: prefer avatar's own audio (perfectly synced by SadTalker)
                # Fall back to separate TTS audio only if avatar has no audio track
                if avatar_has_audio:
                    cmd += ["-map", "0:a"]
                    logger.info(f"   [{job_id}] Scene {i}: Using avatar's own synced audio")
                elif audio_path and Path(audio_path).exists():
                    cmd += ["-i", str(audio_path), "-map", "1:a"]
                    logger.info(f"   [{job_id}] Scene {i}: Avatar has no audio, using separate TTS")

                cmd += [
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "20",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    str(scene_out)
                ]

                logger.info(f"   [{job_id}] Scene {i}: Running ffmpeg (lip-sync fast path, fps={scene_fps})...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

                if result.returncode != 0:
                    logger.warning(f"   [{job_id}] Scene {i}: Lip-sync fast path failed: {result.stderr[-400:]}")
                    # Fallback: simple re-encode without complex filter
                    fb_cmd = [
                        "ffmpeg", "-y", "-i", str(avatar_clip),
                        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
                               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#0f0f2e,setsar=1",
                        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(scene_out)
                    ]
                    fb_result = subprocess.run(fb_cmd, capture_output=True, text=True, timeout=120)
                    if fb_result.returncode != 0:
                        logger.error(f"   [{job_id}] Scene {i}: Fallback also failed: {fb_result.stderr[-300:]}")

            else:
                # ═══════════════════════════════════════════════════════
                # STANDARD PATH: No lip-sync clip (static image or no avatar)
                # ═══════════════════════════════════════════════════════
                cmd = ["ffmpeg", "-y"]
                filter_parts = []
                input_idx = 0

                # Input 0: Background (b-roll or solid color)
                if broll_path and Path(broll_path).exists():
                    cmd += ["-stream_loop", "-1", "-i", str(broll_path)]
                    filter_parts.append(
                        f"[{input_idx}:v]scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
                        f"crop={width}:{height},setsar=1,fps={FPS}[bg]"
                    )
                else:
                    cmd += [
                        "-f", "lavfi",
                        "-i", f"color=c=#0f0f2e:s={width}x{height}:r={FPS}:d={actual_duration}"
                    ]
                    filter_parts.append(f"[{input_idx}:v]fps={FPS}[bg]")
                input_idx += 1

                # Input 1: Audio narration
                has_audio = False
                if audio_path and Path(audio_path).exists():
                    cmd += ["-i", str(audio_path)]
                    audio_input_idx = input_idx
                    has_audio = True
                    input_idx += 1

                # Input 2: Static avatar image (if available)
                has_avatar_img = False
                if avatar_image_path and Path(avatar_image_path).exists():
                    cmd += ["-loop", "1", "-i", str(avatar_image_path)]
                    avatar_input_idx = input_idx
                    has_avatar_img = True
                    input_idx += 1

                if has_avatar_img:
                    filter_parts.append(
                        f"[{avatar_input_idx}:v]scale={width}:{height}:"
                        f"force_original_aspect_ratio=increase:flags=lanczos,"
                        f"crop={width}:{height},setsar=1,"
                        f"fps={FPS}[avatar]"
                    )
                    filter_parts.append(
                        f"[bg][avatar]overlay=0:0:format=auto[composed]"
                    )
                    current_label = "composed"
                else:
                    current_label = "bg"

                filter_parts.append(f"[{current_label}]null[outv]")
                full_filter = ";\n".join(filter_parts)

                cmd += ["-filter_complex", full_filter, "-map", "[outv]"]
                if has_audio:
                    cmd += ["-map", f"{audio_input_idx}:a"]
                cmd += [
                    "-t", str(actual_duration),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-c:a", "aac", "-b:a", "192k",
                    "-r", str(FPS),
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(scene_out)
                ]

                logger.info(f"   [{job_id}] Scene {i}: Running ffmpeg (static/broll path)...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

                if result.returncode != 0:
                    logger.warning(f"   [{job_id}] Scene {i}: Composition failed: {result.stderr[-500:]}")
                    # Minimal fallback
                    fallback_cmd = ["ffmpeg", "-y"]
                    if avatar_image_path and Path(avatar_image_path).exists():
                        fallback_cmd += ["-loop", "1", "-i", str(avatar_image_path)]
                    elif broll_path and Path(broll_path).exists():
                        fallback_cmd += ["-i", str(broll_path)]
                    else:
                        fallback_cmd += ["-f", "lavfi", "-i", f"color=c=#141428:s={width}x{height}:r={FPS}:d={actual_duration}"]
                    if audio_path and Path(audio_path).exists():
                        fallback_cmd += ["-i", str(audio_path)]
                    fallback_cmd += [
                        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height},setsar=1",
                        "-t", str(actual_duration),
                        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                        "-c:a", "aac", "-b:a", "128k",
                        "-movflags", "+faststart",
                        str(scene_out)
                    ]
                    subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=120)

            if scene_out.exists() and scene_out.stat().st_size > 0:
                scene_files.append(scene_out)
                logger.info(f"✅ [{job_id}] Scene {i} composed ({scene_out.stat().st_size} bytes)")
            else:
                logger.error(f"❌ [{job_id}] Scene {i}: output file missing or empty")

        except Exception as e:
            logger.error(f"❌ [{job_id}] Scene {i} failed: {e}\n{_tb.format_exc()}")

    if not scene_files:
        err = "No scene clips were created — all scenes failed"
        logger.error(f"❌ [{job_id}] {err}")
        update_job_status(job_id, status="failed", error=err)
        return None

    # ── Concatenate scenes (sync-safe: no xfade overlap) ──
    # IMPORTANT: We use concat-demuxer instead of xfade because:
    #  - xfade shortens video by TRANSITION_DURATION per join but audio stays
    #    full-length → cumulative A/V drift that breaks lip-sync
    #  - xfade blends two avatar faces together → ugly visual glitch
    # Instead, each scene gets a short fade-out/fade-in for smooth transitions
    # while preserving exact per-clip A/V synchronization.
    try:
        update_job_status(job_id, progress=93, stage="Joining scenes...")
        logger.info(f"🔗 [{job_id}] Joining {len(scene_files)} scenes (sync-safe concat)...")

        FADE_DUR = 0.3  # seconds of fade-in/out per scene edge

        if len(scene_files) == 1:
            pre_music_path = scene_files[0]
        else:
            pre_music_path = WORK_DIR / f"{job_id}_pre_music.mp4"

            # Step 1: Add fade-in/out to each scene for smooth visual transitions
            faded_files = []
            for idx_f, sf in enumerate(scene_files):
                faded_out = WORK_DIR / f"{job_id}_faded_{idx_f}.mp4"
                try:
                    # Get scene duration for fade-out offset
                    dur_probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(sf)],
                        capture_output=True, text=True, timeout=10
                    )
                    sdur = float(dur_probe.stdout.strip())
                except Exception:
                    sdur = 10.0

                fade_out_start = max(0, sdur - FADE_DUR)
                # Build fade filter: fade-in at start, fade-out at end
                # First scene: no fade-in; Last scene: no fade-out
                vf_parts = []
                af_parts = []
                if idx_f > 0:
                    vf_parts.append(f"fade=t=in:st=0:d={FADE_DUR}")
                    af_parts.append(f"afade=t=in:st=0:d={FADE_DUR}")
                if idx_f < len(scene_files) - 1:
                    vf_parts.append(f"fade=t=out:st={fade_out_start}:d={FADE_DUR}")
                    af_parts.append(f"afade=t=out:st={fade_out_start}:d={FADE_DUR}")

                if vf_parts:
                    fade_cmd = [
                        "ffmpeg", "-y", "-i", str(sf),
                        "-vf", ",".join(vf_parts),
                        "-af", ",".join(af_parts),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                        "-c:a", "aac", "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        str(faded_out)
                    ]
                    r = subprocess.run(fade_cmd, capture_output=True, text=True, timeout=120)
                    if r.returncode == 0 and faded_out.exists():
                        faded_files.append(faded_out)
                    else:
                        logger.warning(f"   [{job_id}] Fade for scene {idx_f} failed, using raw clip")
                        faded_files.append(sf)
                else:
                    faded_files.append(sf)

            # Step 2: Concat-demuxer join (no frame overlap, preserves A/V sync)
            concat_file = WORK_DIR / f"{job_id}_concat.txt"
            with open(concat_file, "w") as f:
                for sf in faded_files:
                    f.write(f"file '{str(sf).replace(chr(92), '/')}'\n")

            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-movflags", "+faststart",
                str(pre_music_path)
            ]
            logger.info(f"   [{job_id}] Running concat-demuxer join...")
            result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=300)

            if result.returncode != 0:
                logger.warning(f"   [{job_id}] Concat copy failed, trying re-encode: {result.stderr[-300:]}")
                # Fallback: re-encode concat
                concat_cmd_reencode = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    str(pre_music_path)
                ]
                subprocess.run(concat_cmd_reencode, capture_output=True, timeout=300)

            # Clean up faded intermediates
            for ff in faded_files:
                if ff not in scene_files:
                    try:
                        ff.unlink()
                    except Exception:
                        pass

        # ── Mix background music ──
        if pre_music_path and Path(str(pre_music_path)).exists():
            # Find a music track
            music_file = None
            if MUSIC_DIR.exists():
                for ext in ("*.mp3", "*.m4a", "*.wav"):
                    tracks = list(MUSIC_DIR.glob(ext))
                    if tracks:
                        music_file = tracks[0]
                        break

            if music_file:
                logger.info(f"🎵 [{job_id}] Mixing background music: {music_file.name}")
                update_job_status(job_id, progress=96, stage="Mixing background music...")

                # Get video duration
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(pre_music_path)],
                        capture_output=True, text=True, timeout=10
                    )
                    video_duration = float(probe.stdout.strip())
                except Exception:
                    video_duration = 60

                music_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(pre_music_path),
                    "-stream_loop", "-1", "-i", str(music_file),
                    "-filter_complex",
                    f"[1:a]volume=0.08,afade=t=in:d=2,afade=t=out:st={max(0, video_duration-3)}:d=3[music];"
                    f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[outa]",
                    "-map", "0:v",
                    "-map", "[outa]",
                    "-t", str(video_duration),
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart",
                    str(output_path)
                ]

                result = subprocess.run(music_cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    logger.warning(f"   [{job_id}] Music mixing failed, using video without music")
                    import shutil
                    shutil.copy2(str(pre_music_path), str(output_path))
            else:
                # No music available — copy pre_music as final
                import shutil
                if str(pre_music_path) != str(output_path):
                    shutil.copy2(str(pre_music_path), str(output_path))
                logger.info(f"   [{job_id}] No background music found, using video as-is")

        # Cleanup temp scene files
        for sf in scene_files:
            try:
                sf.unlink()
            except Exception:
                pass
        for tmp in WORK_DIR.glob(f"{job_id}_scene_*.mp4"):
            try:
                tmp.unlink()
            except Exception:
                pass
        for tmp in [WORK_DIR / f"{job_id}_pre_music.mp4", WORK_DIR / f"{job_id}_concat.txt"]:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

        if output_path.exists() and output_path.stat().st_size > 0:
            file_size = output_path.stat().st_size
            size_mb = file_size / (1024 * 1024)
            logger.info(f"✅ [{job_id}] Final video composed: {output_path} ({size_mb:.1f} MB)")
            return str(output_path)
        else:
            err = "Video composition completed but output file missing"
            logger.error(f"❌ [{job_id}] {err}")
            update_job_status(job_id, status="failed", error=err)
            return None

    except Exception as e:
        err_detail = _tb.format_exc()
        err = f"Video composition failed: {e}"
        logger.error(f"❌ [{job_id}] {err}\n{err_detail}")
        update_job_status(job_id, status="failed", error=err)
        return None


# ═══════════════════════════════════════════════════════════════════
# ▸ Stage 7: Full Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════
# Persistent topic → video mapping (survives server restarts)
# ═══════════════════════════════════════════════════════════════════
_TOPIC_MAP_FILE = WORK_DIR / "_video_topics.json"

def _load_topic_map() -> dict:
    """Load topic→video mapping from persistent file."""
    try:
        if _TOPIC_MAP_FILE.exists():
            import json
            return json.loads(_TOPIC_MAP_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_topic_video(topic: str, video_filename: str, user_id: str = ""):
    """Save a topic→video mapping to the persistent file."""
    try:
        import json
        mapping = _load_topic_map()
        key = topic.strip().lower()
        mapping[key] = {
            "filename": video_filename,
            "topic": topic,
            "user_id": user_id,
        }
        _TOPIC_MAP_FILE.write_text(json.dumps(mapping, indent=2))
    except Exception as e:
        logger.warning(f"Could not save topic mapping: {e}")

def find_video_by_topic(topic: str) -> Optional[dict]:
    """Find a video for a given topic. Returns dict with url + scene data, or None."""
    import json
    key = topic.strip().lower()
    
    def _build_result(video_file: str) -> Optional[dict]:
        """Read meta file for a video and return full result dict."""
        video_path = WORK_DIR / video_file
        if not (video_path.exists() and video_path.stat().st_size > 1000):
            return None
        url = f"/static/avatar_video_temp/{video_file}"
        # Try to read scene data from .meta.json
        job_id = video_file.replace("_final.mp4", "")
        meta_path = WORK_DIR / f"{job_id}_final.meta.json"
        script_path = WORK_DIR / f"{job_id}_script.json"
        scene_timings = []
        scenes = []
        video_mode = "presentation"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                scene_timings = meta.get("scene_timings", [])
                scenes = meta.get("scenes", [])
                video_mode = meta.get("video_mode", "presentation")
            except Exception:
                pass
        # Fallback: _script.json has narration text even if meta is old
        if not scenes and script_path.exists():
            try:
                sdata = json.loads(script_path.read_text())
                scenes = sdata.get("scenes", [])
            except Exception:
                pass
        return {
            "url": url,
            "topic": topic,
            "video_mode": video_mode,
            "scene_timings": scene_timings,
            "scenes": scenes,
        }

    # 1. Check persistent mapping file first (fastest)
    mapping = _load_topic_map()
    entry = mapping.get(key)
    if entry:
        result = _build_result(entry["filename"])
        if result:
            return result

    # 2. Fallback: scan all .meta.json files for a matching topic
    for meta_file in WORK_DIR.glob("*_final.meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            meta_topic = meta.get("topic", "")
            if meta_topic and meta_topic.strip().lower() == key:
                job_id = meta_file.name.replace("_final.meta.json", "")
                video_file = f"{job_id}_final.mp4"
                result = _build_result(video_file)
                if result:
                    _save_topic_video(meta_topic, video_file)
                    return result
        except Exception:
            pass

    return None


# Bootstrap: populate topic map from existing .meta.json files on startup
# Also write _script.json for completed jobs in _jobs dict
def _bootstrap_topic_map():
    """Scan all existing .meta.json and _script.json files and populate the topic→video mapping.
    Also persist scene data from _jobs dict to disk."""
    import json
    mapping = _load_topic_map()
    count = 0

    # 1. Scan .meta.json files
    for meta_file in WORK_DIR.glob("*_final.meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            topic = meta.get("topic", "")
            if topic:
                key = topic.strip().lower()
                job_id = meta_file.name.replace("_final.meta.json", "")
                video_file = f"{job_id}_final.mp4"
                video_path = WORK_DIR / video_file
                if video_path.exists() and video_path.stat().st_size > 1000:
                    if key not in mapping:
                        mapping[key] = {
                            "filename": video_file,
                            "topic": topic,
                            "user_id": meta.get("user_id", ""),
                        }
                        count += 1
        except Exception:
            pass

    # 2. Scan _script.json files (have topic + scene data)
    for script_file in WORK_DIR.glob("*_script.json"):
        try:
            sdata = json.loads(script_file.read_text())
            topic = sdata.get("topic", "")
            if topic:
                key = topic.strip().lower()
                job_id = script_file.name.replace("_script.json", "")
                video_file = f"{job_id}_final.mp4"
                video_path = WORK_DIR / video_file
                if video_path.exists() and video_path.stat().st_size > 1000:
                    if key not in mapping:
                        mapping[key] = {
                            "filename": video_file,
                            "topic": topic,
                        }
                        count += 1
        except Exception:
            pass

    if count > 0:
        _TOPIC_MAP_FILE.write_text(json.dumps(mapping, indent=2))
        logger.info(f"📋 Bootstrapped {count} new topic→video mappings (total: {len(mapping)})")


# In-memory job store for status tracking
_jobs: Dict[str, Dict] = {}

_bootstrap_topic_map()


def get_job_status(job_id: str) -> Optional[Dict]:
    return _jobs.get(job_id)


def update_job_status(job_id: str, **kwargs):
    if job_id not in _jobs:
        _jobs[job_id] = {}
    _jobs[job_id].update(kwargs)
    
    # Auto-persist scene data to disk when job completes
    if kwargs.get("status") == "completed" and _jobs[job_id].get("scene_timings"):
        try:
            import json
            script_path = WORK_DIR / f"{job_id}_script.json"
            if not script_path.exists():
                jdata = _jobs[job_id]
                json.dump({
                    "scenes": [{"narration": st.get("narration", ""), "text_overlay": st.get("text_overlay", "")}
                               for st in jdata.get("scene_timings", [])],
                    "scene_count": jdata.get("scene_count", 0),
                }, script_path.open("w"))
        except Exception:
            pass


def get_avatar_image_path(avatar_id: str) -> str:
    """Resolve avatar ID to image file path. Auto-generates if missing."""
    # Check custom upload directory first
    # Handle both 'custom_xxx' (from upload endpoint) and raw IDs
    if avatar_id.startswith("custom_"):
        custom_path = AVATAR_DIR / f"{avatar_id}.png"
    else:
        custom_path = AVATAR_DIR / f"custom_{avatar_id}.png"
    if custom_path.exists():
        logger.info(f"✅ Found custom avatar: {custom_path}")
        return str(custom_path)

    # Check pre-made avatars
    for avatar in DEFAULT_AVATARS:
        if avatar["id"] == avatar_id:
            path = AVATAR_DIR / avatar["image"]
            if path.exists():
                return str(path)
            # Also check by avatar_id.png
            alt_path = AVATAR_DIR / f"{avatar_id}.png"
            if alt_path.exists():
                return str(alt_path)

    # Fallback to first available avatar
    for avatar in DEFAULT_AVATARS:
        path = AVATAR_DIR / avatar["image"]
        if path.exists():
            return str(path)

    # Check any generated avatar
    gen_path = AVATAR_DIR / f"{avatar_id}.png"
    if gen_path.exists():
        return str(gen_path)

    # Auto-generate avatar face using Replicate FLUX Schnell
    logger.info(f"🧑 No avatar image for '{avatar_id}' — auto-generating with AI...")
    generated = generate_avatar_face(avatar_id)
    if generated:
        return generated

    logger.warning(f"No avatar image found for '{avatar_id}' and generation failed")
    return ""


def generate_avatar_video(
    topic: str,
    content: str = "",
    user_id: str = "",
    avatar_id: str = "teacher_female_1",
    language: str = "en",
    voice: str = "nova",
    style: str = "educational",
    aspect_ratio: str = "16:9",
    include_captions: bool = True,
    include_broll: bool = True,
    job_id: str = "",
    video_style: str = "educational_diagram",
    video_mode: str = "presentation",
) -> Dict:
    """
    Full avatar video generation pipeline.
    This is the main entry point — runs synchronously (call from background task).
    Returns dict with status, video_url, scenes, etc.
    """
    if not job_id:
        job_id = hashlib.md5(f"{user_id}:{topic}:{language}:{style}:{time.time()}".encode()).hexdigest()[:12]

    update_job_status(job_id, status="starting", progress=0, stage="Initializing...")
    # Set current user for Replicate usage tracking
    _tls.current_user_id = user_id

    try:
        # ── Stage 1: Generate script ──
        logger.info(f"🚀 [{job_id}] Starting pipeline for topic='{topic}', avatar={avatar_id}, lang={language}")
        update_job_status(job_id, status="processing", progress=10, stage="Writing script...")
        script = generate_video_script(topic, content, language, style)
        if not script:
            err = "Script generation failed — OpenAI returned empty"
            logger.error(f"❌ [{job_id}] {err}")
            update_job_status(job_id, status="failed", error=err)
            return {"status": "failed", "error": err, "job_id": job_id}
        logger.info(f"✅ [{job_id}] Stage 1 done: script={len(script)} chars")

        # ── Stage 2: Plan scenes ──
        update_job_status(job_id, progress=20, stage="Planning scenes...")
        scenes = plan_video_scenes(script, style, language, video_style=video_style)
        if not scenes:
            err = "Scene planning failed — no scenes returned"
            logger.error(f"❌ [{job_id}] {err}")
            update_job_status(job_id, status="failed", error=err)
            return {"status": "failed", "error": err, "job_id": job_id}
        logger.info(f"✅ [{job_id}] Stage 2 done: {len(scenes)} scenes planned")

        # Persist scene data to disk early (survives crashes and restarts)
        try:
            import json as _json
            script_path = WORK_DIR / f"{job_id}_script.json"
            _json.dump({
                "topic": topic,
                "script": script,
                "scenes": [{"narration": s.get("narration", ""), "text_overlay": s.get("text_overlay", ""),
                            "duration_estimate": s.get("duration_estimate", 10)} for s in scenes],
                "scene_count": len(scenes),
            }, script_path.open("w"))
            logger.info(f"💾 [{job_id}] Saved script data to {script_path.name}")
        except Exception:
            pass

        # ── Stage 3: Generate audio for all scenes ──
        update_job_status(job_id, progress=30, stage="Generating voice narration...")
        audio_paths = generate_all_scene_audio(scenes, job_id, voice, language)
        audio_count = sum(1 for p in audio_paths if p)
        logger.info(f"✅ [{job_id}] Stage 3 done: {audio_count}/{len(scenes)} audio files generated")
        for idx, ap in enumerate(audio_paths):
            logger.info(f"   Audio[{idx}]: {ap}")

        # ── Stages 4+5: Avatar lip-sync AND scene images (run concurrently) ──
        # OPT: These are independent — lip-sync needs audio, images need scene text.
        # Running them in parallel saves the full duration of the shorter stage.
        avatar_image = get_avatar_image_path(avatar_id)
        avatar_clips = [None] * len(scenes)
        broll_paths = [None] * len(scenes)
        is_face = _is_face_avatar(avatar_id)
        use_did = False  # Always use SadTalker/Replicate for lip-sync (D-ID disabled)

        # ── Define Stage 4 worker (lip-sync) ──
        def _run_stage4():
            nonlocal avatar_clips
            if video_style == "animated_explainer":
                logger.info(f"🎨 [{job_id}] Stage 4: Skipping avatar (animated_explainer style — voiceover only)")
                update_job_status(job_id, progress=45, stage="Animated explainer — skipping avatar...")

            elif not is_face:
                logger.info(f"🍌 [{job_id}] Stage 4: Object avatar '{avatar_id}' — voiceover mode (no lip-sync)")
                update_job_status(job_id, progress=45, stage="Object avatar — voiceover mode...")

            elif use_did:
                logger.info(f"🎬 [{job_id}] Stage 4: Using D-ID for lip-sync (avatar='{avatar_id}')")
                update_job_status(job_id, progress=45, stage="Creating AI avatar via D-ID...")
                try:
                    from did_service import upload_image_to_did
                    avatar_url = upload_image_to_did(avatar_image) if avatar_image else ""
                    logger.info(f"📤 [{job_id}] Avatar uploaded to D-ID: {avatar_url[:80]}...")
                except Exception as e:
                    logger.error(f"❌ [{job_id}] Failed to upload avatar to D-ID: {e}")
                    avatar_url = ""
                if avatar_url:
                    avatar_clips[:] = generate_all_did_talking_heads(
                        scenes, job_id, avatar_image_url=avatar_url, language=language,
                    )
                    did_count = sum(1 for c in avatar_clips if c)
                    logger.info(f"✅ [{job_id}] D-ID: {did_count}/{len(scenes)} clips generated")
                    if did_count == 0 and avatar_image and REPLICATE_API_TOKEN:
                        logger.warning(f"⚠️ [{job_id}] D-ID produced 0 clips — falling back to SadTalker")
                        update_job_status(job_id, progress=50, stage="D-ID failed, using SadTalker fallback...")
                        avatar_clips[:] = generate_all_talking_heads(avatar_image, audio_paths, job_id)
                else:
                    logger.warning(f"⚠️ [{job_id}] D-ID avatar upload failed, falling back to SadTalker")
                    if avatar_image and REPLICATE_API_TOKEN:
                        avatar_clips[:] = generate_all_talking_heads(avatar_image, audio_paths, job_id)

            elif avatar_image and REPLICATE_API_TOKEN:
                logger.info(f"📋 [{job_id}] Stage 4: Using SadTalker for lip-sync")
                update_job_status(job_id, progress=45, stage="Creating AI avatar via SadTalker...")
                avatar_clips[:] = generate_all_talking_heads(avatar_image, audio_paths, job_id)

            else:
                update_job_status(job_id, progress=45, stage="Skipping avatar (no API keys)...")
                logger.info(f"⏭️ [{job_id}] Skipping talking head generation (no DID/Replicate keys)")

        # ── Define Stage 5 worker (scene images) ──
        def _run_stage5():
            nonlocal broll_paths
            logger.info(f"📋 [{job_id}] Stage 5: include_broll={include_broll}, PEXELS_KEY={'set' if PEXELS_API_KEY else 'NOT SET'}")
            if include_broll and PEXELS_API_KEY:
                update_job_status(job_id, progress=65, stage="Finding background footage...")
                broll_paths[:] = search_all_broll(scenes, job_id, video_style=video_style, video_mode=video_mode)
            else:
                update_job_status(job_id, progress=65, stage="Skipping B-roll...")
                logger.info(f"⏭️ [{job_id}] Skipping B-roll search")

        # ── Run Stages 4+5 concurrently ──
        logger.info(f"🚀 [{job_id}] Running Stage 4 (lip-sync) + Stage 5 (scene images) concurrently...")
        update_job_status(job_id, progress=40, stage="Creating avatar + scene images (parallel)...")
        with ThreadPoolExecutor(max_workers=2) as stage_pool:
            s4_future = stage_pool.submit(_run_stage4)
            s5_future = stage_pool.submit(_run_stage5)
            # Wait for both to complete
            s4_future.result()
            s5_future.result()
        logger.info(f"✅ [{job_id}] Stages 4+5 complete: {sum(1 for c in avatar_clips if c)} avatar clips, {sum(1 for b in broll_paths if b)} scene images")

        # ── Stage 6: Compose final video ──
        logger.info(f"🎬 [{job_id}] Stage 6: Composing video with {len(scenes)} scenes, {audio_count} audio files")
        update_job_status(job_id, progress=80, stage="Composing final video...")
        video_path = compose_final_video(
            scenes, audio_paths, avatar_clips, broll_paths,
            job_id, aspect_ratio, include_captions,
            avatar_image_path=avatar_image or "",
        )

        if not video_path:
            err = "Video composition failed — compose_final_video returned None (check server logs for traceback)"
            logger.error(f"❌ [{job_id}] {err}")
            update_job_status(job_id, status="failed", error=err)
            return {"status": "failed", "error": err, "job_id": job_id}
        logger.info(f"✅ [{job_id}] Stage 6 done: video_path={video_path}")

        # ── Stage 7: Upload to storage ──
        update_job_status(job_id, progress=95, stage="Uploading video...")

        # Build scene timing data for frontend side text panel
        # Use ACTUAL clip durations (not estimates) for accurate seek
        # Priority: avatar clip duration > audio duration > estimate
        scene_timings = []
        cumulative = 0.0
        for idx_s, sc in enumerate(scenes):
            real_dur = sc.get("duration_estimate", 10)
            # Prefer avatar clip duration (what's actually in the final video)
            clip_file = avatar_clips[idx_s] if idx_s < len(avatar_clips) else None
            audio_file = audio_paths[idx_s] if idx_s < len(audio_paths) else None
            probe_file = None
            if clip_file and Path(clip_file).exists():
                probe_file = clip_file
            elif audio_file and Path(audio_file).exists():
                probe_file = audio_file
            if probe_file:
                try:
                    _p = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(probe_file)],
                        capture_output=True, text=True, timeout=10
                    )
                    real_dur = float(_p.stdout.strip())
                except Exception:
                    pass
            scene_timings.append({
                "index": idx_s,
                "start_time": round(cumulative, 2),
                "end_time": round(cumulative + real_dur, 2),
                "narration": sc.get("narration", ""),
                "text_overlay": sc.get("text_overlay", ""),
            })
            cumulative += real_dur

        result = {
            "status": "completed",
            "job_id": job_id,
            "video_path": video_path,
            "video_url": "",  # Will be set after Supabase upload
            "script": script,
            "scenes": scenes,
            "scene_timings": scene_timings,
            "scene_count": len(scenes),
            "duration_estimate": sum(s.get("duration_estimate", 10) for s in scenes),
        }

        update_job_status(job_id, status="completed", progress=100, stage="Done!",
                          video_path=video_path, video_url="",
                          scene_count=len(scenes),
                          scene_timings=scene_timings,
                          duration_estimate=sum(s.get("duration_estimate", 10) for s in scenes))

        # Save topic metadata + scene data alongside the video for the list endpoint
        try:
            import json as _json
            meta_path = WORK_DIR / f"{job_id}_final.meta.json"
            _json.dump({
                "topic": topic,
                "avatar_id": avatar_id,
                "language": language,
                "video_mode": video_mode,
                "scene_timings": scene_timings,
                "scenes": [{"narration": s.get("narration", ""), "text_overlay": s.get("text_overlay", "")} for s in scenes],
                "script": script,
                "scene_count": len(scenes),
                "status": "completed",
            }, meta_path.open("w"))
        except Exception:
            pass

        # Persist topic → video mapping for instant lookup
        _save_topic_video(topic, f"{job_id}_final.mp4", user_id)

        return result

    except Exception as e:
        logger.error(f"Avatar video pipeline failed: {e}")
        update_job_status(job_id, status="failed", error=str(e))
        return {"status": "failed", "error": str(e), "job_id": job_id}


# ═══════════════════════════════════════════════════════════════════
# ▸ Utility: List available avatars
# ═══════════════════════════════════════════════════════════════════

def list_available_avatars() -> List[Dict]:
    """List all available avatars (pre-made + custom uploaded)."""
    avatars = []

    # Pre-made avatars
    for av in DEFAULT_AVATARS:
        path = AVATAR_DIR / av["image"]
        avatars.append({
            **av,
            "available": path.exists(),
            "type": "premade",
        })

    # Custom uploaded avatars
    for f in AVATAR_DIR.glob("custom_*.png"):
        avatar_id = f.stem  # e.g., "custom_abc123"
        avatars.append({
            "id": avatar_id,
            "name": avatar_id.replace("custom_", "").replace("_", " ").title(),
            "description": "Custom uploaded avatar",
            "image": f.name,
            "style": "custom",
            "available": True,
            "type": "custom",
        })

    return avatars


# ═══════════════════════════════════════════════════════════════════
# ▸ Background Batch Video Pre-Generation Worker
# ═══════════════════════════════════════════════════════════════════

import threading as _threading
_cancel_event = _threading.Event()

# ── Persistent batch control file (survives backend restarts) ──
_BATCH_CONTROL_FILE = WORK_DIR / "_batch_control.json"

def _load_batch_control() -> dict:
    """Load persistent batch control state from disk."""
    try:
        if _BATCH_CONTROL_FILE.exists():
            import json
            return json.loads(_BATCH_CONTROL_FILE.read_text())
    except Exception:
        pass
    return {"user_cancelled": False}

def _save_batch_control(state: dict):
    """Save batch control state to disk (persists across restarts)."""
    try:
        import json
        _BATCH_CONTROL_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        logger.error(f"Failed to save batch control state: {e}")

# Load persistent cancel state on startup
_persisted = _load_batch_control()

_batch_worker_status = {
    "running": False,
    "current_topic": "",
    "completed": 0,
    "total": 0,
    "failed": 0,
    "skipped": 0,
    "errors": [],
    "started_at": "",
    "last_completed_at": "",
    "cancelled": _persisted.get("user_cancelled", False),
    "paused": _persisted.get("user_cancelled", False),
    "user_cancelled": _persisted.get("user_cancelled", False),
}


def get_all_topics_without_videos() -> list:
    """
    Discover all topics from local .meta.json files and the _video_topics.json,
    then find which ones DON'T have avatar videos yet.
    Returns list of topic titles that need video generation.
    """
    import json

    existing = _load_topic_map()
    existing_keys = set(existing.keys())

    # Strategy 1: Scan all lesson_cache topics from local meta/script files
    all_topics = set()

    # Scan _script.json files for topics
    for script_file in WORK_DIR.glob("*_script.json"):
        try:
            sdata = json.loads(script_file.read_text())
            topic = sdata.get("topic", "")
            if topic:
                all_topics.add(topic.strip())
        except Exception:
            pass

    # Scan _final.meta.json files for topics
    for meta_file in WORK_DIR.glob("*_final.meta.json"):
        try:
            meta = json.loads(meta_file.read_text())
            topic = meta.get("topic", "")
            if topic:
                all_topics.add(topic.strip())
        except Exception:
            pass

    # Strategy 2: Also include topics from existing mapping (already generated)
    for entry in existing.values():
        topic = entry.get("topic", "")
        if topic:
            all_topics.add(topic.strip())

    # Filter: only topics that DON'T have a valid video
    missing = []
    for topic in sorted(all_topics):
        key = topic.strip().lower()
        if key in existing_keys:
            # Verify the video file actually exists
            entry = existing[key]
            video_file = entry.get("filename", "")
            if video_file and (WORK_DIR / video_file).exists():
                continue  # Already has a valid video
        missing.append(topic)

    return missing


def get_batch_worker_status() -> dict:
    """Return the current status of the background batch worker."""
    status = dict(_batch_worker_status)
    # Always reflect persistent user_cancelled state
    persisted = _load_batch_control()
    status["user_cancelled"] = persisted.get("user_cancelled", False)
    return status


def cancel_batch_worker():
    """Signal the batch worker to stop after the current video.
    Persists user_cancelled to disk so it survives backend restarts."""
    _batch_worker_status["cancelled"] = True
    _batch_worker_status["paused"] = True
    _batch_worker_status["user_cancelled"] = True
    _cancel_event.set()  # Signal immediately
    # Persist to disk — this survives backend restarts
    _save_batch_control({"user_cancelled": True})
    logger.info("🛑 Batch video worker cancellation requested — persisted to disk")


def resume_batch_worker():
    """Clear the persistent user_cancelled flag so auto-scheduler or manual start can proceed."""
    _batch_worker_status["cancelled"] = False
    _batch_worker_status["paused"] = False
    _batch_worker_status["user_cancelled"] = False
    _cancel_event.clear()
    _save_batch_control({"user_cancelled": False})
    logger.info("▶ Batch worker resume requested — persistent cancel flag cleared")


def batch_generate_videos(
    topics: list = None,
    user_id: str = "",
    voice: str = "nova",
    avatar_id: str = "teacher_female_1",
    video_mode: str = "presentation",
):
    """
    Generate avatar videos for a list of topics (or all missing topics).
    Runs synchronously — should be called from a background thread.
    """
    import time

    if topics is None:
        topics = get_all_topics_without_videos()

    if not topics:
        logger.info("✅ All topics already have avatar videos!")
        return

    _cancel_event.clear()  # Reset cancel signal
    # Clear persistent cancel flag when batch is explicitly started
    _save_batch_control({"user_cancelled": False})
    _batch_worker_status.update({
        "running": True,
        "current_topic": "",
        "completed": 0,
        "total": len(topics),
        "failed": 0,
        "skipped": 0,
        "errors": [],
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_completed_at": "",
        "cancelled": False,
        "paused": False,
        "user_cancelled": False,
    })

    logger.info(f"🎬 Batch video worker starting: {len(topics)} topics to generate")

    for i, topic in enumerate(topics):
        if _batch_worker_status["cancelled"] or _cancel_event.is_set():
            logger.info(f"🛑 Batch worker cancelled/paused after {i} videos")
            _batch_worker_status["paused"] = True
            break

        # Skip if video was generated while we were working
        key = topic.strip().lower()
        mapping = _load_topic_map()
        if key in mapping:
            entry = mapping[key]
            video_file = entry.get("filename", "")
            if video_file and (WORK_DIR / video_file).exists():
                _batch_worker_status["skipped"] += 1
                _batch_worker_status["completed"] += 1
                logger.info(f"⏭️ [{i+1}/{len(topics)}] Skipping '{topic}' — already exists")
                continue

        _batch_worker_status["current_topic"] = topic
        logger.info(f"🎬 [{i+1}/{len(topics)}] Generating video for: '{topic}'")

        try:
            import hashlib
            job_id = hashlib.md5(
                f"batch:{topic}:{time.time()}".encode()
            ).hexdigest()[:12]

            result = generate_avatar_video(
                topic=topic,
                content="",  # Let the pipeline search for content
                user_id=user_id,
                avatar_id=avatar_id,
                language="en",
                voice=voice,
                style="educational",
                aspect_ratio="16:9",
                include_captions=True,
                include_broll=True,
                job_id=job_id,
                video_style="educational_diagram",
                video_mode=video_mode,
            )

            if result.get("status") == "completed":
                _batch_worker_status["completed"] += 1
                _batch_worker_status["last_completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"✅ [{i+1}/{len(topics)}] Video generated: '{topic}'")
            else:
                _batch_worker_status["failed"] += 1
                err_msg = result.get("error", "Unknown error")
                _batch_worker_status["errors"].append(f"{topic}: {err_msg}")
                logger.warning(f"❌ [{i+1}/{len(topics)}] Failed for '{topic}': {err_msg}")

        except Exception as e:
            _batch_worker_status["failed"] += 1
            _batch_worker_status["errors"].append(f"{topic}: {str(e)}")
            logger.error(f"❌ [{i+1}/{len(topics)}] Error generating '{topic}': {e}")

        # Brief pause between videos to avoid overloading
        # Also check cancel during the pause for faster response
        for _ in range(4):
            if _cancel_event.is_set():
                break
            time.sleep(0.5)

    was_cancelled = _batch_worker_status["cancelled"] or _cancel_event.is_set()
    _batch_worker_status["running"] = False
    _batch_worker_status["current_topic"] = ""
    if was_cancelled:
        _batch_worker_status["paused"] = True
    logger.info(
        f"{'⏸️ Batch video worker paused' if was_cancelled else '🎉 Batch video worker finished'}: "
        f"{_batch_worker_status['completed']} completed, "
        f"{_batch_worker_status['failed']} failed, "
        f"{_batch_worker_status['skipped']} skipped"
    )
