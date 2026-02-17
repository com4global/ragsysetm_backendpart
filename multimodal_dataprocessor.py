"""
Multimodal Data Processor - Orchestrates processing of all file types
Supports: Text (PDF, DOCX, TXT, CSV, XLSX), Images, Audio, Video
"""

import os
from typing import Dict, List
from pathlib import Path

# Import existing processors
from pdfreader import read_pdf
from chunker import chunk_pages
from embedder import embed_chunks
from vectorstore import store_in_pinecone
from file_processor import read_file, get_file_type

# Import multimodal processors
from image_processor import process_single_image
from audio_processor import process_audio
from video_processor import process_video


def _process_text_file(file_path: str, file_type: str, chunk_size: int = 900, chunk_overlap: int = 150) -> Dict:
    """
    Process text-based files (PDF, DOCX, TXT, CSV, XLSX, XML)
    
    Returns:
        Dictionary with processing results
    """
    try:
        print(f"\n📄 Processing text file: {os.path.basename(file_path)}")
        
        # Read file
        pages, detected_type = read_file(file_path)
        print(f"✅ Extracted {len(pages)} pages")
        
        # Chunk the text
        chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        print(f"✂️  Created {len(chunks)} chunks")
        
        # Embed chunks
        embeddings = embed_chunks(chunks)
        print(f"🧠 Embedded {len(embeddings)} chunks")
        
        # Prepare embedded_chunks structure (Adapting to vectorstore.py signature)
        embedded_chunks = []
        if len(chunks) == len(embeddings):
            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                embedded_chunks.append({
                    "embedding": embedding,
                    "metadata": {
                        "text": chunk_text,
                        "page": "N/A",  # Lost page info in this simple pipeline
                        "doc_name": os.path.basename(file_path),
                        "path": file_path
                    }
                })
        
        # Store in Pinecone
        namespace = f"text_{file_type}"
        chunks_stored = 0
        
        if embedded_chunks:
            store_in_pinecone(embedded_chunks, namespace=namespace)
            chunks_stored = len(embedded_chunks)
            print(f"📌 Stored in Pinecone (namespace: {namespace})")
        else:
            print(f"⚠️ No chunks/embeddings to store for {file_path}")
        
        return {
            "file_name": os.path.basename(file_path),
            "file_type": file_type,
            "modality": "text",
            "chunks_created": len(chunks),
            "embeddings_created": len(embeddings),
            "namespace": namespace,
            "status": "success"
        }
    except Exception as e:
        print(f"❌ Error processing text file: {e}")
        return {
            "file_name": os.path.basename(file_path),
            "file_type": file_type,
            "modality": "text",
            "status": "error",
            "error": str(e)
        }


def _process_image_file(file_path: str) -> Dict:
    """
    Process image files (JPG, PNG, GIF, BMP, WEBP)
    
    Returns:
        Dictionary with processing results
    """
    try:
        print(f"\n🖼️  Processing image file: {os.path.basename(file_path)}")
        
        # Process image
        image_result = process_single_image(file_path)
        
        if not image_result:
            raise Exception("Image processing returned empty result")
        
        # Extract data
        embedding = image_result.get("embedding", [])
        caption = image_result.get("caption", "")
        combined_text = image_result.get("combined_text", "")
        
        # Store in Pinecone
        namespace = "images"
        store_in_pinecone(
            chunks=[combined_text],
            embeddings=[embedding],
            namespace=namespace
        )
        print(f"📌 Stored in Pinecone (namespace: {namespace})")
        
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "image",
            "modality": "image",
            "caption": caption,
            "chunks_created": 1,
            "embeddings_created": 1,
            "namespace": namespace,
            "status": "success"
        }
    except Exception as e:
        print(f"❌ Error processing image file: {e}")
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "image",
            "modality": "image",
            "status": "error",
            "error": str(e)
        }


def _process_audio_file(file_path: str) -> Dict:
    """
    Process audio files (MP3, WAV, OGG, FLAC, M4A)
    
    Returns:
        Dictionary with processing results
    """
    try:
        print(f"\n🎵 Processing audio file: {os.path.basename(file_path)}")
        
        # Process audio
        audio_result = process_audio(file_path)
        
        if not audio_result or not audio_result.get("chunks"):
            raise Exception("Audio processing returned no chunks")
        
        # Extract data
        chunks = audio_result.get("chunks", [])
        embeddings = audio_result.get("embeddings", [])
        duration = audio_result.get("duration", 0)
        
        if not chunks or not embeddings:
            raise Exception("No audio chunks or embeddings generated")
        
        # Store in Pinecone
        namespace = "audio"
        store_in_pinecone(
            chunks=chunks,
            embeddings=embeddings,
            namespace=namespace
        )
        print(f"📌 Stored in Pinecone (namespace: {namespace})")
        
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "audio",
            "modality": "audio",
            "duration": duration,
            "chunks_created": len(chunks),
            "embeddings_created": len(embeddings),
            "namespace": namespace,
            "status": "success"
        }
    except Exception as e:
        print(f"❌ Error processing audio file: {e}")
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "audio",
            "modality": "audio",
            "status": "error",
            "error": str(e)
        }


def _process_video_file(file_path: str) -> Dict:
    """
    Process video files (MP4, AVI, MOV, MKV, WEBM)
    
    Returns:
        Dictionary with processing results
    """
    try:
        print(f"\n🎥 Processing video file: {os.path.basename(file_path)}")
        
        # Process video
        video_result = process_video(file_path, extract_frames_fps=0.5)
        
        if not video_result:
            raise Exception("Video processing returned empty result")
        
        # Extract data
        text_chunks = video_result.get("text_chunks", [])
        text_embeddings = video_result.get("text_embeddings", [])
        frames_extracted = video_result.get("frames_extracted", 0)
        scenes_detected = video_result.get("scenes_detected", 0)
        
        # Store in Pinecone if we have text chunks
        if text_chunks and text_embeddings:
            namespace = "video"
            store_in_pinecone(
                chunks=text_chunks,
                embeddings=text_embeddings,
                namespace=namespace
            )
            print(f"📌 Stored in Pinecone (namespace: {namespace})")
        
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "video",
            "modality": "video",
            "frames_extracted": frames_extracted,
            "scenes_detected": scenes_detected,
            "chunks_created": len(text_chunks),
            "embeddings_created": len(text_embeddings),
            "namespace": "video",
            "status": "success"
        }
    except Exception as e:
        print(f"❌ Error processing video file: {e}")
        return {
            "file_name": os.path.basename(file_path),
            "file_type": "video",
            "modality": "video",
            "status": "error",
            "error": str(e)
        }


def process_multimodal_file(file_path: str, chunk_size: int = 900, chunk_overlap: int = 150) -> Dict:
    """
    Process any supported file type (text, image, audio, video)
    
    Args:
        file_path: Path to the file to process
        chunk_size: Size of text chunks (default: 900)
        chunk_overlap: Overlap between text chunks (default: 150)
    
    Returns:
        Dictionary with processing results and metadata
    
    Supported formats:
        - Text: PDF, DOCX, TXT, CSV, XLSX, XML
        - Image: JPG, JPEG, PNG, GIF, BMP, WEBP
        - Audio: MP3, WAV, OGG, FLAC, M4A
        - Video: MP4, AVI, MOV, MKV, WEBM
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_name = os.path.basename(file_path)
    file_type = get_file_type(file_path).lower()
    
    print(f"\n{'='*60}")
    print(f"📁 Processing file: {file_name}")
    print(f"📋 File type: {file_type}")
    print(f"{'='*60}")
    
    # ROUTE BY FILE TYPE
    
    # ===== TEXT FILES =====
    if file_type in ['pdf', 'docx', 'txt', 'csv', 'xlsx', 'xls', 'xml']:
        return _process_text_file(file_path, file_type, chunk_size, chunk_overlap)
    
    # ===== IMAGE FILES =====
    elif file_type in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
        return _process_image_file(file_path)
    
    # ===== AUDIO FILES =====
    elif file_type in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
        return _process_audio_file(file_path)
    
    # ===== VIDEO FILES =====
    elif file_type in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
        return _process_video_file(file_path)
    
    else:
        raise ValueError(f"Unsupported file type: {file_type}. Supported formats: PDF, DOCX, TXT, CSV, XLSX, JPG, PNG, MP3, WAV, MP4, AVI, MOV")


def batch_process_files(directory_path: str, file_extensions: List[str] = None) -> Dict:
    """
    Process multiple files in a directory
    
    Args:
        directory_path: Path to directory containing files
        file_extensions: List of extensions to process (e.g., ['.pdf', '.mp3', '.mp4'])
                        If None, processes all supported formats
    
    Returns:
        Dictionary with results for each file
    """
    if not os.path.isdir(directory_path):
        raise NotADirectoryError(f"Directory not found: {directory_path}")
    
    # Default to all supported formats
    if file_extensions is None:
        file_extensions = [
            '.pdf', '.docx', '.txt', '.csv', '.xlsx', '.xls', '.xml',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
            '.mp3', '.wav', '.ogg', '.flac', '.m4a',
            '.mp4', '.avi', '.mov', '.mkv', '.webm'
        ]
    
    results = {
        "total_files": 0,
        "successful": 0,
        "failed": 0,
        "files": []
    }
    
    print(f"\n📂 Batch processing directory: {directory_path}")
    print(f"📋 File extensions: {file_extensions}")
    
    for file in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file)
        
        if not os.path.isfile(file_path):
            continue
        
        if not any(file.lower().endswith(ext) for ext in file_extensions):
            continue
        
        results["total_files"] += 1
        
        try:
            result = process_multimodal_file(file_path)
            results["files"].append(result)
            
            if result.get("status") == "success":
                results["successful"] += 1
                print(f"✅ {file}")
            else:
                results["failed"] += 1
                print(f"❌ {file}: {result.get('error', 'Unknown error')}")
        except Exception as e:
            results["failed"] += 1
            results["files"].append({
                "file_name": file,
                "status": "error",
                "error": str(e)
            })
            print(f"❌ {file}: {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 Batch Processing Summary:")
    print(f"   Total files: {results['total_files']}")
    print(f"   Successful: {results['successful']}")
    print(f"   Failed: {results['failed']}")
    print(f"{'='*60}")
    
    return results


if __name__ == "__main__":
    # Test multimodal processor
    print("Testing multimodal processor...")
    
    # Test with different file types
    test_files = {
        "pdf": "./resources/HRPolicy.pdf",
        "image": "./resources/test_image.png",
        "audio": "./resources/test_audio.mp3",
        "video": "./resources/test_video.mp4"
    }
    
    for file_type, file_path in test_files.items():
        if os.path.exists(file_path):
            print(f"\n{'='*60}")
            try:
                result = process_multimodal_file(file_path)
                print(f"✅ {file_type.upper()} Result: {result}")
            except Exception as e:
                print(f"❌ {file_type.upper()} Error: {e}")
        else:
            print(f"⚠️  {file_type.upper()} test file not found: {file_path}")
