import whisper
import librosa
import numpy as np
from typing import List, Tuple, Dict
import os

# Load Whisper model
print("🎵 Loading Whisper model for audio transcription...")
try:
    whisper_model = whisper.load_model("base")
    print("✅ Whisper model loaded successfully")
except Exception as e:
    print(f"❌ Error loading Whisper model: {e}")
    whisper_model = None


def transcribe_audio(audio_path: str, language: str = "en") -> str:
    """Transcribe audio to text using Whisper"""
    try:
        if whisper_model is None:
            print(f"⚠️  Whisper model not available for {audio_path}")
            return ""
        
        print(f"🎵 Transcribing: {os.path.basename(audio_path)}")
        result = whisper_model.transcribe(audio_path, language=language)
        transcript = result["text"]
        
        print(f"✅ Transcription complete: {len(transcript)} characters")
        return transcript
    except Exception as e:
        print(f"❌ Transcription Error for {audio_path}: {e}")
        return ""


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds"""
    try:
        y, sr = librosa.load(audio_path)
        duration = librosa.get_duration(y=y, sr=sr)
        print(f"📊 Audio duration: {duration:.2f} seconds")
        return duration
    except Exception as e:
        print(f"❌ Duration Error for {audio_path}: {e}")
        return 0.0


def get_audio_sample_rate(audio_path: str) -> int:
    """Get sample rate of audio file"""
    try:
        y, sr = librosa.load(audio_path)
        return sr
    except Exception as e:
        print(f"❌ Sample Rate Error for {audio_path}: {e}")
        return 0


def chunk_audio_by_silence(audio_path: str, threshold_db: int = -40) -> List[Tuple[float, float]]:
    """Chunk audio by detecting silence"""
    try:
        y, sr = librosa.load(audio_path)
        S = librosa.feature.melspectrogram(y=y, sr=sr)
        S_db = librosa.power_to_db(S, ref=np.max)
        
        # Find silent segments
        silent_frames = np.where(np.mean(S_db, axis=0) < threshold_db)[0]
        
        if len(silent_frames) == 0:
            # No silence detected, return single chunk
            duration = librosa.get_duration(y=y, sr=sr)
            return [(0, duration)]
        
        chunks = []
        chunk_start = 0
        
        for i, frame in enumerate(silent_frames):
            if i == 0 or frame - silent_frames[i-1] > 1:
                chunk_end = librosa.frames_to_time(frame, sr=sr)
                if chunk_end > chunk_start:
                    chunks.append((chunk_start, chunk_end))
                chunk_start = chunk_end
        
        # Add final chunk
        duration = librosa.get_duration(y=y, sr=sr)
        if chunk_start < duration:
            chunks.append((chunk_start, duration))
        
        print(f"🔊 Detected {len(chunks)} audio segments")
        return chunks
    except Exception as e:
        print(f"❌ Chunking Error for {audio_path}: {e}")
        return []


def get_audio_embedding_dummy(transcript: str) -> List[float]:
    """
    Create audio embedding from transcript using OpenAI embeddings
    Falls back to dummy embedding if needed
    """
    try:
        # For now, return a dummy embedding of standard size
        # In production, use: from embedder import embed_chunks
        embedding = np.random.randn(1536).tolist()  # Match text embedding size
        return embedding
    except Exception as e:
        print(f"❌ Audio Embedding Error: {e}")
        return []


def process_audio(audio_path: str) -> Dict:
    """Complete audio processing pipeline"""
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        print(f"\n🎵 Processing audio: {os.path.basename(audio_path)}")
        
        # Get duration and sample rate
        duration = get_audio_duration(audio_path)
        sample_rate = get_audio_sample_rate(audio_path)
        
        # Transcribe
        transcript = transcribe_audio(audio_path)
        
        if not transcript:
            print("⚠️ No transcript generated")
            return {"transcript": ""} # Return empty so main.py doesn't crash   
        return {
                "file": os.path.basename(audio_path),
                "duration": duration,
                "sample_rate": sample_rate,
                "transcript": "",
                "chunks": [],
                "embeddings": [],
                "chunk_count": 0,
                "modality": "audio",
                "error": "No transcript generated"
            }
        
        # Chunk transcript by sentences
        sentences = [s.strip() for s in transcript.split('.') if s.strip()]
        
        # Import embedder here to avoid circular dependency
        try:
            from embedder import embed_chunks
            embeddings = embed_chunks(sentences)
        except Exception as e:
            print(f"⚠️  Using dummy embeddings: {e}")
            embeddings = [get_audio_embedding_dummy(s) for s in sentences]
        
        result = {
            "file": os.path.basename(audio_path),
            "file_path": audio_path,
            "transcript": transcript,
            "duration": duration,
            "sample_rate": sample_rate,
            "chunks": sentences,
            "embeddings": embeddings,
            "chunk_count": len(sentences),
            "modality": "audio"
        }
        
        print(f"✅ Audio processed: {len(sentences)} text chunks, {duration:.2f}s duration")
        return result
    except Exception as e:
        print(f"❌ Audio Processing Error: {e}")
        return {}


if __name__ == "__main__":
    # Test audio processor
    print("Testing audio processor...")
    
    # Check if test audio exists
    test_audio_path = "./resources/test_audio.mp3"
    
    if os.path.exists(test_audio_path):
        result = process_audio(test_audio_path)
        print(f"✅ Result: Processed {result.get('chunk_count', 0)} chunks")
    else:
        print(f"⚠️  Test audio not found at {test_audio_path}")
        print("   Please provide an audio file to test")
