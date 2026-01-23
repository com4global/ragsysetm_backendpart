import cv2
import os
import numpy as np
from typing import List, Tuple, Dict
import tempfile

print("🎥 Initializing Video Processor...")

try:
    import moviepy.editor as mpy
    print("✅ MoviePy loaded successfully")
except Exception as e:
    print(f"❌ Error loading MoviePy: {e}")
    mpy = None

try:
    from audio_processor import transcribe_audio
    print("✅ Audio processor imported")
except Exception as e:
    print(f"⚠️  Could not import audio_processor: {e}")


def extract_frames_at_intervals(video_path: str, fps: int = 1) -> List[np.ndarray]:
    """
    Extract frames from video at specified intervals
    
    Args:
        video_path: Path to video file
        fps: Frames per second to extract (1 = 1 frame per second)
    
    Returns:
        List of frame arrays
    """
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        frames = []
        frame_count = 0
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        
        if video_fps <= 0:
            video_fps = 30  # Default fallback
        
        frame_interval = max(1, int(video_fps / fps))
        
        print(f"🎬 Extracting frames at {fps} fps (interval: {frame_interval} frames)")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % frame_interval == 0:
                frames.append(frame)
            
            frame_count += 1
        
        cap.release()
        print(f"✅ Extracted {len(frames)} frames from {frame_count} total frames")
        return frames
    except Exception as e:
        print(f"❌ Frame Extraction Error: {e}")
        return []


def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds"""
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        
        if fps <= 0:
            fps = 30
        
        duration = frame_count / fps
        return duration
    except Exception as e:
        print(f"❌ Duration Error: {e}")
        return 0.0


def extract_audio_from_video(video_path: str) -> str:
    """Extract audio from video and transcribe"""
    try:
        if mpy is None:
            print("⚠️  MoviePy not available, skipping audio extraction")
            return ""
        
        print("🎵 Extracting audio from video...")
        video = mpy.VideoFileClip(video_path)
        
        if video.audio is None:
            print("⚠️  Video has no audio track")
            video.close()
            return ""
        
        # Save audio temporarily
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = tmp.name
            video.audio.write_audiofile(audio_path, verbose=False, logger=None)
        
        # Transcribe
        transcript = transcribe_audio(audio_path)
        
        # Clean up
        try:
            os.remove(audio_path)
        except:
            pass
        
        video.close()
        
        print(f"✅ Transcribed audio: {len(transcript)} characters")
        return transcript
    except Exception as e:
        print(f"❌ Audio Extraction Error: {e}")
        return ""


def detect_scene_changes(video_path: str, threshold: float = 30.0) -> List[Tuple[int, int]]:
    """
    Detect scene changes in video based on frame differences
    
    Args:
        video_path: Path to video file
        threshold: Difference threshold for detecting scene change
    
    Returns:
        List of (start_frame, end_frame) tuples
    """
    try:
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        prev_frame = None
        scenes = [(0, 0)]
        frame_count = 0
        
        print("🎬 Detecting scene changes...")
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if prev_frame is not None:
                # Convert to grayscale for comparison
                prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Calculate frame difference
                diff = cv2.absdiff(prev_gray, curr_gray)
                mean_diff = np.mean(diff)
                
                # Detect scene change
                if mean_diff > threshold:
                    scenes.append((frame_count, frame_count))
            
            prev_frame = frame
            frame_count += 1
        
        cap.release()
        print(f"✅ Detected {len(scenes)} scene changes")
        return scenes
    except Exception as e:
        print(f"❌ Scene Detection Error: {e}")
        return []


def get_video_metadata(video_path: str) -> Dict:
    """Get video metadata"""
    try:
        cap = cv2.VideoCapture(video_path)
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        cap.release()
        
        duration = frame_count / fps if fps > 0 else 0
        
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration": duration
        }
    except Exception as e:
        print(f"❌ Metadata Error: {e}")
        return {}


def process_video(video_path: str, extract_frames_fps: int = 0.5) -> Dict:
    """
    Complete video processing pipeline
    
    Args:
        video_path: Path to video file
        extract_frames_fps: Frames per second to extract (0.5 = 1 frame every 2 seconds)
    
    Returns:
        Dictionary with video metadata and processed content
    """
    try:
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        print(f"\n🎥 Processing video: {os.path.basename(video_path)}")
        
        # Get metadata
        metadata = get_video_metadata(video_path)
        print(f"📊 Video metadata: {metadata['width']}x{metadata['height']}, {metadata['fps']:.2f} fps")
        
        # Extract frames
        frames = extract_frames_at_intervals(video_path, fps=extract_frames_fps)
        
        # Extract and transcribe audio
        transcript = extract_audio_from_video(video_path)
        
        # Detect scenes
        scenes = detect_scene_changes(video_path)
        
        # Chunk transcript
        if transcript:
            sentences = [s.strip() for s in transcript.split('.') if s.strip()]
        else:
            sentences = []
        
        # Embed transcript chunks
        text_embeddings = []
        if sentences:
            try:
                from embedder import embed_chunks
                text_embeddings = embed_chunks(sentences)
            except Exception as e:
                print(f"⚠️  Using dummy embeddings: {e}")
                import numpy as np
                text_embeddings = [np.random.randn(1536).tolist() for _ in sentences]
        
        result = {
            "file": os.path.basename(video_path),
            "file_path": video_path,
            "transcript": transcript,
            "frames_extracted": len(frames),
            "scenes_detected": len(scenes),
            "text_chunks": sentences,
            "text_embeddings": text_embeddings,
            "chunk_count": len(sentences),
            "metadata": metadata,
            "modality": "video"
        }
        
        print(f"✅ Video processed: {len(frames)} frames, {len(scenes)} scenes, {len(sentences)} text chunks")
        return result
    except Exception as e:
        print(f"❌ Video Processing Error: {e}")
        return {}


if __name__ == "__main__":
    # Test video processor
    print("Testing video processor...")
    
    test_video_path = "./resources/test_video.mp4"
    
    if os.path.exists(test_video_path):
        result = process_video(test_video_path)
        print(f"✅ Result: Processed {result.get('frames_extracted', 0)} frames")
    else:
        print(f"⚠️  Test video not found at {test_video_path}")
        print("   Please provide a video file to test")
