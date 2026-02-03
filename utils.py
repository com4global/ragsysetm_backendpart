from urllib.parse import urlparse, parse_qs

def get_video_id(youtube_url: str) -> str:
    parsed = urlparse(youtube_url)
    if "youtube.com" in parsed.hostname:
        return parse_qs(parsed.query)["v"][0]
    elif "youtu.be" in parsed.hostname:
        return parsed.path[1:]
    else:
        raise ValueError("Invalid YouTube URL")

def build_youtube_link(video_id: str, seconds: int) -> str:
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"