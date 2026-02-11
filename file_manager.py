"""
File Management System with User Isolation
Tracks uploaded files and their processing status per user
"""

# import json
# import os
# from datetime import datetime
# from pathlib import Path
# from typing import List, Dict, Optional

# RESOURCES_DIR = Path("./resources")
# METADATA_FILE = RESOURCES_DIR / ".file_metadata.json"


# def ensure_resources_dir():
#     """Ensure resources directory exists"""
#     RESOURCES_DIR.mkdir(exist_ok=True)


# def ensure_user_dir(user_id: str):
#     """Ensure user-specific directory exists"""
#     user_dir = RESOURCES_DIR / user_id
#     user_dir.mkdir(exist_ok=True)
#     return user_dir


# def load_metadata() -> Dict:
#     """Load file metadata from JSON"""
#     ensure_resources_dir()
    
#     if METADATA_FILE.exists():
#         try:
#             with open(METADATA_FILE, 'r') as f:
#                 return json.load(f)
#         except:
#             return {"files": []}
#     return {"files": []}


# def save_metadata(metadata: Dict):
#     """Save file metadata to JSON"""
#     ensure_resources_dir()
#     with open(METADATA_FILE, 'w') as f:
#         json.dump(metadata, f, indent=2)


# def add_file_record(
#     file_name: str, 
#     file_type: str, 
#     file_size: int,
#     user_id: Optional[str] = None
# ) -> Dict:
#     """
#     Add a new file record with optional user association
    
#     Args:
#         file_name: Name of the file
#         file_type: Type/extension of file
#         file_size: Size in bytes
#         user_id: Optional user ID for multi-user systems
        
#     Returns:
#         Dictionary with file record
#     """
#     metadata = load_metadata()
    
#     file_record = {
#         "id": len(metadata["files"]) + 1,
#         "file_name": file_name,
#         "file_type": file_type,
#         "file_size": file_size,
#         "status": "uploaded",
#         "uploaded_at": datetime.now().isoformat(),
#         "processed": False,
#         "chunks_created": 0
#     }
    
#     # Add user_id if provided
#     if user_id:
#         file_record["user_id"] = user_id
    
#     metadata["files"].append(file_record)
#     save_metadata(metadata)
    
#     return file_record


# def update_file_record(
#     file_name: str, 
#     chunks_count: int,
#     user_id: Optional[str] = None
# ):
#     """
#     Update file record after processing
    
#     Args:
#         file_name: Name of the file
#         chunks_count: Number of chunks created
#         user_id: Optional user ID for filtering
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         # Match by file_name and optionally user_id
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             file_record["processed"] = True
#             file_record["status"] = "completed"
#             file_record["chunks_created"] = chunks_count
#             file_record["processed_at"] = datetime.now().isoformat()
#             break
    
#     save_metadata(metadata)


# def get_all_files(user_id: Optional[str] = None) -> List[Dict]:
#     """
#     Get all uploaded files, optionally filtered by user
    
#     Args:
#         user_id: Optional user ID to filter files
        
#     Returns:
#         List of file records
#     """
#     metadata = load_metadata()
#     files = metadata.get("files", [])
    
#     if user_id:
#         # Filter to only this user's files
#         files = [f for f in files if f.get("user_id") == user_id]
    
#     return files


# def get_file_by_name(
#     file_name: str,
#     user_id: Optional[str] = None
# ) -> Optional[Dict]:
#     """
#     Get specific file record
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
        
#     Returns:
#         File record or None
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             return file_record
    
#     return None


# def delete_file_record(
#     file_name: str,
#     user_id: Optional[str] = None
# ) -> bool:
#     """
#     Delete file record
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
        
#     Returns:
#         True if deleted, False otherwise
#     """
#     metadata = load_metadata()
    
#     original_count = len(metadata["files"])
    
#     # Filter out the file to delete
#     if user_id:
#         # Only delete if belongs to user
#         metadata["files"] = [
#             f for f in metadata["files"] 
#             if not (f["file_name"] == file_name and f.get("user_id") == user_id)
#         ]
#     else:
#         # Legacy mode: delete any matching file
#         metadata["files"] = [
#             f for f in metadata["files"] 
#             if f["file_name"] != file_name
#         ]
    
#     if len(metadata["files"]) < original_count:
#         save_metadata(metadata)
#         return True
    
#     return False


# def get_file_stats(user_id: Optional[str] = None) -> Dict:
#     """
#     Get statistics about uploaded files
    
#     Args:
#         user_id: Optional user ID to filter stats
        
#     Returns:
#         Dictionary with file statistics
#     """
#     files = get_all_files(user_id=user_id)
    
#     total_files = len(files)
#     processed_files = sum(1 for f in files if f.get("processed", False))
#     total_chunks = sum(f.get("chunks_created", 0) for f in files)
#     total_size = sum(f.get("file_size", 0) for f in files)
    
#     file_types = {}
#     for f in files:
#         ftype = f.get("file_type", "unknown")
#         file_types[ftype] = file_types.get(ftype, 0) + 1
    
#     stats = {
#         "total_files": total_files,
#         "processed_files": processed_files,
#         "total_chunks": total_chunks,
#         "total_size_bytes": total_size,
#         "file_types_distribution": file_types
#     }
    
#     if user_id:
#         stats["user_id"] = user_id
    
#     return stats


# def mark_file_as_completed(
#     file_name: str,
#     user_id: Optional[str] = None
# ):
#     """
#     Mark file as completed
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             file_record["status"] = "completed"
#             break
    
#     save_metadata(metadata)


# def file_belongs_to_user(file_name: str, user_id: str) -> bool:
#     """
#     Check if a file belongs to a specific user
    
#     Args:
#         file_name: Name of the file
#         user_id: User ID to check
        
#     Returns:
#         True if file belongs to user, False otherwise
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         if (file_record["file_name"] == file_name and 
#             file_record.get("user_id") == user_id):
#             return True
    
#     return False


# def get_user_files_summary(user_id: str) -> Dict:
#     """
#     Get a summary of a user's files
    
#     Args:
#         user_id: User ID
        
#     Returns:
#         Dictionary with summary
#     """
#     files = get_all_files(user_id=user_id)
    
#     return {
#         "user_id": user_id,
#         "total_files": len(files),
#         "processed_files": sum(1 for f in files if f.get("processed")),
#         "pending_files": sum(1 for f in files if not f.get("processed")),
#         "recent_files": sorted(
#             files, 
#             key=lambda x: x.get("uploaded_at", ""), 
#             reverse=True
#         )[:5]  # Last 5 files
#     }


# # --------------------------------------------------
# # MIGRATION HELPER
# # --------------------------------------------------

# def migrate_legacy_files_to_user(user_id: str):
#     """
#     Helper function to migrate files that don't have user_id
#     to a specific user
    
#     Args:
#         user_id: User ID to assign legacy files to
#     """
#     metadata = load_metadata()
    
#     migrated_count = 0
    
#     for file_record in metadata["files"]:
#         if "user_id" not in file_record:
#             file_record["user_id"] = user_id
#             migrated_count += 1
    
#     if migrated_count > 0:
#         save_metadata(metadata)
#         print(f"✅ Migrated {migrated_count} files to user {user_id}")
    
#     return migrated_count

# """
# File Management System with User Isolation
# Tracks uploaded files and their processing status per user
# """

# import json
# import os
# from datetime import datetime
# from pathlib import Path
# from typing import List, Dict, Optional

# RESOURCES_DIR = Path("./resources")
# METADATA_FILE = RESOURCES_DIR / ".file_metadata.json"


# def ensure_resources_dir():
#     """Ensure resources directory exists"""
#     RESOURCES_DIR.mkdir(exist_ok=True)


# def ensure_user_dir(user_id: str):
#     """Ensure user-specific directory exists"""
#     user_dir = RESOURCES_DIR / user_id
#     user_dir.mkdir(exist_ok=True)
#     return user_dir


# def load_metadata() -> Dict:
#     """Load file metadata from JSON"""
#     ensure_resources_dir()
    
#     if METADATA_FILE.exists():
#         try:
#             with open(METADATA_FILE, 'r') as f:
#                 return json.load(f)
#         except:
#             return {"files": []}
#     return {"files": []}


# def save_metadata(metadata: Dict):
#     """Save file metadata to JSON"""
#     ensure_resources_dir()
#     with open(METADATA_FILE, 'w') as f:
#         json.dump(metadata, f, indent=2)


# def add_file_record(
#     file_name: str, 
#     file_type: str, 
#     file_size: int,
#     user_id: Optional[str] = None
# ) -> Dict:
#     """
#     Add a new file record with optional user association
    
#     Args:
#         file_name: Name of the file
#         file_type: Type/extension of file
#         file_size: Size in bytes
#         user_id: Optional user ID for multi-user systems
        
#     Returns:
#         Dictionary with file record
#     """
#     metadata = load_metadata()
    
#     file_record = {
#         "id": len(metadata["files"]) + 1,
#         "file_name": file_name,
#         "file_type": file_type,
#         "file_size": file_size,
#         "status": "uploaded",
#         "uploaded_at": datetime.now().isoformat(),
#         "processed": False,
#         "chunks_created": 0
#     }
    
#     # Add user_id if provided
#     if user_id:
#         file_record["user_id"] = user_id
    
#     metadata["files"].append(file_record)
#     save_metadata(metadata)
    
#     return file_record


# def update_file_record(
#     file_name: str, 
#     chunks_count: int,
#     user_id: Optional[str] = None
# ):
#     """
#     Update file record after processing
    
#     Args:
#         file_name: Name of the file
#         chunks_count: Number of chunks created
#         user_id: Optional user ID for filtering
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         # Match by file_name and optionally user_id
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             file_record["processed"] = True
#             file_record["status"] = "completed"
#             file_record["chunks_created"] = chunks_count
#             file_record["processed_at"] = datetime.now().isoformat()
#             break
    
#     save_metadata(metadata)


# def get_all_files(user_id: Optional[str] = None) -> List[Dict]:
#     """
#     Get all uploaded files, optionally filtered by user
    
#     Args:
#         user_id: Optional user ID to filter files
        
#     Returns:
#         List of file records
#     """
#     metadata = load_metadata()
#     files = metadata.get("files", [])
    
#     if user_id:
#         # Filter to only this user's files
#         files = [f for f in files if f.get("user_id") == user_id]
    
#     return files


# def get_file_by_name(
#     file_name: str,
#     user_id: Optional[str] = None
# ) -> Optional[Dict]:
#     """
#     Get specific file record
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
        
#     Returns:
#         File record or None
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             return file_record
    
#     return None


# def delete_file_record(
#     file_name: str,
#     user_id: Optional[str] = None
# ) -> bool:
#     """
#     Delete file record
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
        
#     Returns:
#         True if deleted, False otherwise
#     """
#     metadata = load_metadata()
    
#     original_count = len(metadata["files"])
    
#     # Filter out the file to delete
#     if user_id:
#         # Only delete if belongs to user
#         metadata["files"] = [
#             f for f in metadata["files"] 
#             if not (f["file_name"] == file_name and f.get("user_id") == user_id)
#         ]
#     else:
#         # Legacy mode: delete any matching file
#         metadata["files"] = [
#             f for f in metadata["files"] 
#             if f["file_name"] != file_name
#         ]
    
#     if len(metadata["files"]) < original_count:
#         save_metadata(metadata)
#         return True
    
#     return False


# def get_file_stats(user_id: Optional[str] = None) -> Dict:
#     """
#     Get statistics about uploaded files
    
#     Args:
#         user_id: Optional user ID to filter stats
        
#     Returns:
#         Dictionary with file statistics
#     """
#     files = get_all_files(user_id=user_id)
    
#     total_files = len(files)
#     processed_files = sum(1 for f in files if f.get("processed", False))
#     total_chunks = sum(f.get("chunks_created", 0) for f in files)
#     total_size = sum(f.get("file_size", 0) for f in files)
    
#     file_types = {}
#     for f in files:
#         ftype = f.get("file_type", "unknown")
#         file_types[ftype] = file_types.get(ftype, 0) + 1
    
#     stats = {
#         "total_files": total_files,
#         "processed_files": processed_files,
#         "total_chunks": total_chunks,
#         "total_size_bytes": total_size,
#         "file_types_distribution": file_types
#     }
    
#     if user_id:
#         stats["user_id"] = user_id
    
#     return stats


# def mark_file_as_completed(
#     file_name: str,
#     user_id: Optional[str] = None
# ):
#     """
#     Mark file as completed
    
#     Args:
#         file_name: Name of the file
#         user_id: Optional user ID for filtering
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         file_match = file_record["file_name"] == file_name
#         user_match = (user_id is None or 
#                      file_record.get("user_id") == user_id)
        
#         if file_match and user_match:
#             file_record["status"] = "completed"
#             break
    
#     save_metadata(metadata)


# def file_belongs_to_user(file_name: str, user_id: str) -> bool:
#     """
#     Check if a file belongs to a specific user
    
#     Args:
#         file_name: Name of the file
#         user_id: User ID to check
        
#     Returns:
#         True if file belongs to user, False otherwise
#     """
#     metadata = load_metadata()
    
#     for file_record in metadata["files"]:
#         if (file_record["file_name"] == file_name and 
#             file_record.get("user_id") == user_id):
#             return True
    
#     return False


# def get_user_files_summary(user_id: str) -> Dict:
#     """
#     Get a summary of a user's files
    
#     Args:
#         user_id: User ID
        
#     Returns:
#         Dictionary with summary
#     """
#     files = get_all_files(user_id=user_id)
    
#     return {
#         "user_id": user_id,
#         "total_files": len(files),
#         "processed_files": sum(1 for f in files if f.get("processed")),
#         "pending_files": sum(1 for f in files if not f.get("processed")),
#         "recent_files": sorted(
#             files, 
#             key=lambda x: x.get("uploaded_at", ""), 
#             reverse=True
#         )[:5]  # Last 5 files
#     }


# # --------------------------------------------------
# # MIGRATION HELPER
# # --------------------------------------------------

# def migrate_legacy_files_to_user(user_id: str):
#     """
#     Helper function to migrate files that don't have user_id
#     to a specific user
    
#     Args:
#         user_id: User ID to assign legacy files to
#     """
#     metadata = load_metadata()
    
#     migrated_count = 0
    
#     for file_record in metadata["files"]:
#         if "user_id" not in file_record:
#             file_record["user_id"] = user_id
#             migrated_count += 1
    
#     if migrated_count > 0:
#         save_metadata(metadata)
#         print(f"✅ Migrated {migrated_count} files to user {user_id}")
    
#     return migrated_count

# """
# File Management System
# Tracks uploaded files and their processing status
# """

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict

RESOURCES_DIR = Path("./resources")
METADATA_FILE = RESOURCES_DIR / ".file_metadata.json"


def ensure_resources_dir():
    """Ensure resources directory exists"""
    RESOURCES_DIR.mkdir(exist_ok=True)


def load_metadata() -> Dict:
    """Load file metadata from JSON"""
    ensure_resources_dir()
    
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"files": []}
    return {"files": []}


def save_metadata(metadata: Dict):
    """Save file metadata to JSON"""
    ensure_resources_dir()
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def add_file_record(file_name: str, file_type: str, file_size: int) -> Dict:
    """Add a new file record"""
    metadata = load_metadata()
    
    file_record = {
        "id": len(metadata["files"]) + 1,
        "file_name": file_name,
        "file_type": file_type,
        "file_size": file_size,
        "status": "uploaded",
        "uploaded_at": datetime.now().isoformat(),
        "processed": False,
        "chunks_created": 0
    }
    
    metadata["files"].append(file_record)
    save_metadata(metadata)
    
    return file_record


def update_file_record(file_name: str, chunks_count: int):
    """Update file record after processing"""
    metadata = load_metadata()
    
    for file_record in metadata["files"]:
        if file_record["file_name"] == file_name:
            file_record["processed"] = True
            file_record["status"] = "completed"
            file_record["chunks_created"] = chunks_count
            file_record["processed_at"] = datetime.now().isoformat()
            break
    
    save_metadata(metadata)


def reset_file_chunks(file_name: str):
    """Reset file to pending after chunks are removed from vector DB (chunks only)."""
    metadata = load_metadata()
    for file_record in metadata["files"]:
        if file_record["file_name"] == file_name:
            file_record["processed"] = False
            file_record["status"] = "uploaded"
            file_record["chunks_created"] = 0
            file_record.pop("processed_at", None)
            break
    save_metadata(metadata)


def get_all_files() -> List[Dict]:
    """Get all uploaded files"""
    metadata = load_metadata()
    return metadata.get("files", [])


def get_file_by_name(file_name: str) -> Dict:
    """Get specific file record"""
    metadata = load_metadata()
    
    for file_record in metadata["files"]:
        if file_record["file_name"] == file_name:
            return file_record
    return None


def delete_file_record(file_name: str) -> bool:
    """Delete file record"""
    metadata = load_metadata()
    
    original_count = len(metadata["files"])
    metadata["files"] = [f for f in metadata["files"] if f["file_name"] != file_name]
    
    if len(metadata["files"]) < original_count:
        save_metadata(metadata)
        return True
    return False


def get_file_stats() -> Dict:
    """Get statistics about uploaded files"""
    files = get_all_files()
    
    total_files = len(files)
    processed_files = sum(1 for f in files if f.get("processed", False))
    total_chunks = sum(f.get("chunks_created", 0) for f in files)
    total_size = sum(f.get("file_size", 0) for f in files)
    
    file_types = {}
    for f in files:
        ftype = f.get("file_type", "unknown")
        file_types[ftype] = file_types.get(ftype, 0) + 1
    
    return {
        "total_files": total_files,
        "processed_files": processed_files,
        "total_chunks": total_chunks,
        "total_size_bytes": total_size,
        "file_types_distribution": file_types
    }


def mark_file_as_completed(file_name: str):
    """Mark file as completed"""
    metadata = load_metadata()
    
    for file_record in metadata["files"]:
        if file_record["file_name"] == file_name:
            file_record["status"] = "completed"
            break
    
    save_metadata(metadata)
