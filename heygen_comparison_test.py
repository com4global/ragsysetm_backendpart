"""
HeyGen API Comparison Script
Generates a video using HeyGen's v2 API with the same Gemini Enterprise content
used by our custom engine, so we can compare output quality side-by-side.

Usage: python heygen_comparison_test.py
"""

import requests
import time
import os
import sys

# ── Config ──────────────────────────────────────────────────────────
HEYGEN_API_KEY = "sk_V2_hgu_kviuLlzqCrz_uY2QlqYkQDYs16uYYaYtrIQ6d1cmWlW8"
HEYGEN_BASE_URL = "https://api.heygen.com"

# Same content as the custom engine test
SCRIPT = (
    "Gemini Enterprise is our advanced agentic platform that brings the best of "
    "Google AI to every employee, for every workflow. It empowers teams to discover, "
    "create, share, and run AI agents — all in one secure environment."
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "avatar_video_temp")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def list_avatars():
    """List available avatars on this HeyGen account."""
    print("Fetching available avatars...")
    headers = {"X-Api-Key": HEYGEN_API_KEY, "Accept": "application/json"}
    resp = requests.get(HEYGEN_BASE_URL + "/v2/avatars", headers=headers, timeout=30)
    if resp.status_code != 200:
        print("  Failed to list avatars: " + str(resp.status_code))
        print("  " + resp.text[:500])
        return None
    data = resp.json().get("data", {})
    avatars = data.get("avatars", [])
    print("  Found " + str(len(avatars)) + " avatars")
    # Show first 5
    for a in avatars[:5]:
        print("    - " + str(a.get("avatar_id", "?")) + ": " + str(a.get("avatar_name", "?")))
    return avatars


def list_voices():
    """List available voices on this HeyGen account."""
    print("Fetching available voices...")
    headers = {"X-Api-Key": HEYGEN_API_KEY, "Accept": "application/json"}
    resp = requests.get(HEYGEN_BASE_URL + "/v2/voices", headers=headers, timeout=30)
    if resp.status_code != 200:
        print("  Failed to list voices: " + str(resp.status_code))
        print("  " + resp.text[:500])
        return None
    data = resp.json().get("data", {})
    voices = data.get("voices", [])
    print("  Found " + str(len(voices)) + " voices")
    # Filter for English voices
    en_voices = [v for v in voices if "en" in str(v.get("language", "")).lower()]
    print("  English voices: " + str(len(en_voices)))
    for v in en_voices[:5]:
        print("    - " + str(v.get("voice_id", "?")) + ": " + str(v.get("display_name", v.get("name", "?"))))
    return en_voices


def generate_heygen_video(script, avatar_id=None, voice_id=None):
    """Submit video generation to HeyGen v2 API."""
    headers = {
        "X-Api-Key": HEYGEN_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Use provided or default avatar/voice
    if not avatar_id:
        avatar_id = "Anna_public_3_20240108"  # Professional female educator
    if not voice_id:
        voice_id = "M2WosQ2Ju3f2b7jdddsj"    # en female (verified from account)

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
                    "input_text": script,
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
        "test": True,  # Test mode: watermarked but doesn't consume credits
    }

    print()
    print("Submitting video to HeyGen v2/video/generate...")
    print("  Avatar: " + avatar_id)
    print("  Voice:  " + voice_id)
    print("  Script: " + script[:80] + "...")
    print()

    resp = requests.post(
        HEYGEN_BASE_URL + "/v2/video/generate",
        json=payload, headers=headers, timeout=60,
    )

    print("  Response status: " + str(resp.status_code))
    resp_body = resp.text[:500]
    print("  Response body:   " + resp_body)

    if resp.status_code not in (200, 201):
        print("ERROR: HeyGen API returned " + str(resp.status_code))
        return None

    resp_data = resp.json()
    video_id = (
        resp_data.get("data", {}).get("video_id")
        or resp_data.get("video_id")
    )
    if not video_id:
        print("ERROR: No video_id in response")
        return None

    print("  Video ID: " + video_id)
    return video_id


def poll_until_done(video_id, max_wait=600, interval=10):
    """Poll HeyGen for video completion."""
    headers = {"X-Api-Key": HEYGEN_API_KEY, "Accept": "application/json"}
    deadline = time.time() + max_wait
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        resp = requests.get(
            HEYGEN_BASE_URL + "/v1/video_status.get",
            headers=headers,
            params={"video_id": video_id},
            timeout=15,
        )
        if resp.status_code != 200:
            print("  Poll error: " + str(resp.status_code) + " - " + resp.text[:200])
            time.sleep(interval)
            continue

        data = resp.json().get("data", {})
        status = data.get("status", "unknown")
        elapsed = int(time.time() - (deadline - max_wait))
        print("  [" + str(elapsed) + "s] Poll #" + str(attempt) + ": status=" + status)

        if status == "completed":
            video_url = data.get("video_url", "")
            thumbnail = data.get("thumbnail_url", "")
            duration = data.get("duration", 0)
            print()
            print("VIDEO COMPLETED!")
            print("  URL:       " + video_url)
            print("  Thumbnail: " + thumbnail)
            print("  Duration:  " + str(duration) + "s")
            return data

        elif status in ("failed", "error"):
            error = data.get("error", "unknown")
            print("VIDEO FAILED: " + str(error))
            return None

        time.sleep(interval)

    print("TIMEOUT: Video did not complete within " + str(max_wait) + "s")
    return None


def download_video(url, filename):
    """Download the video file."""
    output_path = os.path.join(OUTPUT_DIR, filename)
    print("Downloading video to: " + output_path)
    resp = requests.get(url, stream=True, timeout=120)
    if resp.status_code == 200:
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print("  Downloaded: " + str(round(size_mb, 2)) + " MB")
        return output_path
    else:
        print("  Download failed: " + str(resp.status_code))
        return None


def main():
    print("=" * 60)
    print("  HeyGen API — Video Quality Comparison")
    print("=" * 60)
    print()
    print("Content: " + SCRIPT)
    print()

    # Step 1: Check available avatars and voices
    avatars = list_avatars()
    voices = list_voices()
    print()

    # Step 2: Generate video
    start = time.time()
    video_id = generate_heygen_video(SCRIPT)
    if not video_id:
        print("Failed to submit video. Exiting.")
        return

    # Step 3: Poll until done (up to 10 minutes)
    print()
    print("Polling for completion (max 10 minutes)...")
    result = poll_until_done(video_id, max_wait=600, interval=10)
    elapsed = time.time() - start

    if not result:
        print("Video generation failed or timed out.")
        return

    # Step 4: Download the video
    video_url = result.get("video_url", "")
    if video_url:
        local_path = download_video(video_url, "heygen_comparison.mp4")
        print()
        print("=" * 60)
        print("  COMPARISON READY")
        print("=" * 60)
        print()
        print("  HeyGen video:     " + str(local_path))
        print("  Our engine video:  static/avatar_video_temp/test_broll_fix_final.mp4")
        print("  Total time:        " + str(round(elapsed, 1)) + "s")
        print()
        print("  HeyGen URL:        " + video_url)
        print("  Our engine URL:    http://localhost:8000/static/avatar_video_temp/test_broll_fix_final.mp4")
        if local_path:
            print("  HeyGen local URL:  http://localhost:8000/static/avatar_video_temp/heygen_comparison.mp4")


if __name__ == "__main__":
    main()
