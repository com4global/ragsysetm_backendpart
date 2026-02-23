"""
local_video_service.py — Local TTS + Avatar Video Engine (No lip-sync)
=======================================================================
Generates professional educational videos WITHOUT any paid external API:

Pipeline:
  1. Check Supabase ai_videos cache → return instantly if already generated
  2. Generate narration audio via OpenAI TTS → temp MP3
  3. Build video frames with Pillow (avatar + waveform animation)
  4. Composite with moviepy → MP4
  5. Upload to Supabase Storage bucket 'ai-videos' → permanent URL
  6. Cache URL in ai_videos table

No HeyGen, no D-ID, no GPU required. Only needs:
  - OpenAI TTS API (cheap: ~$0.015 per 1k chars ≈ $0.01 per video)
  - ffmpeg (system package, already installed)
  - moviepy, Pillow, numpy (pip)
"""

import hashlib
import logging
import math
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────────
VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
FPS = 24
AVATAR_RADIUS = 130
FONT_DIR = Path(__file__).parent / "assets" / "fonts"

# OpenAI TTS voices — pick a clear, professional one
TTS_VOICE_DEFAULT = "nova"       # Female, warm & professional
TTS_VOICE_MALE    = "onyx"       # Male, deep & authoritative
TTS_VOICE_TAMIL   = "nova"       # Tamil: OpenAI TTS doesn't support Tamil; falls back to English


# ── Cache helpers (shared with heygen_service) ───────────────────────────────

def _local_cache_key(topic: str, doc_name: str, language: str) -> str:
    """MD5 cache key — same topic/doc/language = same video for ALL users.
    Bump the version suffix whenever the video layout changes significantly."""
    raw = f"{topic.strip().lower()}|{doc_name.strip().lower()}|{language.strip().lower()}|v2"
    return hashlib.md5(raw.encode()).hexdigest()


def get_supabase_cached_video(topic: str, doc_name: str, language: str) -> Optional[Dict]:
    """Check Supabase ai_videos table for an already-generated video."""
    try:
        from database import get_supabase_client
        sb = get_supabase_client()
        key = _local_cache_key(topic, doc_name, language)
        result = (
            sb.table("ai_videos")
            .select("*")
            .eq("cache_key", key)
            .eq("status", "completed")
            .limit(1)
            .execute()
        )
        if result.data:
            logger.info(f"🎯 Supabase ai_videos cache HIT: {topic}")
            return result.data[0]
    except Exception as e:
        logger.warning(f"Supabase video cache lookup failed (non-fatal): {e}")
    return None


def save_supabase_video(
    topic: str, doc_name: str, language: str,
    video_id: str, video_url: str,
    thumbnail_url: str = "", script: str = "", presenter: str = "AI Teacher"
) -> None:
    """Upsert a completed video into Supabase ai_videos for permanent caching."""
    try:
        from database import get_supabase_client
        sb = get_supabase_client()
        key = _local_cache_key(topic, doc_name, language)
        sb.table("ai_videos").upsert(
            {
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
            },
            on_conflict="cache_key",
        ).execute()
        logger.info(f"✅ Supabase ai_videos saved: {topic} → {video_url[:80]}...")
    except Exception as e:
        logger.warning(f"Supabase video cache save failed (non-fatal): {e}")


# ── Step 1 — TTS Audio Generation ────────────────────────────────────────────

def generate_tts_audio(script: str, language: str, output_path: str) -> float:
    """
    Generate MP3 narration using OpenAI TTS.
    Returns estimated duration in seconds.
    """
    from openai import OpenAI
    client = OpenAI()

    voice = TTS_VOICE_DEFAULT
    if language in ("hi",):
        voice = TTS_VOICE_MALE  # Hindi sounds better with deeper voice

    # OpenAI TTS supports Hindi but not Tamil — keep as English for Tamil
    logger.info(f"🔊 Generating TTS audio ({voice}, {len(script)} chars)...")

    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice=voice,
        input=script[:4096],  # TTS limit
        response_format="mp3",
        speed=0.95,
    ) as response:
        response.stream_to_file(output_path)

    # Estimate duration via ffprobe (comes with ffmpeg)
    try:
        import subprocess, json
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_streams", output_path],
            capture_output=True, text=True, timeout=10
        )
        info = json.loads(probe.stdout)
        duration = float(info["streams"][0].get("duration", 0))
        if duration <= 0:
            raise ValueError("zero duration")
    except Exception:
        # Fallback: estimate from char count (~150 wpm)
        duration = len(script.split()) / 150 * 60
        duration = max(30.0, min(duration, 180.0))

    logger.info(f"🔊 TTS audio ready: {duration:.1f}s")
    return duration


# ── Step 2 — Avatar Frame Rendering ──────────────────────────────────────────

def _get_font(size: int):
    """Try system fonts in order; fall back to PIL default."""
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


_GRADIENT_BG    = (15, 23, 42)       # Deep navy (top)
_GRADIENT_BOT   = (30, 41, 59)       # Slate (bottom)
_ACCENT         = (99, 102, 241)      # Indigo
_ACCENT2        = (139, 92, 246)      # Violet
_TEXT_PRIMARY   = (248, 250, 252)     # Near-white
_TEXT_SECONDARY = (148, 163, 184)     # Slate-400
_WAVEFORM_COL   = (99, 102, 241)      # Indigo bars
_WAVEFORM_GLOW  = (139, 92, 246)      # Glow color


def _draw_gradient_bg(draw: ImageDraw.Draw, w: int, h: int) -> None:
    """Vertical gradient background."""
    for y in range(h):
        t = y / h
        r = int(_GRADIENT_BG[0] + t * (_GRADIENT_BOT[0] - _GRADIENT_BG[0]))
        g = int(_GRADIENT_BG[1] + t * (_GRADIENT_BOT[1] - _GRADIENT_BG[1]))
        b = int(_GRADIENT_BG[2] + t * (_GRADIENT_BOT[2] - _GRADIENT_BG[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _draw_avatar_circle(img: Image.Image, draw: ImageDraw.Draw,
                         cx: int, cy: int, radius: int) -> None:
    """Draw a professional avatar circle with gradient ring."""
    # Outer glow ring
    for r in range(radius + 20, radius - 1, -1):
        alpha = int(60 * (1 - (r - radius) / 20)) if r > radius else 200
        color = (*_ACCENT2, alpha) if r > radius else (*_ACCENT, alpha)
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            outline=color, width=2
        )

    # Solid avatar background
    draw.ellipse(
        [(cx - radius, cy - radius), (cx + radius, cy + radius)],
        fill=(30, 41, 80)
    )

    # AI Teacher icon — stylized "A" with graduation cap aesthetic
    font_icon = _get_font(80)
    icon_text = "AI"
    bbox = draw.textbbox((0, 0), icon_text, font=font_icon)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 8), icon_text,
              fill=_TEXT_PRIMARY, font=font_icon)

    # Small "Teacher" label below icon
    font_sub = _get_font(18)
    sub_text = "TEACHER"
    bbox2 = draw.textbbox((0, 0), sub_text, font=font_sub)
    sw = bbox2[2] - bbox2[0]
    draw.text((cx - sw // 2, cy + th // 2 - 5), sub_text,
              fill=_ACCENT2, font=font_sub)


def _draw_waveform(draw: ImageDraw.Draw, w: int, h: int,
                    t: float, num_bars: int = 40) -> None:
    """Draw animated waveform bars at the bottom of the frame."""
    bar_area_w = w * 0.7
    bar_area_x = (w - bar_area_w) / 2
    bar_area_y = h - 130
    bar_area_h = 60
    bar_w = bar_area_w / (num_bars * 1.6)
    bar_gap = bar_w * 0.6

    for i in range(num_bars):
        # Sine wave pattern with time offset
        phase = (i / num_bars) * math.pi * 4 + t * 3.5
        amplitude = abs(math.sin(phase)) * 0.85 + 0.15  # 15-100% height
        # Secondary wave for more natural look
        phase2 = (i / num_bars) * math.pi * 6 + t * 2.1
        amplitude = (amplitude + abs(math.sin(phase2)) * 0.4) / 1.4

        bar_h = amplitude * bar_area_h
        x = bar_area_x + i * (bar_w + bar_gap)
        y_top = bar_area_y + (bar_area_h - bar_h)

        # Color gradient per bar
        t_color = i / num_bars
        r = int(_WAVEFORM_COL[0] + t_color * (_WAVEFORM_GLOW[0] - _WAVEFORM_COL[0]))
        g = int(_WAVEFORM_COL[1] + t_color * (_WAVEFORM_GLOW[1] - _WAVEFORM_COL[1]))
        b = int(_WAVEFORM_COL[2] + t_color * (_WAVEFORM_GLOW[2] - _WAVEFORM_COL[2]))

        draw.rounded_rectangle(
            [(x, y_top), (x + bar_w, y_top + bar_h)],
            radius=bar_w / 2,
            fill=(r, g, b)
        )


def _wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list:
    """Wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]  # max 3 lines in frame


def make_frame(topic: str, script_excerpt: str, t: float,
               w: int = VIDEO_WIDTH, h: int = VIDEO_HEIGHT) -> np.ndarray:
    """
    Generate a single video frame as a numpy array (RGB).
    Called by moviepy for each second of video.
    """
    img = Image.new("RGB", (w, h), _GRADIENT_BG)
    draw = ImageDraw.Draw(img)

    # Background gradient
    _draw_gradient_bg(draw, w, h)

    # Subtle grid lines (decoration)
    for gx in range(0, w, 60):
        draw.line([(gx, 0), (gx, h)], fill=(255, 255, 255, 10), width=1)

    # Avatar card on the LEFT side
    avatar_cx = w // 4
    avatar_cy = h // 2 - 30
    _draw_avatar_circle(img, draw, avatar_cx, avatar_cy, AVATAR_RADIUS)

    # Vertical divider
    div_x = w // 2 - 60
    draw.line([(div_x, h * 0.1), (div_x, h * 0.85)],
              fill=(*_ACCENT, 100), width=2)

    # RIGHT side — Topic title
    font_title = _get_font(38)
    font_body  = _get_font(24)
    font_badge = _get_font(16)

    text_x = div_x + 40
    text_max_w = w - text_x - 40

    # "AI TEACHER" badge
    badge_text = "✦  AI TEACHER  ✦"
    draw.text((text_x, h * 0.12), badge_text, fill=_ACCENT2, font=font_badge)

    # Topic heading
    topic_lines = _wrap_text(topic.upper(), font_title, text_max_w, draw)
    ty = h * 0.22
    for line in topic_lines:
        draw.text((text_x, ty), line, fill=_TEXT_PRIMARY, font=font_title)
        bbox = draw.textbbox((0, 0), line, font=font_title)
        ty += (bbox[3] - bbox[1]) + 8

    # Horizontal accent line under title
    draw.line([(text_x, ty + 10), (text_x + 200, ty + 10)],
               fill=_ACCENT, width=3)

    # Script excerpt — fades in/out slowly
    body_lines = _wrap_text(script_excerpt[:220], font_body, text_max_w, draw)
    by = ty + 35
    for line in body_lines:
        draw.text((text_x, by), line, fill=_TEXT_SECONDARY, font=font_body)
        bbox = draw.textbbox((0, 0), line, font=font_body)
        by += (bbox[3] - bbox[1]) + 6

    # Animated waveform at the bottom
    _draw_waveform(draw, w, h, t)

    # Bottom bar
    draw.rectangle([(0, h - 50), (w, h)], fill=(10, 15, 30))
    font_footer = _get_font(15)
    draw.text((20, h - 35), "Powered by AI Teacher Engine",
              fill=_TEXT_SECONDARY, font=font_footer)
    # Pulsing dot
    pulse = (math.sin(t * 4) + 1) / 2
    dot_color = (
        int(99 + pulse * 40),
        int(102 + pulse * 10),
        int(241 - pulse * 20)
    )
    draw.ellipse([(w - 30, h - 38), (w - 18, h - 26)], fill=dot_color)

    return np.array(img)


# ── Step 3 — Video Compositing ────────────────────────────────────────────────

def _render_static_frame(topic: str, script: str, frame_path: str) -> None:
    """
    Render ONE static background PNG. Top 58% = content; bottom 42% = dark
    waveform canvas (ffmpeg showwaves renders there).
    """
    w, h = VIDEO_WIDTH, VIDEO_HEIGHT
    CONTENT_H = int(h * 0.58)          # top 58% = 417px for content
    WAVE_Y    = CONTENT_H               # waveform starts here
    BOTTOM_BAR= 40                      # footer strip height

    img = Image.new("RGB", (w, h), _GRADIENT_BG)
    draw = ImageDraw.Draw(img)

    # Content zone gradient
    for y in range(CONTENT_H):
        t = y / CONTENT_H
        r = int(_GRADIENT_BG[0] + t * (_GRADIENT_BOT[0] - _GRADIENT_BG[0]))
        g = int(_GRADIENT_BG[1] + t * (_GRADIENT_BOT[1] - _GRADIENT_BG[1]))
        b = int(_GRADIENT_BG[2] + t * (_GRADIENT_BOT[2] - _GRADIENT_BG[2]))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Subtle grid decoration
    for gx in range(0, w, 60):
        draw.line([(gx, 0), (gx, CONTENT_H)], fill=(30, 40, 60), width=1)

    # Avatar on LEFT — vertically centered in the content zone
    avatar_cy = CONTENT_H // 2
    _draw_avatar_circle(img, draw, w // 4, avatar_cy, AVATAR_RADIUS)

    # Vertical divider
    div_x = w // 2 - 60
    draw.line([(div_x, int(CONTENT_H * 0.08)), (div_x, int(CONTENT_H * 0.92))],
              fill=(*_ACCENT, 80), width=2)

    # RIGHT side text
    font_title = _get_font(36)
    font_body  = _get_font(20)
    font_badge = _get_font(14)
    text_x     = div_x + 40
    text_max_w = w - text_x - 40

    draw.text((text_x, int(CONTENT_H * 0.10)), "\u2726  AI TEACHER  \u2726",
              fill=_ACCENT2, font=font_badge)

    topic_lines = _wrap_text(topic.upper(), font_title, text_max_w, draw)
    ty = int(CONTENT_H * 0.22)
    for line in topic_lines:
        draw.text((text_x, ty), line, fill=_TEXT_PRIMARY, font=font_title)
        bbox = draw.textbbox((0, 0), line, font=font_title)
        ty += (bbox[3] - bbox[1]) + 5

    draw.line([(text_x, ty + 8), (text_x + 180, ty + 8)], fill=_ACCENT, width=3)

    body_lines = _wrap_text(script[:200], font_body, text_max_w, draw)
    by = ty + 24
    for line in body_lines:
        draw.text((text_x, by), line, fill=_TEXT_SECONDARY, font=font_body)
        bbox = draw.textbbox((0, 0), line, font=font_body)
        by += (bbox[3] - bbox[1]) + 4

    # ── Waveform canvas: dark gradient from content zone to bottom ──
    wave_h = h - WAVE_Y - BOTTOM_BAR    # ~260px
    for y in range(WAVE_Y, h - BOTTOM_BAR):
        t = (y - WAVE_Y) / max(wave_h, 1)
        darkness = int(4 + t * 6)       # very dark: 4→10
        draw.line([(0, y), (w, y)], fill=(darkness, darkness + 2, darkness + 12))

    # Label above waveform
    font_label = _get_font(13)
    label = "▶  AUDIO WAVEFORM"
    draw.text((20, WAVE_Y + 8), label, fill=(80, 90, 130), font=font_label)

    # Thin accent line separating content from waveform
    draw.line([(0, WAVE_Y), (w, WAVE_Y)], fill=(*_ACCENT, 60), width=2)

    # ── Bottom bar ──
    draw.rectangle([(0, h - BOTTOM_BAR), (w, h)], fill=(6, 8, 18))
    draw.text((20, h - 27), "Powered by AI Teacher Engine",
              fill=_TEXT_SECONDARY, font=_get_font(13))
    draw.ellipse([(w - 26, h - 30), (w - 14, h - 18)], fill=_ACCENT)

    img.save(frame_path)


def create_video(audio_path: str, topic: str, script: str,
                 output_path: str) -> None:
    """
    Fast video build: one static Pillow background + ffmpeg showwaves overlay.
    Top 58% = static content card. Bottom 42% = live animated audio waveform.
    Generation time: ~5-15 seconds.
    """
    import subprocess

    logger.info("\U0001f3ac Building video (static frame + large showwaves)...")

    frame_path = output_path.replace(".mp4", "_bg.png")
    _render_static_frame(topic, script[:200], frame_path)

    CONTENT_H  = int(VIDEO_HEIGHT * 0.58)   # 417px — must match _render_static_frame
    BOTTOM_BAR = 40
    wave_y     = CONTENT_H                   # waveform starts right below content
    wave_h     = VIDEO_HEIGHT - CONTENT_H - BOTTOM_BAR  # ~263px

    # Two-layer waveform for visual depth:
    #   [wv1] full-width center-line waveform (bright, thick)
    #   [wv2] same waveform but half-opacity — gives a glow effect
    filter_graph = (
        f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}[bg];"
        # Layer 1: bright indigo→violet waveform
        f"[1:a]showwaves=s={VIDEO_WIDTH}x{wave_h}"
        f":mode=cline:rate={FPS}"
        f":colors=ffffff|6366f1[wv1];"
        # Layer 2: tinted copy for glow (60% scale, centered)
        f"[1:a]showwaves=s={VIDEO_WIDTH}x{int(wave_h * 0.6)}"
        f":mode=cline:rate={FPS}"
        f":colors=8b5cf6|a78bfa[wv2];"
        # Composite: bg → overlay wv1 → overlay wv2 (centered in wave strip)
        f"[bg][wv1]overlay=0:{wave_y}[tmp];"
        f"[tmp][wv2]overlay=0:{wave_y + wave_h // 2 - int(wave_h * 0.6) // 2}[v]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", frame_path,
        "-i", audio_path,
        "-filter_complex", filter_graph,
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-c:a", "aac",
        "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    try:
        os.remove(frame_path)
    except Exception:
        pass

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr[-600:]}")

    logger.info(f"\U0001f3ac Video written: {output_path}")


# ── Step 4 — Supabase Storage Upload ─────────────────────────────────────────

def upload_video_to_supabase(video_path: str, filename: str) -> str:
    """
    Upload MP4 to Supabase Storage bucket 'ai-videos'.
    Returns the public URL. Falls back to serving via FastAPI /static if upload fails.
    """
    try:
        from database import get_supabase_client
        sb = get_supabase_client()

        with open(video_path, "rb") as f:
            video_bytes = f.read()

        res = sb.storage.from_("ai-videos").upload(
            path=filename,
            file=video_bytes,
            file_options={"content-type": "video/mp4", "upsert": "true"},
        )
        # Build public URL
        url_resp = sb.storage.from_("ai-videos").get_public_url(filename)
        if isinstance(url_resp, str):
            return url_resp
        # Older supabase-py returns dict
        return url_resp.get("publicURL") or url_resp.get("publicUrl", "")
    except Exception as e:
        logger.warning(f"Supabase storage upload failed (non-fatal): {e}")
        return ""


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def generate_local_video_sync(
    script: str,
    topic: str,
    doc_name: str = "",
    language: str = "en",
) -> Dict:
    """
    Full synchronous pipeline — runs in a thread pool from main.py.

    Returns:
        {
          video_url: str,       # MP4 URL (Supabase or local)
          video_id: str,
          presenter: str,
          cached: bool,
        }
    """
    # ── 1. Check Supabase cache ──
    cached = get_supabase_cached_video(topic, doc_name, language)
    if cached and cached.get("video_url"):
        logger.info(f"🎯 Local video cache HIT: {topic}")
        return {
            "video_url": cached["video_url"],
            "video_id": cached.get("video_id", ""),
            "thumbnail_url": cached.get("thumbnail_url", ""),
            "presenter": cached.get("presenter", "AI Teacher"),
            "cached": True,
        }

    video_id = str(uuid.uuid4()).replace("-", "")[:16]
    filename  = f"{video_id}.mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "narration.mp3")
        video_path = os.path.join(tmpdir, filename)

        # ── 2. Generate TTS audio ──
        try:
            generate_tts_audio(script, language, audio_path)
        except Exception as e:
            raise RuntimeError(f"TTS audio generation failed: {e}")

        # ── 3. Render video ──
        try:
            create_video(audio_path, topic, script, video_path)
        except Exception as e:
            raise RuntimeError(f"Video compositing failed: {e}")

        # ── 4. Upload to Supabase Storage ──
        video_url = upload_video_to_supabase(video_path, filename)

        # If Supabase upload failed, copy to local static dir as fallback
        if not video_url:
            static_dir = Path(__file__).parent / "static" / "videos"
            static_dir.mkdir(parents=True, exist_ok=True)
            dest = static_dir / filename
            import shutil
            shutil.copy2(video_path, dest)
            video_url = f"/static/videos/{filename}"
            logger.warning(f"Using local fallback URL: {video_url}")

    # ── 5. Persist to Supabase ai_videos cache ──
    save_supabase_video(
        topic, doc_name, language,
        video_id, video_url, "", script, "AI Teacher"
    )

    logger.info(f"✅ Local video ready: {video_url}")
    return {
        "video_url": video_url,
        "video_id": video_id,
        "thumbnail_url": "",
        "presenter": "AI Teacher",
        "cached": False,
    }
