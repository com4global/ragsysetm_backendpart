"""
FastAPI Main Application with Authentication
Production-ready API with user isolation and security
"""

# from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from typing import Dict, Optional, List
# import os
# import shutil
# from pathlib import Path
# from fastapi.staticfiles import StaticFiles
# from datetime import datetime, timedelta
# import uuid
# from datetime import timezone
# from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Query
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# from pydantic import BaseModel
# from typing import Optional, List, Dict, Any
# import os
# import shutil
# from pathlib import Path
# from fastapi.staticfiles import StaticFiles
# from datetime import datetime, timedelta
# import uuid

# # Import authentication modules
# from Auth import (
#     UserCreate, UserLogin, Token, TokenData, User,
#     verify_password, get_password_hash,
#     create_access_token, create_refresh_token,
#     get_current_user, verify_refresh_token
# )
# from database import user_db

# app = FastAPI(title="RAG.AI Enterprise API", version="2.0.0")

# # CORS Configuration
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["https://documentperser-frontend-cwd4.vercel.app/", "https://documentperser-frontend-cwd4.vercel.app"],  # Update for production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # File storage
# RESOURCES_DIR = Path("./resources")
# RESOURCES_DIR.mkdir(exist_ok=True)
# app.mount("/static_files", StaticFiles(directory=str(RESOURCES_DIR)), name="static")

# # ==================== MODELS ====================

# class QueryRequest(BaseModel):
#     query: str
#     session_id: Optional[str] = None

# # ✅ FLEXIBLE SOURCE MODEL - handles both string and dict sources
# class QueryResponse(BaseModel):
#     response: str
#     query: str
#     sources: List[Dict[str, Any]] = []  # ✅ Changed to flexible dict
#     session_id: str

# class RefreshTokenRequest(BaseModel):
#     refresh_token: str

# class FileResponse(BaseModel):
#     filename: str
#     file_type: str
#     file_size: int
#     chunks_created: int = 0
#     uploaded_at: str
#     processed: bool = False

# # ==================== AUTHENTICATION ENDPOINTS ====================

# @app.post("/api/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
# async def register(user_data: UserCreate):
#     """Register a new user"""
#     # Check if user already exists
#     existing_user = user_db.get_user_by_email(user_data.email)
#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email already registered"
#         )
    
#     # Hash password and create user
#     password_hash = get_password_hash(user_data.password)
#     user = user_db.create_user(
#         email=user_data.email,
#         password_hash=password_hash,
#         full_name=user_data.full_name,
#         company=user_data.company
#     )
    
#     # Create tokens
#     token_data = {"user_id": user["user_id"], "email": user["email"]}
#     access_token = create_access_token(token_data)
#     refresh_token = create_refresh_token(token_data)
    
#     # Save refresh token
#     expires_at = datetime.now(timezone.utc) + timedelta(days=7)
#     user_db.save_refresh_token(user["user_id"], refresh_token, expires_at)
    
#     return Token(
#         access_token=access_token,
#         refresh_token=refresh_token
#     )

# @app.post("/api/auth/login", response_model=Token)
# async def login(credentials: UserLogin):
#     """Login user and return tokens"""
#     # Get user
#     user = user_db.get_user_by_email(credentials.email)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid email or password"
#         )
    
#     # Verify password
#     if not verify_password(credentials.password, user["password_hash"]):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid email or password"
#         )
    
#     # Check if user is active
#     if not user["is_active"]:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Account is disabled"
#         )
    
#     # Update last login
#     user_db.update_last_login(user["user_id"])
    
#     # Create tokens
#     token_data = {"user_id": user["user_id"], "email": user["email"]}
#     access_token = create_access_token(token_data)
#     refresh_token = create_refresh_token(token_data)
    
#     # Save refresh token
#     expires_at = datetime.now(timezone.utc) + timedelta(days=7)
#     user_db.save_refresh_token(user["user_id"], refresh_token, expires_at)
    
#     return Token(
#         access_token=access_token,
#         refresh_token=refresh_token
#     )

# @app.post("/api/auth/refresh", response_model=Token)
# async def refresh_access_token(request: RefreshTokenRequest):
#     """Refresh access token using refresh token"""
#     try:
#         token_data = verify_refresh_token(request.refresh_token)
        
#         # Verify token in database
#         user_id = user_db.verify_refresh_token(request.refresh_token)
#         if not user_id or user_id != token_data.user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid refresh token"
#             )
        
#         # Create new access token
#         new_token_data = {"user_id": token_data.user_id, "email": token_data.email}
#         access_token = create_access_token(new_token_data)
        
#         return Token(
#             access_token=access_token,
#             refresh_token=request.refresh_token
#         )
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid refresh token"
#         )

# @app.post("/api/auth/logout")
# async def logout(
#     refresh_token: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Logout user by revoking refresh token"""
#     user_db.revoke_refresh_token(refresh_token)
#     return {"message": "Successfully logged out"}

# @app.get("/api/auth/me")
# async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
#     """Get current user information"""
#     user = user_db.get_user_by_id(current_user.user_id)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found"
#         )
    
#     # Remove sensitive data
#     user.pop("password_hash", None)
    
#     # Add statistics
#     stats = user_db.get_user_stats(current_user.user_id)
#     user.update(stats)
    
#     return user

# # ==================== FILE MANAGEMENT ENDPOINTS ====================

# @app.post("/api/upload")
# async def upload_file(
#     file: UploadFile = File(...),
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Upload file for authenticated user"""
#     try:
#         from file_processor import get_supported_formats, get_file_type
        
#         file_ext = Path(file.filename).suffix.lower()
#         supported = get_supported_formats()
#         media_exts = ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.jpg', '.png', '.jpeg', '.gif']
        
#         if file_ext not in supported and file_ext not in media_exts:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"Unsupported format: {file_ext}"
#             )
        
#         # Create user-specific directory
#         user_dir = RESOURCES_DIR / current_user.user_id
#         user_dir.mkdir(exist_ok=True)
        
#         # Save file with user isolation
#         file_path = user_dir / file.filename
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
        
#         file_size = file_path.stat().st_size
#         file_type = get_file_type(str(file_path)) if file_ext in supported else "Media"
        
#         # Add to user's file records
#         file_record = user_db.add_user_file(
#             user_id=current_user.user_id,
#             filename=file.filename,
#             file_type=file_type,
#             file_size=file_size
#         )
        
#         return {"success": True, "file": file_record}
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/process-file")
# async def process_file(
#     filename: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Process uploaded file for authenticated user"""
#     try:
#         # Verify file belongs to user
#         if not user_db.file_belongs_to_user(current_user.user_id, filename):
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Access denied to this file"
#             )
        
#         from dataprocessor import process_file
        
#         # Process file from user's directory
#         user_dir = RESOURCES_DIR / current_user.user_id
#         file_path = user_dir / filename
        
#         if not file_path.exists():
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="File not found"
#             )
        
#         # Process with user_id context for isolation
#         result = process_file(str(file_path), user_id=current_user.user_id)
        
#         # Update file record
#         user_db.update_file_processed(
#             user_id=current_user.user_id,
#             filename=filename,
#             chunks_created=result["chunks_created"]
#         )
        
#         return {"success": True, "result": result}
    
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/api/files")
# async def get_user_files(current_user: TokenData = Depends(get_current_user)):
#     """Get all files for authenticated user"""
#     try:
#         print(f"🔍 Fetching files for user: {current_user.user_id}")
#         files = user_db.get_user_files(current_user.user_id)
#         print(f"✅ Files retrieved: {len(files)}")
        
#         stats = user_db.get_user_stats(current_user.user_id)
#         print(f"✅ Stats retrieved: {stats}")
        
#         return {"files": files, "stats": stats}
#     except Exception as e:
#         print(f"❌ Error in get_user_files: {str(e)}")
#         print(f"❌ Error type: {type(e).__name__}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))
# # @app.get("/api/files")
# # async def get_user_files(current_user: TokenData = Depends(get_current_user)):
# #     """Get all files for authenticated user"""
# #     files = user_db.get_user_files(current_user.user_id)
# #     stats = user_db.get_user_stats(current_user.user_id)
    
# #     return {"files": files, "stats": stats}

# @app.delete("/api/files/{filename}")
# async def delete_file(
#     filename: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Delete file for authenticated user"""
#     try:
#         # Verify file belongs to user
#         if not user_db.file_belongs_to_user(current_user.user_id, filename):
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Access denied to this file"
#             )
        
#         # Delete physical file
#         user_dir = RESOURCES_DIR / current_user.user_id
#         file_path = user_dir / filename
#         if file_path.exists():
#             file_path.unlink()
        
#         # Delete from database
#         user_db.delete_user_file(current_user.user_id, filename)
        
#         # Delete from vector store (you'll need to implement this)
#         from dataprocessor import delete_user_file_vectors
#         delete_user_file_vectors(current_user.user_id, filename)
        
#         return {"success": True, "message": "File deleted"}
    
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# # ==================== CHAT ENDPOINTS ====================

# @app.post("/chat", response_model=QueryResponse)
# async def chat(
#     request: QueryRequest,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Chat endpoint with user-specific context"""
#     try:
#         from QueryProcessor import process_user_query
        
#         # Generate session ID if not provided
#         session_id = request.session_id or str(uuid.uuid4())
        
#         # Process query with user context for data isolation
#         result = process_user_query(
#             query=request.query,
#             user_id=current_user.user_id
#         )
        
#         # Save to chat history
#         user_db.add_chat_message(
#             user_id=current_user.user_id,
#             session_id=session_id,
#             query=request.query,
#             response=result["answer"],
#             sources=result.get("sources", [])
#         )
        
#         return QueryResponse(
#             response=result["answer"],
#             query=request.query,
#             sources=result.get("sources", []),
#             session_id=session_id
#         )
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/api/chat/history")
# async def get_chat_history(
#     session_id: Optional[str] = None,
#     limit: int = 50,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Get chat history for authenticated user"""
#     history = user_db.get_chat_history(
#         user_id=current_user.user_id,
#         session_id=session_id,
#         limit=limit
#     )
#     return {"history": history}

# ==================== MEDIA PROCESSING ENDPOINTS ====================

# @app.post("/api/process-video-file")
# async def process_video(
#     filename: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Process video file for authenticated user"""
#     if not user_db.file_belongs_to_user(current_user.user_id, filename):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied to this file"
#         )
    
#     # Implement your video processing logic with user_id context
#     # ...
#     return {"success": True, "message": "Video processing started"}

# @app.post("/api/process-audio-file")
# async def process_audio(
#     filename: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Process audio file for authenticated user"""
#     if not user_db.file_belongs_to_user(current_user.user_id, filename):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied to this file"
#         )
    
#     # Implement your audio processing logic with user_id context
#     # ...
#     return {"success": True, "message": "Audio processing started"}

# @app.post("/api/process-image-file")
# async def process_image(
#     filename: str,
#     current_user: TokenData = Depends(get_current_user)
# ):
#     """Process image file for authenticated user"""
#     if not user_db.file_belongs_to_user(current_user.user_id, filename):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Access denied to this file"
#         )
    
#     # Implement your image processing logic with user_id context
#     # ...
#     return {"success": True, "message": "Image processing started"}

# ==================== HEALTH CHECK ====================

# @app.get("/")
# def read_root():
#     return {
#         "message": "RAG.AI Enterprise API v2.0",
#         "status": "operational",
#         "features": ["authentication", "user_isolation", "file_management", "chat"]
#     }

# @app.get("/health")
# def health_check():
#     return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 10000))
#     uvicorn.run(app, host="0.0.0.0", port=port)



#without token


from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import shutil
from pathlib import Path
import requests

from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RESOURCES_DIR = Path("./resources")
RESOURCES_DIR.mkdir(exist_ok=True)
#app.mount("/static_files", StaticFiles(directory=str(RESOURCES_DIR)), name="static")
# NEW: Schema for the metadata the frontend will send
class FileMetadataRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    blob_url: str
class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: str
    query: str
    sources: list = []

@app.get("/")
def read_root():
    return {"message": "HR Assistant RAG API (Memory Optimized) is running"}


@app.post("/api/record-metadata")
async def record_metadata(request: FileMetadataRequest):
    try:
        from file_manager import add_file_record
        file_record = add_file_record(
            request.file_name, 
            request.file_type, 
            request.file_size, 
            request.blob_url
        )
        return {"success": True, "file": file_record}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-file")
def process_uploaded_file(filename: str):
    try:
        from dataprocessor import process_file
        from file_manager import update_file_record, get_file_by_name
        
        # 1. Look up the file record to get the URL
        file_info = get_file_by_name(filename)
        if not file_info or "blob_url" not in file_info:
            raise HTTPException(status_code=404, detail="File URL not found")

        # 2. Download from Vercel Blob to a temporary local file
        temp_path = RESOURCES_DIR / filename
        response = requests.get(file_info["blob_url"], stream=True)
        if response.status_code == 200:
            with open(temp_path, "wb") as f:
                f.write(response.content)
        else:
            raise Exception("Failed to download file from Vercel Blob")
        
        # 3. Process the local temp file for RAG
        result = process_file(str(temp_path))
        update_file_record(filename, result["chunks_created"])
        
        # 4. Cleanup: Remove the local file after processing to save disk space
        if temp_path.exists():
            os.remove(temp_path)
            
        return {"success": True, "result": result}
    except Exception as e:
        if temp_path.exists(): os.remove(temp_path) # Cleanup on error
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
def chat(request: QueryRequest):
    try:
        # LAZY IMPORT: Only loads when someone chats
        from QueryProcessor import process_user_query
        result = process_user_query(request.query)
        
        return QueryResponse(
            response=result["answer"], 
            query=request.query,
            sources=result.get("sources", [])
        )
    except Exception as e:
        return {"error": str(e), "query": request.query}

# @app.post("/api/upload")
# async def upload_file(file: UploadFile = File(...)):
#     try:
#         # LAZY IMPORT: For supported formats
#         from file_processor import get_supported_formats, get_file_type
#         from file_manager import add_file_record

#         file_ext = Path(file.filename).suffix.lower()
#         supported = get_supported_formats()
        
#         # Add media formats manually to avoid loading heavy processors here
#         media_exts = ['.mp4', '.avi', '.mov', '.mp3', '.wav', '.jpg', '.png']
        
#         if file_ext not in supported and file_ext not in media_exts:
#             raise HTTPException(status_code=400, detail="Unsupported format")

#         file_path = RESOURCES_DIR / file.filename
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
            
#         file_size = file_path.stat().st_size
#         file_type = get_file_type(str(file_path)) if file_ext in supported else "Media"
        
#         file_record = add_file_record(file.filename, file_type, file_size)
#         return {"success": True, "file": file_record}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/api/process-file")
# def process_uploaded_file(filename: str):
#     try:
#         # LAZY IMPORT: Heavy processing only happens here
#         from dataprocessor import process_file
#         from file_manager import update_file_record
        
#         file_path = RESOURCES_DIR / filename
#         result = process_file(str(file_path))
#         update_file_record(filename, result["chunks_created"])
        
#         return {"success": True, "result": result}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
def get_files():
    # File manager is lightweight, but we still import locally for consistency
    from file_manager import get_all_files, get_file_stats
    return {"files": get_all_files(), "stats": get_file_stats()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)


#original main.py
# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from QueryProcessor import process_user_query
# from file_manager import add_file_record, get_all_files, get_file_stats, update_file_record
# from dataprocessor import process_file
# from file_processor import get_supported_formats
# import os
# import shutil
# from pathlib import Path
# from fastapi.staticfiles import StaticFiles
# # from video_processor import process_video
# # from youtube_processor import process_youtube_link
# # from image_processor import process_single_image
# # from audio_processor import process_audio as process_audio_file
# import os


# app = FastAPI()


# # Enable CORS for React frontend
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# RESOURCES_DIR = Path("./resources")
# RESOURCES_DIR.mkdir(exist_ok=True)
# current_dir = os.path.dirname(os.path.abspath(__file__))
# resources_path = os.path.join(current_dir, "resources")
# app.mount("/static_files", StaticFiles(directory=resources_path), name="static")

# class QueryRequest(BaseModel):
#     query: str

# class QueryResponse(BaseModel):
#     response: str
#     query: str
#     sources: list = [] # Add this field

# @app.get("/")
# def read_root():
#     return {"message": "HR Assistant RAG API is running"}

# # @app.post("/chat")
# # def chat(request: QueryRequest):
# #     """
# #     Process user query through the RAG pipeline
# #     """
# #     # ============== DEBUGGING OUTPUT ===============
# #     print("\n" + "="*70)
# #     print("🔴 CHAT ENDPOINT HIT!")
# #     print("="*70)
# #     print(f"📥 RECEIVED REQUEST")
# #     print(f"   Type: {type(request)}")
# #     print(f"   Query: {request.query}")
# #     print(f"   Query Length: {len(request.query)}")
# #     print("-"*70)
    
# #     try:
# #         print(f"\n🔄 STEP 1: Processing query...")
# #         print(f"   Calling: process_user_query('{request.query}')")
        
# #         response = process_user_query(request.query)
        
# #         print(f"\n✅ STEP 2: Response received from LLM")
# #         print(f"   Type: {type(response)}")
# #         print(f"   Length: {len(str(response))}")
# #         print(f"   Content: {response[:100]}..." if len(str(response)) > 100 else f"   Content: {response}")
        
# #         print(f"\n📤 RETURNING RESPONSE")
# #         print(f"   Status: SUCCESS")
# #         print("="*70 + "\n")
        
# #         return QueryResponse(response=response, query=request.query)
        
# #     except Exception as e:
# #         print(f"\n❌ ERROR OCCURRED")
# #         print(f"   Error Type: {type(e).__name__}")
# #         print(f"   Error Message: {str(e)}")
        
# #         import traceback
# #         print(f"\n📋 TRACEBACK:")
# #         traceback.print_exc()
# #         print("="*70 + "\n")
        
# #         return {"error": str(e), "query": request.query}

# @app.post("/api/process-video-file")
# async def process_video_file_endpoint(filename: str):
#     try:
#         file_path = RESOURCES_DIR / filename
#         if not file_path.exists():
#             raise HTTPException(status_code=404, detail="Video file not found")

#         # 1. Extract and Transcribe
#         video_data = process_video(str(file_path), extract_frames_fps=0.5)
#         transcript = video_data.get("transcript", "")

#         # 2. Save transcript to a .txt file (Mirroring your YouTube logic)
#         txt_filename = f"{Path(filename).stem}_transcript.txt"
#         txt_path = RESOURCES_DIR / txt_filename
        
#         with open(txt_path, "w", encoding="utf-8") as f:
#             f.write(transcript)

#         # 3. Add record for the NEW text file
#         from file_manager import add_file_record, update_file_record
#         from dataprocessor import process_file
        
#         file_record = add_file_record(
#             txt_filename, 
#             "Video Transcript", 
#             os.path.getsize(txt_path)
#         )

#         # 4. Process the text file into Pinecone using your working logic
#         result = process_file(str(txt_path))
        
#         # 5. Update metadata
#         update_file_record(txt_filename, result["chunks_created"])

#         return {
#             "success": True,
#             "message": "Video transcribed to text and indexed",
#             "transcript_file": txt_filename
#         }
#     except Exception as e:
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=str(e))

# # @app.post("/api/process-video-file")
# # async def process_video_file_endpoint(filename: str):
# #     try:
# #         file_path = RESOURCES_DIR / filename
# #         if not file_path.exists():
# #             raise HTTPException(status_code=404, detail="Video file not found")

# #         # 1. Process video
# #         video_data = process_video(str(file_path), extract_frames_fps=0.5)

# #         # 2. Get Embeddings
# #         from embedder import embed_chunks
# #         embeddings = embed_chunks(video_data["text_chunks"])

# #         # 3. Prepare the unified list for store_in_pinecone
# #         # Your vectorstore expects: {"embedding": [...], "metadata": {...}}
# #         combined_data = []
# #         for i, text in enumerate(video_data["text_chunks"]):
# #             combined_data.append({
# #                 "embedding": embeddings[i],
# #                 "metadata": {
# #                     "text": text,
# #                     "doc_name": filename,
# #                     "page": f"Segment {i+1}", 
# #                     "path": str(file_path)
# #                 }
# #             })

# #         # 4. Correct Function Name Import
# #         from vectorstore import store_in_pinecone
        
# #         # Store in Vector DB (using 'video' namespace or 'pdf' as you prefer)
# #         store_in_pinecone(combined_data, namespace="pdf") 

# #         # 5. Update file metadata
# #         update_file_record(filename, len(combined_data))

# #         return {
# #             "success": True,
# #             "message": "Video processed and indexed",
# #             "chunks": len(combined_data)
# #         }
# #     except Exception as e:
# #         import traceback
# #         traceback.print_exc()
# #         raise HTTPException(status_code=500, detail=str(e))
    
# # @app.post("/api/process-video-file")
# # async def process_video_file_endpoint(filename: str):
# #     """
# #     Process a locally uploaded video file (MP4, AVI, etc.)
# #     """
# #     try:
# #         file_path = RESOURCES_DIR / filename
# #         if not file_path.exists():
# #             raise HTTPException(status_code=404, detail="Video file not found")

# #         # 1. Use your existing video_processor.py logic
# #         # extract_frames_fps=0.5 means 1 frame every 2 seconds
# #         video_data = process_video(str(file_path), extract_frames_fps=0.5)

# #         # 2. Convert video text chunks into Pinecone-ready format
# #         # We format them to look like the YouTube transcripts your LLM likes
# #         chunks_for_db = []
# #         for i, text in enumerate(video_data["text_chunks"]):
# #             # Assuming 1 chunk per sentence, we estimate the "page" as a timestamp
# #             # or just label it as 'Video Segment'
# #             chunks_for_db.append({
# #                 "text": text,
# #                 "doc_name": filename,
# #                 "page": f"Segment {i+1}", 
# #                 "path": str(file_path)
# #             })

# #         # 3. Store in Vector DB (Pinecone)
# #         from vectorstore import upsert_to_pinecone
# #         from embedder import embed_chunks
        
# #         # Embed the text segments
# #         embeddings = embed_chunks(video_data["text_chunks"])
        
# #         # Upsert
# #         upsert_to_pinecone(chunks_for_db, embeddings, namespace="pdf") # Using 'pdf' namespace for testing as per your code

# #         # 4. Update file metadata
# #         update_file_record(filename, len(chunks_for_db))

# #         return {
# #             "success": True,
# #             "message": "Video processed and indexed",
# #             "chunks": len(chunks_for_db)
# #         }
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# @app.post("/chat")
# def chat(request: QueryRequest):
#         try:
#             # result is now the dict {"answer": ..., "sources": ...}
#             result = process_user_query(request.query)
        
#             return QueryResponse(
#             response=result["answer"], 
#             query=request.query,
#             sources=result["sources"]
#         )
#         except Exception as e:
#             return {"error": str(e), "query": request.query}

# # ============== FILE MANAGEMENT ENDPOINTS ==============

# @app.post("/api/upload")
# async def upload_file(file: UploadFile = File(...)):
#     try:
#         file_ext = Path(file.filename).suffix.lower()
        
#         # 1. Define all media categories based on your MultimodalUploader.jsx
#         media_map = {
#             'video': ['.mp4', '.avi', '.mov', '.mkv', '.webm'],
#             'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
#             'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
#             'document': get_supported_formats()  # ['.pdf', '.docx', '.xlsx', etc.]
#         }
        
#         # Flatten the map to get a master list of all allowed extensions
#         all_supported = [ext for sublist in media_map.values() for ext in sublist]
        
#         if file_ext not in all_supported:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"Format {file_ext} not supported. Use: {', '.join(all_supported)}"
#             )

#         # 2. Save file to resources directory
#         file_path = RESOURCES_DIR / file.filename
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
            
#         # 3. Determine File Type for Metadata
#         file_type = "Unknown"
#         for category, extensions in media_map.items():
#             if file_ext in extensions:
#                 file_type = category.capitalize()
#                 break
        
#         # 4. Fallback for document sub-types (Excel vs PDF vs Word)
#         if file_type == "Document":
#             try:
#                 from file_processor import get_file_type
#                 file_type = get_file_type(str(file_path))
#             except Exception:
#                 pass # Keep as "Document" if sub-processor fails

#         # 5. Record in Database/File Manager
#         file_size = file_path.stat().st_size
#         file_record = add_file_record(file.filename, file_type, file_size)
        
#         return {
#             "success": True, 
#             "message": f"{file_type} uploaded successfully",
#             "file": file_record
#         }
        
#     except Exception as e:
#         print(f"CRITICAL UPLOAD ERROR: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

# # @app.post("/api/upload")
# # async def upload_file(file: UploadFile = File(...)):
# #     """
# #     Upload a file to resources folder
# #     Supports: PDF, Excel, CSV, TXT, Word, XML
# #     """
# #     try:
# #         # Validate file extension
# #         supported = get_supported_formats()
# #         file_ext = Path(file.filename).suffix.lower()
        
# #         if file_ext not in supported:
# #             raise HTTPException(
# #                 status_code=400, 
# #                 detail=f"File type {file_ext} not supported. Supported: {', '.join(supported)}"
# #             )
        
# #         # Save file
# #         file_path = RESOURCES_DIR / file.filename
        
# #         with open(file_path, "wb") as buffer:
# #             shutil.copyfileobj(file.file, buffer)
        
# #         file_size = file_path.stat().st_size
        
# #         # Get file type
# #         from file_processor import get_file_type
# #         file_type = get_file_type(str(file_path))
        
# #         # Record in metadata
# #         file_record = add_file_record(file.filename, file_type, file_size)
        
# #         return {
# #             "success": True,
# #             "message": f"File {file.filename} uploaded successfully",
# #             "file": file_record
# #         }
    
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))
    
    

# @app.post("/api/process-file")
# def process_uploaded_file(filename: str):
#     """
#     Process an uploaded file and store in vector DB
#     """
#     try:
#         file_path = RESOURCES_DIR / filename
        
#         if not file_path.exists():
#             raise HTTPException(status_code=404, detail=f"File {filename} not found")
        
#         # Process the file
#         result = process_file(str(file_path))
        
#         # Update metadata
#         update_file_record(filename, result["chunks_created"])
        
#         return {
#             "success": True,
#             "message": f"File processed successfully",
#             "result": result
#         }
    
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
#     # Add this new endpoint
# # @app.post("/api/process-youtube")
# # async def process_youtube(data: dict):
# #     url = data.get("url")
# #     if not url:
# #         raise HTTPException(status_code=400, detail="No URL provided")
    
# #     try:
# #         # 1. Download & Transcribe
# #         video_info = process_youtube_link(url)
        
# #         # 2. Add to your existing file manager
# #         file_record = add_file_record(
# #             video_info["filename"], 
# #             video_info["file_type"], 
# #             video_info["file_size"]
# #         )
        
# #         # 3. Process into Vector DB (Reuse your existing process_file!)
# #         from dataprocessor import process_file
# #         file_path = RESOURCES_DIR / video_info["filename"]
# #         result = process_file(str(file_path))
        
# #         # 4. Update metadata
# #         update_file_record(video_info["filename"], result["chunks_created"])
        
# #         return {"success": True, "message": "Video transcribed and indexed", "file": file_record}
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))
    

    
# # @app.post("/api/process-image-file")
# # async def process_image_file_endpoint(filename: str):
# #     file_path = RESOURCES_DIR / filename
    
# #         # This now uses the Smart Toggle logic!
# #     image_data = process_single_image(str(file_path))
    
# #         # Save to TXT for your RAG system
# #     txt_filename = f"{Path(filename).stem}_content.txt"
# #     with open(RESOURCES_DIR / txt_filename, "w", encoding="utf-8") as f:
# #         f.write(image_data["combined_text"])
        
# #     # Process into Pinecone via your existing dataprocessor
# #     from dataprocessor import process_file
# #     result = process_file(str(RESOURCES_DIR / txt_filename))
    
# #     return {"success": True, "method": "Smart Image Logic", "indexed_chunks": result["chunks_created"]}

# # --- AUDIO ENDPOINT ---
# # @app.post("/api/process-audio-file")
# # async def process_audio_file_endpoint(filename: str):
# #     try:
# #         file_path = RESOURCES_DIR / filename
# #         if not file_path.exists():
# #             raise HTTPException(status_code=404, detail="Audio file not found")

# #         # 1. Use audio_processor to get Whisper transcript
# #         audio_data = process_audio_file(str(file_path))
# #         transcript = audio_data.get("transcript", "")

# #         # 2. Save to .txt
# #         txt_filename = f"{Path(filename).stem}_audio_transcript.txt"
# #         txt_path = RESOURCES_DIR / txt_filename
# #         with open(txt_path, "w", encoding="utf-8") as f:
# #             f.write(transcript)

# #         # 3. Add record and process into Pinecone
# #         from file_manager import add_file_record, update_file_record
# #         from dataprocessor import process_file
        
# #         add_file_record(txt_filename, "Audio Transcript", os.path.getsize(txt_path))
# #         result = process_file(str(txt_path))
# #         update_file_record(txt_filename, result["chunks_created"])

# #         return {"success": True, "message": "Audio transcribed and indexed", "text_file": txt_filename}
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/api/files")
# def get_files():
#     """
#     Get all uploaded files with their metadata
#     """
#     try:
#         files = get_all_files()
#         stats = get_file_stats()
#         return {
#             "files": files,
#             "stats": stats
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/api/files/stats")
# def get_stats():
#     """
#     Get file upload statistics
#     """
#     try:
#         stats = get_file_stats()
#         return stats
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/api/supported-formats")
# def get_formats():
#     """
#     Get list of supported file formats
#     """
#     return {
#         "supported_formats": get_supported_formats(),
#         "description": "Upload documents in any of these formats for RAG processing"
#     }

# if __name__ == "__main__":
#     import uvicorn
#     port = int(os.environ.get("PORT", 10000))
#     uvicorn.run(app, host="0.0.0.0", port=port)
#     #uvicorn.run(app, host="127.0.0.1", port=8000)
