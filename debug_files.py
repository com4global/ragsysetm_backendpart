from pathlib import Path
import json

RESOURCES_DIR = Path("resources")
print(f"RESOURCES_DIR: {RESOURCES_DIR.absolute()}")
print(f"Exists: {RESOURCES_DIR.exists()}")

def _read_local_file_metadata():
    """Read file metadata from local .file_metadata.json"""
    import json as _json
    metadata_path = RESOURCES_DIR / ".file_metadata.json"
    if not metadata_path.exists():
        print("Metadata file not found")
        return []
    
    try:
        with open(metadata_path, "r") as f:
            metadata = _json.load(f)
        
        files = []
        for file_meta in metadata.get("files", []):
            filename = file_meta.get("file_name", "")
            if not filename:
                continue
            
            # Get actual file size from disk
            file_path = RESOURCES_DIR / filename
            exists = file_path.exists()
            # print(f"Checking {file_path}: {exists}")
            file_size = int(file_path.stat().st_size) if exists else file_meta.get("file_size", 0)
            
            files.append({
                "filename": filename,
                "file_name": filename,
                "file_type": file_meta.get("file_type", "document"),
                "file_size": file_size,
                "chunks_created": file_meta.get("chunks_created", 0),
                "processed": file_meta.get("processed", False),
                "status": "completed" if file_meta.get("processed") else "pending",
                "uploaded_at": file_meta.get("uploaded_at", ""),
            })
        
        return files
    except Exception as e:
        print(f"Error: {e}")
        return []

files = _read_local_file_metadata()
print(f"Found {len(files)} files")
for f in files:
    print(f" - {f['filename']} ({f['status']})")
