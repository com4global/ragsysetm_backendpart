import os
from pathlib import Path
from whisper_transcribe import transcribe_youtube, format_transcript
from utils import get_video_id, build_youtube_link

RESOURCES_DIR = Path("./resources")

def process_youtube_link(youtube_url: str):
    # 1. Get Metadata
    video_id = get_video_id(youtube_url)
    filename = f"youtube_{video_id}.txt"
    file_path = RESOURCES_DIR / filename

    # 2. Transcribe
    print(f"🎬 Transcribing video: {video_id}")
    segments = transcribe_youtube(youtube_url)
    
    # 3. Save transcript to a text file so your current RAG can "see" it
    # We include the clickable links inside the text so the LLM can retrieve them
    with open(file_path, "w", encoding="utf-8") as f:
        for seg in segments:
            link = build_youtube_link(video_id, seg['start'])
            f.write(f"[{seg['start']}s] ({link}) : {seg['text']}\n")

    # 4. Return info to be added to your file_manager (similar to upload)
    return {
        "filename": filename,
        "file_type": "YouTube Video",
        "file_size": os.path.getsize(file_path),
        "video_id": video_id
    }