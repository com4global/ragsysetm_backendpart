"""
File Management System
Tracks uploaded files and their processing status
"""

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
