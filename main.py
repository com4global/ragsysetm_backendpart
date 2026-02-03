from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from QueryProcessor import process_user_query
from file_manager import add_file_record, get_all_files, get_file_stats, update_file_record
from dataprocessor import process_file
from file_processor import get_supported_formats
import os
import shutil
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from video_processor import process_video
from youtube_processor import process_youtube_link
from image_processor import process_single_image
from audio_processor import process_audio as process_audio_file
import os


app = FastAPI()


# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESOURCES_DIR = Path("./resources")
RESOURCES_DIR.mkdir(exist_ok=True)
current_dir = os.path.dirname(os.path.abspath(__file__))
resources_path = os.path.join(current_dir, "resources")
app.mount("/static_files", StaticFiles(directory=resources_path), name="static")

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    query: str
    sources: list = [] # Add this field

@app.get("/")
def read_root():
    return {"message": "HR Assistant RAG API is running"}

# @app.post("/chat")
# def chat(request: QueryRequest):
#     """
#     Process user query through the RAG pipeline
#     """
#     # ============== DEBUGGING OUTPUT ===============
#     print("\n" + "="*70)
#     print("🔴 CHAT ENDPOINT HIT!")
#     print("="*70)
#     print(f"📥 RECEIVED REQUEST")
#     print(f"   Type: {type(request)}")
#     print(f"   Query: {request.query}")
#     print(f"   Query Length: {len(request.query)}")
#     print("-"*70)
    
#     try:
#         print(f"\n🔄 STEP 1: Processing query...")
#         print(f"   Calling: process_user_query('{request.query}')")
        
#         response = process_user_query(request.query)
        
#         print(f"\n✅ STEP 2: Response received from LLM")
#         print(f"   Type: {type(response)}")
#         print(f"   Length: {len(str(response))}")
#         print(f"   Content: {response[:100]}..." if len(str(response)) > 100 else f"   Content: {response}")
        
#         print(f"\n📤 RETURNING RESPONSE")
#         print(f"   Status: SUCCESS")
#         print("="*70 + "\n")
        
#         return QueryResponse(response=response, query=request.query)
        
#     except Exception as e:
#         print(f"\n❌ ERROR OCCURRED")
#         print(f"   Error Type: {type(e).__name__}")
#         print(f"   Error Message: {str(e)}")
        
#         import traceback
#         print(f"\n📋 TRACEBACK:")
#         traceback.print_exc()
#         print("="*70 + "\n")
        
#         return {"error": str(e), "query": request.query}

@app.post("/api/process-video-file")
async def process_video_file_endpoint(filename: str):
    try:
        file_path = RESOURCES_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Video file not found")

        # 1. Extract and Transcribe
        video_data = process_video(str(file_path), extract_frames_fps=0.5)
        transcript = video_data.get("transcript", "")

        # 2. Save transcript to a .txt file (Mirroring your YouTube logic)
        txt_filename = f"{Path(filename).stem}_transcript.txt"
        txt_path = RESOURCES_DIR / txt_filename
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript)

        # 3. Add record for the NEW text file
        from file_manager import add_file_record, update_file_record
        from dataprocessor import process_file
        
        file_record = add_file_record(
            txt_filename, 
            "Video Transcript", 
            os.path.getsize(txt_path)
        )

        # 4. Process the text file into Pinecone using your working logic
        result = process_file(str(txt_path))
        
        # 5. Update metadata
        update_file_record(txt_filename, result["chunks_created"])

        return {
            "success": True,
            "message": "Video transcribed to text and indexed",
            "transcript_file": txt_filename
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/process-video-file")
# async def process_video_file_endpoint(filename: str):
#     try:
#         file_path = RESOURCES_DIR / filename
#         if not file_path.exists():
#             raise HTTPException(status_code=404, detail="Video file not found")

#         # 1. Process video
#         video_data = process_video(str(file_path), extract_frames_fps=0.5)

#         # 2. Get Embeddings
#         from embedder import embed_chunks
#         embeddings = embed_chunks(video_data["text_chunks"])

#         # 3. Prepare the unified list for store_in_pinecone
#         # Your vectorstore expects: {"embedding": [...], "metadata": {...}}
#         combined_data = []
#         for i, text in enumerate(video_data["text_chunks"]):
#             combined_data.append({
#                 "embedding": embeddings[i],
#                 "metadata": {
#                     "text": text,
#                     "doc_name": filename,
#                     "page": f"Segment {i+1}", 
#                     "path": str(file_path)
#                 }
#             })

#         # 4. Correct Function Name Import
#         from vectorstore import store_in_pinecone
        
#         # Store in Vector DB (using 'video' namespace or 'pdf' as you prefer)
#         store_in_pinecone(combined_data, namespace="pdf") 

#         # 5. Update file metadata
#         update_file_record(filename, len(combined_data))

#         return {
#             "success": True,
#             "message": "Video processed and indexed",
#             "chunks": len(combined_data)
#         }
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
    
# @app.post("/api/process-video-file")
# async def process_video_file_endpoint(filename: str):
#     """
#     Process a locally uploaded video file (MP4, AVI, etc.)
#     """
#     try:
#         file_path = RESOURCES_DIR / filename
#         if not file_path.exists():
#             raise HTTPException(status_code=404, detail="Video file not found")

#         # 1. Use your existing video_processor.py logic
#         # extract_frames_fps=0.5 means 1 frame every 2 seconds
#         video_data = process_video(str(file_path), extract_frames_fps=0.5)

#         # 2. Convert video text chunks into Pinecone-ready format
#         # We format them to look like the YouTube transcripts your LLM likes
#         chunks_for_db = []
#         for i, text in enumerate(video_data["text_chunks"]):
#             # Assuming 1 chunk per sentence, we estimate the "page" as a timestamp
#             # or just label it as 'Video Segment'
#             chunks_for_db.append({
#                 "text": text,
#                 "doc_name": filename,
#                 "page": f"Segment {i+1}", 
#                 "path": str(file_path)
#             })

#         # 3. Store in Vector DB (Pinecone)
#         from vectorstore import upsert_to_pinecone
#         from embedder import embed_chunks
        
#         # Embed the text segments
#         embeddings = embed_chunks(video_data["text_chunks"])
        
#         # Upsert
#         upsert_to_pinecone(chunks_for_db, embeddings, namespace="pdf") # Using 'pdf' namespace for testing as per your code

#         # 4. Update file metadata
#         update_file_record(filename, len(chunks_for_db))

#         return {
#             "success": True,
#             "message": "Video processed and indexed",
#             "chunks": len(chunks_for_db)
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(request: QueryRequest):
        try:
            # result is now the dict {"answer": ..., "sources": ...}
            result = process_user_query(request.query)
        
            return QueryResponse(
            response=result["answer"], 
            query=request.query,
            sources=result["sources"]
        )
        except Exception as e:
            return {"error": str(e), "query": request.query}

# ============== FILE MANAGEMENT ENDPOINTS ==============

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_ext = Path(file.filename).suffix.lower()
        
        # 1. Define all media categories based on your MultimodalUploader.jsx
        media_map = {
            'video': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
            'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
            'document': get_supported_formats()  # ['.pdf', '.docx', '.xlsx', etc.]
        }
        
        # Flatten the map to get a master list of all allowed extensions
        all_supported = [ext for sublist in media_map.values() for ext in sublist]
        
        if file_ext not in all_supported:
            raise HTTPException(
                status_code=400, 
                detail=f"Format {file_ext} not supported. Use: {', '.join(all_supported)}"
            )

        # 2. Save file to resources directory
        file_path = RESOURCES_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Determine File Type for Metadata
        file_type = "Unknown"
        for category, extensions in media_map.items():
            if file_ext in extensions:
                file_type = category.capitalize()
                break
        
        # 4. Fallback for document sub-types (Excel vs PDF vs Word)
        if file_type == "Document":
            try:
                from file_processor import get_file_type
                file_type = get_file_type(str(file_path))
            except Exception:
                pass # Keep as "Document" if sub-processor fails

        # 5. Record in Database/File Manager
        file_size = file_path.stat().st_size
        file_record = add_file_record(file.filename, file_type, file_size)
        
        return {
            "success": True, 
            "message": f"{file_type} uploaded successfully",
            "file": file_record
        }
        
    except Exception as e:
        print(f"CRITICAL UPLOAD ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

# @app.post("/api/upload")
# async def upload_file(file: UploadFile = File(...)):
#     """
#     Upload a file to resources folder
#     Supports: PDF, Excel, CSV, TXT, Word, XML
#     """
#     try:
#         # Validate file extension
#         supported = get_supported_formats()
#         file_ext = Path(file.filename).suffix.lower()
        
#         if file_ext not in supported:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"File type {file_ext} not supported. Supported: {', '.join(supported)}"
#             )
        
#         # Save file
#         file_path = RESOURCES_DIR / file.filename
        
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
        
#         file_size = file_path.stat().st_size
        
#         # Get file type
#         from file_processor import get_file_type
#         file_type = get_file_type(str(file_path))
        
#         # Record in metadata
#         file_record = add_file_record(file.filename, file_type, file_size)
        
#         return {
#             "success": True,
#             "message": f"File {file.filename} uploaded successfully",
#             "file": file_record
#         }
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
    

@app.post("/api/process-file")
def process_uploaded_file(filename: str):
    """
    Process an uploaded file and store in vector DB
    """
    try:
        file_path = RESOURCES_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
        # Process the file
        result = process_file(str(file_path))
        
        # Update metadata
        update_file_record(filename, result["chunks_created"])
        
        return {
            "success": True,
            "message": f"File processed successfully",
            "result": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    # Add this new endpoint
@app.post("/api/process-youtube")
async def process_youtube(data: dict):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="No URL provided")
    
    try:
        # 1. Download & Transcribe
        video_info = process_youtube_link(url)
        
        # 2. Add to your existing file manager
        file_record = add_file_record(
            video_info["filename"], 
            video_info["file_type"], 
            video_info["file_size"]
        )
        
        # 3. Process into Vector DB (Reuse your existing process_file!)
        from dataprocessor import process_file
        file_path = RESOURCES_DIR / video_info["filename"]
        result = process_file(str(file_path))
        
        # 4. Update metadata
        update_file_record(video_info["filename"], result["chunks_created"])
        
        return {"success": True, "message": "Video transcribed and indexed", "file": file_record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# @app.post("/api/process-image-file")
# async def process_image_file_endpoint(filename: str):
#     try:
#         file_path = RESOURCES_DIR / filename
#         if not file_path.exists():
#             raise HTTPException(status_code=404, detail="Image not found")

#         # 1. Use image_processor to get OCR text and Captions
#         image_data = process_single_image(str(file_path))
#         content = image_data.get("combined_text", "")

#         # 2. Save to .txt (The "YouTube Logic")
#         txt_filename = f"{Path(filename).stem}_image_content.txt"
#         txt_path = RESOURCES_DIR / txt_filename
#         with open(txt_path, "w", encoding="utf-8") as f:
#             f.write(content)

#         # 3. Add record and process into Pinecone
#         from file_manager import add_file_record, update_file_record
#         from dataprocessor import process_file
        
#         add_file_record(txt_filename, "Image Analysis", os.path.getsize(txt_path))
#         result = process_file(str(txt_path))
#         update_file_record(txt_filename, result["chunks_created"])

#         return {"success": True, "message": "Image analyzed and indexed", "text_file": txt_filename}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/api/process-image-file")
async def process_image_file_endpoint(filename: str):
    file_path = RESOURCES_DIR / filename
    
        # This now uses the Smart Toggle logic!
    image_data = process_single_image(str(file_path))
    
        # Save to TXT for your RAG system
    txt_filename = f"{Path(filename).stem}_content.txt"
    with open(RESOURCES_DIR / txt_filename, "w", encoding="utf-8") as f:
        f.write(image_data["combined_text"])
        
    # Process into Pinecone via your existing dataprocessor
    from dataprocessor import process_file
    result = process_file(str(RESOURCES_DIR / txt_filename))
    
    return {"success": True, "method": "Smart Image Logic", "indexed_chunks": result["chunks_created"]}

# --- AUDIO ENDPOINT ---
@app.post("/api/process-audio-file")
async def process_audio_file_endpoint(filename: str):
    try:
        file_path = RESOURCES_DIR / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        # 1. Use audio_processor to get Whisper transcript
        audio_data = process_audio_file(str(file_path))
        transcript = audio_data.get("transcript", "")

        # 2. Save to .txt
        txt_filename = f"{Path(filename).stem}_audio_transcript.txt"
        txt_path = RESOURCES_DIR / txt_filename
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript)

        # 3. Add record and process into Pinecone
        from file_manager import add_file_record, update_file_record
        from dataprocessor import process_file
        
        add_file_record(txt_filename, "Audio Transcript", os.path.getsize(txt_path))
        result = process_file(str(txt_path))
        update_file_record(txt_filename, result["chunks_created"])

        return {"success": True, "message": "Audio transcribed and indexed", "text_file": txt_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
def get_files():
    """
    Get all uploaded files with their metadata
    """
    try:
        files = get_all_files()
        stats = get_file_stats()
        return {
            "files": files,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/stats")
def get_stats():
    """
    Get file upload statistics
    """
    try:
        stats = get_file_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/supported-formats")
def get_formats():
    """
    Get list of supported file formats
    """
    return {
        "supported_formats": get_supported_formats(),
        "description": "Upload documents in any of these formats for RAG processing"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    #uvicorn.run(app, host="127.0.0.1", port=8000)
