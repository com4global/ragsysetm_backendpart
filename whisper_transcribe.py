import os
import yt_dlp
import whisper_timestamped as whisper
import tempfile

FFMPEG_BIN = r"C:\ffmpeg-2026-01-26-git-fe0813d6e2-essentials_build\ffmpeg\bin"
os.environ["PATH"] += f";{FFMPEG_BIN}"

def transcribe_youtube(youtube_url: str):
    model = whisper.load_model("base")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_template = os.path.join(tmpdir, "audio.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_template,          # ✅ MUST use %(ext)s
            "ffmpeg_location": FFMPEG_BIN,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],
            "extractor_args": {
        "youtube": {
            "player_client": ["android"]
        }
    },
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

        audio_path = os.path.join(tmpdir, "audio.wav")

        if not os.path.exists(audio_path):
            raise RuntimeError("Audio file was not created by yt-dlp")

        result = whisper.transcribe(model, audio_path)

    segments = [
        {
            "start": int(seg["start"]),
            "end": int(seg["end"]),
            "text": seg["text"].strip(),
        }
        for seg in result["segments"]
    ]

    return segments


def format_transcript(segments):
    return "\n".join(f"[{s['start']}s] {s['text']}" for s in segments)