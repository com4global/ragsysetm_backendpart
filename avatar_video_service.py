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
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = "gpt-4o-mini"

# ── Directories ─────────────────────────────────────────────────────
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
AVATAR_DIR = BASE_DIR / "static" / "avatars"
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
        "id": "teacher_female_1",
        "name": "Professor Maya",
        "description": "Professional female teacher",
        "image": "teacher_female_1.png",
        "style": "professional",
    },
    {
        "id": "teacher_male_1",
        "name": "Dr. James",
        "description": "Academic male professor",
        "image": "teacher_male_1.png",
        "style": "academic",
    },
    {
        "id": "presenter_female_1",
        "name": "Sarah",
        "description": "Casual female presenter",
        "image": "presenter_female_1.png",
        "style": "casual",
    },
    {
        "id": "presenter_male_1",
        "name": "Alex",
        "description": "Modern male presenter",
        "image": "presenter_male_1.png",
        "style": "modern",
    },
    {
        "id": "corporate_female_1",
        "name": "Diana",
        "description": "Corporate female executive",
        "image": "corporate_female_1.png",
        "style": "corporate",
    },
    {
        "id": "corporate_male_1",
        "name": "Michael",
        "description": "Corporate male executive",
        "image": "corporate_male_1.png",
        "style": "corporate",
    },
]


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

    system_prompt = f"""You are an expert video script writer. Write a script for {style_desc}.

Rules:
- Target duration: {duration_target}
- Write in {language} language
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

    # Remove [PAUSE] markers and clean text
    clean_text = text.replace("[PAUSE]", "... ").strip()
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
    """Generate TTS using Sarvam AI for Indian languages."""
    headers = {"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"}
    payload = {
        "inputs": [text[:500]],
        "target_language_code": language,
        "speaker": "meera",
        "model": "bulbul:v1",
        "enable_preprocessing": True,
    }
    resp = requests.post("https://api.sarvam.ai/text-to-speech", json=payload, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        import base64
        audio_b64 = data.get("audios", [""])[0]
        if audio_b64:
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))


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
    Generate a talking head video with lip-sync using Replicate's Wav2Lip.
    Input: avatar image + audio → Output: MP4 video of avatar speaking with synced lips.
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

        if not face_url or not audio_url:
            # Fallback: try with file:// URLs or base64 encoding
            import base64
            with open(avatar_image_path, "rb") as f:
                face_b64 = base64.b64encode(f.read()).decode()
            face_url = f"data:image/png;base64,{face_b64}"

            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode()
            audio_url = f"data:audio/mp3;base64,{audio_b64}"

        result = _replicate_api(
            # devxpy/cog-wav2lip — high quality lip sync
            "8d65e3f4f4298520e079198b493c25adfc43c058ffec924f2aefc8010ed25eef",
            {
                "face": face_url,
                "audio": audio_url,
                "pads": "0 10 0 0",
                "smooth": True,
                "fps": 25,
            },
            timeout=300,
        )

        output = result.get("output")
        if output:
            video_url = str(output)
            resp = requests.get(video_url, stream=True, timeout=120)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"✅ Lip-sync avatar generated for scene {scene_index} ({output_path.stat().st_size} bytes)")
                return str(output_path)

        logger.warning(f"Talking head generation returned no output for scene {scene_index}")
        return None

    except Exception as e:
        logger.error(f"Talking head generation failed for scene {scene_index}: {e}")
        return None


def generate_all_talking_heads(
    avatar_image_path: str,
    audio_paths: List[Optional[str]],
    job_id: str,
) -> List[Optional[str]]:
    """Generate talking head clips for all scenes (sequentially — Replicate rate limits)."""
    avatar_clips = []
    for i, audio_path in enumerate(audio_paths):
        if audio_path:
            clip = generate_talking_head(avatar_image_path, audio_path, i, job_id)
            avatar_clips.append(clip)
        else:
            avatar_clips.append(None)
    return avatar_clips


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
) -> Optional[str]:
    """
    Generate a custom AI scene image using Replicate FLUX Schnell.
    Returns the path to a video clip with Ken Burns zoom effect.
    Falls back gracefully if Replicate is unavailable.

    video_style: "photorealistic" (default) or "animated_explainer" (flat illustration)
    """
    if not REPLICATE_API_TOKEN:
        logger.info(f"   [{job_id}] REPLICATE_API_TOKEN not set — skipping AI image for scene {scene_index}")
        return None

    output_path = WORK_DIR / f"{job_id}_ai_broll_{scene_index}.mp4"
    if output_path.exists() and output_path.stat().st_size > 1000:
        logger.info(f"🎯 AI B-roll {scene_index} cached")
        return str(output_path)

    img_path = WORK_DIR / f"{job_id}_ai_img_{scene_index}.png"
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
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
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
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
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
) -> List[Optional[str]]:
    """
    Get scene visuals for all scenes.
    Phase 1: Try AI-generated images via FLUX Schnell (Replicate).
    Phase 2: Fall back to Pexels stock footage for any missing scenes.
    """
    broll_paths: List[Optional[str]] = [None] * len(scenes)

    # ── Phase 1: AI-Generated Scene Images (FLUX Schnell) ──
    if REPLICATE_API_TOKEN:
        logger.info(f"🎨 [{job_id}] Phase 1: Generating AI scene images via FLUX Schnell...")
        # Run AI generation sequentially (Replicate rate limits concurrent requests)
        for i, scene in enumerate(scenes):
            visual_queries = scene.get("visual_queries", [])
            primary_query = scene.get("visual_query", "")
            narration = scene.get("narration", "")

            if not primary_query and visual_queries:
                primary_query = visual_queries[0]

            if primary_query:
                result = generate_ai_scene_image(
                    primary_query, i, job_id, narration=narration,
                    video_style=video_style,
                )
                if result:
                    broll_paths[i] = result

        ai_count = sum(1 for p in broll_paths if p)
        logger.info(f"🎨 [{job_id}] AI images generated: {ai_count}/{len(scenes)}")
    else:
        logger.info(f"   [{job_id}] No REPLICATE_API_TOKEN — skipping AI image generation")

    # ── Phase 2: Pexels Fallback for missing scenes ──
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
    logger.info(f"🎬 [{job_id}] Total scene visuals: {found}/{len(scenes)} (AI + Pexels)")
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
        escaped_font = font_file.replace(chr(92), '/').replace(':', '\\\\:')
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
            caption_text = scene.get("text_overlay", "")

            scene_out = WORK_DIR / f"{job_id}_scene_{i}.mp4"
            logger.info(f"🎬 [{job_id}] Scene {i}/{len(scenes)}: dur={duration}s, "
                        f"audio={'yes' if audio_path else 'no'}, "
                        f"broll={'yes' if broll_path else 'no'}, "
                        f"avatar={'yes' if avatar_clip else 'no'}")
            update_job_status(job_id, progress=82 + int(i / len(scenes) * 10),
                              stage=f"Composing scene {i+1}/{len(scenes)}...")

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

            # ── Build complex ffmpeg filter graph ──
            cmd = ["ffmpeg", "-y"]
            filter_parts = []
            input_idx = 0

            # Input 0: Background (b-roll or solid color)
            if broll_path and Path(broll_path).exists():
                cmd += ["-stream_loop", "-1", "-i", str(broll_path)]
                # Scale b-roll to fill frame with slight zoom effect
                filter_parts.append(
                    f"[{input_idx}:v]scale={width*2}:{height*2}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height},setsar=1,fps={FPS}[bg]"
                )
            else:
                # Generate gradient background instead of solid color
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

            # Input 2: Avatar PiP (if available)
            has_avatar = False
            if avatar_clip and Path(avatar_clip).exists():
                cmd += ["-stream_loop", "-1", "-i", str(avatar_clip)]
                avatar_input_idx = input_idx
                has_avatar = True
                input_idx += 1

            # ── Build filter graph ──
            if has_avatar:
                # PiP Layout: avatar circle in bottom-right corner
                pip_size = int(min(width, height) * 0.28)  # 28% of smaller dimension
                pip_x = width - pip_size - 20  # 20px from right edge
                pip_y = height - pip_size - 80  # 80px from bottom (room for captions)

                # Scale avatar and make circular with border
                filter_parts.append(
                    f"[{avatar_input_idx}:v]scale={pip_size}:{pip_size}:force_original_aspect_ratio=decrease,"
                    f"pad={pip_size}:{pip_size}:(ow-iw)/2:(oh-ih)/2:color=0x00000000,"
                    f"format=rgba,"
                    f"geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)':"
                    f"a='if(gt(pow((X-{pip_size}/2),2)+pow((Y-{pip_size}/2),2),pow({pip_size}/2-4,2)),0,255)',"
                    f"fps={FPS}[avatar]"
                )

                # Overlay avatar on background
                filter_parts.append(
                    f"[bg][avatar]overlay={pip_x}:{pip_y}:format=auto[composed]"
                )
                current_label = "composed"
            else:
                current_label = "bg"

            # ── Per-word highlighting captions (reference video style) ──
            narration_text = scene.get("narration", caption_text or "")
            if include_captions and narration_text:
                words = narration_text.split()
                if words:
                    caption_fontsize = max(int(height * 0.042), 28)
                    caption_y = int(height * 0.85)
                    word_duration = actual_duration / len(words) if words else actual_duration

                    # Show 3-4 words at a time with the active word highlighted red
                    chunk_size = min(4, max(2, len(words) // max(1, int(actual_duration / 2))))
                    if chunk_size < 2:
                        chunk_size = 3
                    word_chunks = []
                    for ci in range(0, len(words), chunk_size):
                        chunk_words = words[ci:ci + chunk_size]
                        chunk_start = ci * word_duration
                        chunk_end = min((ci + chunk_size) * word_duration, actual_duration)
                        word_chunks.append((chunk_words, chunk_start, chunk_end, ci))

                    # Build drawtext filters for each word in each chunk
                    # Two layers per word: dark bg (inactive) + red bg (active)
                    prev_label = current_label
                    label_counter = 0
                    for ci, (chunk_words, chunk_start, chunk_end, word_offset) in enumerate(word_chunks):
                        for wi, word in enumerate(chunk_words):
                            # Sanitize word for drawtext
                            safe_word = word.replace("'", "").replace(":", "").replace("%", "")
                            safe_word = safe_word.replace("\\", "").replace('"', '')
                            safe_word = safe_word.replace(";", "").replace("[", "").replace("]", "")
                            if not safe_word:
                                continue

                            word_abs_idx = word_offset + wi
                            word_start = word_abs_idx * word_duration
                            word_end = (word_abs_idx + 1) * word_duration

                            # Calculate x position: center the chunk, offset each word
                            char_w = caption_fontsize * 0.55
                            total_chunk_w = sum(len(w) for w in chunk_words) * char_w + (len(chunk_words) - 1) * caption_fontsize * 0.4
                            chunk_start_x = f"(w-{int(total_chunk_w)})/2"
                            preceding_w = sum(len(chunk_words[k]) for k in range(wi)) * char_w + wi * caption_fontsize * 0.4
                            x_expr = f"{chunk_start_x}+{int(preceding_w)}"

                            boxbw = int(caption_fontsize * 0.35)

                            # Layer 1: Dark background (shown during chunk time)
                            lbl_dark = f"c{label_counter}"
                            label_counter += 1
                            dt_dark = [
                                f"text='{safe_word}'",
                                f"fontsize={caption_fontsize}",
                                "fontcolor=white",
                                f"x={x_expr}",
                                f"y={caption_y}",
                                "box=1",
                                "boxcolor=black@0.65",
                                f"boxborderw={boxbw}",
                                f"enable='between(t,{chunk_start:.2f},{chunk_end:.2f})'",
                            ]
                            filter_parts.append(
                                f"[{prev_label}]drawtext={':'.join(dt_dark)}[{lbl_dark}]"
                            )
                            prev_label = lbl_dark

                            # Layer 2: Red background (shown only when this word is active)
                            lbl_red = f"c{label_counter}"
                            label_counter += 1
                            dt_red = [
                                f"text='{safe_word}'",
                                f"fontsize={caption_fontsize}",
                                "fontcolor=white",
                                f"x={x_expr}",
                                f"y={caption_y}",
                                "box=1",
                                "boxcolor=red@0.9",
                                f"boxborderw={boxbw}",
                                f"enable='between(t,{word_start:.2f},{word_end:.2f})'",
                            ]
                            filter_parts.append(
                                f"[{prev_label}]drawtext={':'.join(dt_red)}[{lbl_red}]"
                            )
                            prev_label = lbl_red

                    current_label = prev_label

            # Final output label
            filter_parts.append(f"[{current_label}]null[outv]")

            # Build the full filter
            full_filter = ";\n".join(filter_parts)

            # Output options
            cmd += [
                "-filter_complex", full_filter,
                "-map", "[outv]",
            ]

            if has_audio:
                cmd += ["-map", f"{audio_input_idx}:a"]

            cmd += [
                "-t", str(actual_duration),
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-c:a", "aac",
                "-b:a", "192k",
                "-r", str(FPS),
                "-shortest",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(scene_out)
            ]

            logger.info(f"   [{job_id}] Scene {i}: Running ffmpeg (PiP + captions)...")
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=180  # 3-minute timeout per scene
            )

            if result.returncode != 0:
                logger.warning(f"   [{job_id}] Scene {i}: Complex filter failed, using simple mode: {result.stderr[-300:]}")
                # Fallback: simple b-roll + audio without PiP/captions
                fallback_cmd = ["ffmpeg", "-y"]
                if broll_path and Path(broll_path).exists():
                    fallback_cmd += ["-stream_loop", "-1", "-i", str(broll_path)]
                    vf = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#141428,setsar=1,fps={FPS}"
                else:
                    fallback_cmd += ["-f", "lavfi", "-i", f"color=c=#141428:s={width}x{height}:r={FPS}:d={actual_duration}"]
                    vf = f"fps={FPS}"

                if audio_path and Path(audio_path).exists():
                    fallback_cmd += ["-i", str(audio_path)]

                fallback_cmd += [
                    "-vf", vf,
                    "-t", str(actual_duration),
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest", "-movflags", "+faststart",
                    str(scene_out)
                ]
                subprocess.run(fallback_cmd, capture_output=True, timeout=120)

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

    # ── Concatenate with crossfade transitions ──
    try:
        update_job_status(job_id, progress=93, stage="Adding transitions & music...")
        logger.info(f"🔗 [{job_id}] Joining {len(scene_files)} scenes with transitions...")

        if len(scene_files) == 1:
            # Single scene — just copy it
            import shutil
            pre_music_path = scene_files[0]
        else:
            # Use xfade for transitions between scenes
            pre_music_path = WORK_DIR / f"{job_id}_pre_music.mp4"

            # Get durations of each scene
            scene_durations = []
            for sf in scene_files:
                try:
                    probe = subprocess.run(
                        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(sf)],
                        capture_output=True, text=True, timeout=10
                    )
                    scene_durations.append(float(probe.stdout.strip()))
                except Exception:
                    scene_durations.append(10.0)

            # Build xfade chain: [0][1]xfade -> [result][2]xfade -> ...
            xfade_cmd = ["ffmpeg", "-y"]
            for sf in scene_files:
                xfade_cmd += ["-i", str(sf)]

            # Build filter for xfade chain
            xfade_filters = []
            audio_filters = []
            n = len(scene_files)
            transition_types = ["fade", "fadeblack", "dissolve", "slideleft", "slideup"]

            if n == 2:
                offset = max(0, scene_durations[0] - TRANSITION_DURATION)
                t = transition_types[0]
                xfade_filters.append(
                    f"[0:v][1:v]xfade=transition={t}:duration={TRANSITION_DURATION}:offset={offset}[outv]"
                )
                audio_filters.append(
                    f"[0:a][1:a]acrossfade=d={TRANSITION_DURATION}[outa]"
                )
            else:
                # Multi-scene xfade chain
                cumulative_offset = 0
                for j in range(n - 1):
                    t = transition_types[j % len(transition_types)]
                    offset = cumulative_offset + scene_durations[j] - TRANSITION_DURATION
                    in_label = f"[v{j}]" if j > 0 else "[0:v]"
                    out_label = "[outv]" if j == n - 2 else f"[v{j+1}]"
                    xfade_filters.append(
                        f"{in_label}[{j+1}:v]xfade=transition={t}:duration={TRANSITION_DURATION}:offset={offset}{out_label}"
                    )
                    cumulative_offset = offset

                # Audio: simple concat for now (acrossfade only works with 2 inputs)
                audio_inputs = "".join(f"[{j}:a]" for j in range(n))
                audio_filters.append(
                    f"{audio_inputs}concat=n={n}:v=0:a=1[outa]"
                )

            full_filter = ";".join(xfade_filters + audio_filters)

            xfade_cmd += [
                "-filter_complex", full_filter,
                "-map", "[outv]",
                "-map", "[outa]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                str(pre_music_path)
            ]

            logger.info(f"   [{job_id}] Running xfade transition join...")
            result = subprocess.run(
                xfade_cmd, capture_output=True, text=True, timeout=300
            )

            if result.returncode != 0:
                logger.warning(f"   [{job_id}] xfade failed, using simple concat: {result.stderr[-300:]}")
                # Fallback: simple concat
                pre_music_path = WORK_DIR / f"{job_id}_pre_music.mp4"
                concat_file = WORK_DIR / f"{job_id}_concat.txt"
                with open(concat_file, "w") as f:
                    for sf in scene_files:
                        f.write(f"file '{str(sf).replace(chr(92), '/')}'\n")

                concat_cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-movflags", "+faststart",
                    str(pre_music_path)
                ]
                subprocess.run(concat_cmd, capture_output=True, timeout=300)

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

# In-memory job store for status tracking
_jobs: Dict[str, Dict] = {}


def get_job_status(job_id: str) -> Optional[Dict]:
    return _jobs.get(job_id)


def update_job_status(job_id: str, **kwargs):
    if job_id not in _jobs:
        _jobs[job_id] = {}
    _jobs[job_id].update(kwargs)


def get_avatar_image_path(avatar_id: str) -> str:
    """Resolve avatar ID to image file path. Auto-generates if missing."""
    # Check custom upload directory first
    custom_path = AVATAR_DIR / f"custom_{avatar_id}.png"
    if custom_path.exists():
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
) -> Dict:
    """
    Full avatar video generation pipeline.
    This is the main entry point — runs synchronously (call from background task).
    Returns dict with status, video_url, scenes, etc.
    """
    if not job_id:
        job_id = hashlib.md5(f"{user_id}:{topic}:{language}:{style}:{time.time()}".encode()).hexdigest()[:12]

    update_job_status(job_id, status="starting", progress=0, stage="Initializing...")

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

        # ── Stage 3: Generate audio for all scenes ──
        update_job_status(job_id, progress=30, stage="Generating voice narration...")
        audio_paths = generate_all_scene_audio(scenes, job_id, voice, language)
        audio_count = sum(1 for p in audio_paths if p)
        logger.info(f"✅ [{job_id}] Stage 3 done: {audio_count}/{len(scenes)} audio files generated")
        for idx, ap in enumerate(audio_paths):
            logger.info(f"   Audio[{idx}]: {ap}")

        # ── Stage 4: Generate talking head avatars ──
        # Skip avatar for animated_explainer style (voiceover only, no PiP)
        avatar_image = get_avatar_image_path(avatar_id)
        avatar_clips = [None] * len(scenes)
        if video_style == "animated_explainer":
            logger.info(f"🎨 [{job_id}] Stage 4: Skipping avatar (animated_explainer style — voiceover only)")
            update_job_status(job_id, progress=45, stage="Animated explainer — skipping avatar...")
        elif avatar_image and REPLICATE_API_TOKEN:
            logger.info(f"📋 [{job_id}] Stage 4: avatar_image='{avatar_image}', REPLICATE_TOKEN={'set' if REPLICATE_API_TOKEN else 'NOT SET'}")
            update_job_status(job_id, progress=45, stage="Creating AI avatar...")
            avatar_clips = generate_all_talking_heads(avatar_image, audio_paths, job_id)
        else:
            update_job_status(job_id, progress=45, stage="Skipping avatar (no image/token)...")
            logger.info(f"⏭️ [{job_id}] Skipping talking head generation")

        # ── Stage 5: Search B-roll footage ──
        broll_paths = [None] * len(scenes)
        logger.info(f"📋 [{job_id}] Stage 5: include_broll={include_broll}, PEXELS_KEY={'set' if PEXELS_API_KEY else 'NOT SET'}")
        if include_broll and PEXELS_API_KEY:
            update_job_status(job_id, progress=65, stage="Finding background footage...")
            broll_paths = search_all_broll(scenes, job_id, video_style=video_style)
        else:
            update_job_status(job_id, progress=65, stage="Skipping B-roll...")
            logger.info(f"⏭️ [{job_id}] Skipping B-roll search")

        # ── Stage 6: Compose final video ──
        logger.info(f"🎬 [{job_id}] Stage 6: Composing video with {len(scenes)} scenes, {audio_count} audio files")
        update_job_status(job_id, progress=80, stage="Composing final video...")
        video_path = compose_final_video(
            scenes, audio_paths, avatar_clips, broll_paths,
            job_id, aspect_ratio, include_captions,
        )

        if not video_path:
            err = "Video composition failed — compose_final_video returned None (check server logs for traceback)"
            logger.error(f"❌ [{job_id}] {err}")
            update_job_status(job_id, status="failed", error=err)
            return {"status": "failed", "error": err, "job_id": job_id}
        logger.info(f"✅ [{job_id}] Stage 6 done: video_path={video_path}")

        # ── Stage 7: Upload to storage ──
        update_job_status(job_id, progress=95, stage="Uploading video...")

        result = {
            "status": "completed",
            "job_id": job_id,
            "video_path": video_path,
            "video_url": "",  # Will be set after Supabase upload
            "script": script,
            "scenes": scenes,
            "scene_count": len(scenes),
            "duration_estimate": sum(s.get("duration_estimate", 10) for s in scenes),
        }

        update_job_status(job_id, status="completed", progress=100, stage="Done!",
                          video_path=video_path, video_url="",
                          scene_count=len(scenes),
                          duration_estimate=sum(s.get("duration_estimate", 10) for s in scenes))
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
