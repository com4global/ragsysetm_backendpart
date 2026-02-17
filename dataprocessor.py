"""
Data Processor Module with User Isolation
Handles:
1. Single document ingestion with user context
2. Folder-based ingestion (SharePoint / Google Drive style)
3. User-specific namespace isolation
"""

import os
from pathlib import Path
from typing import Dict, List
import hashlib

from chunker import chunk_pages
from embedder import embed_chunks
from vectorstore import store_in_pinecone
from file_processor import read_file, get_file_type


def create_user_namespace(user_id: str, file_type: str) -> str:
    """
    Create a unique namespace combining user_id and file_type
    Format: {file_type}-user-{hash}
    Example: pdf-user-a1b2c3d4
    """
    user_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
    return f"{file_type}-user-{user_hash}"


def process_file(
    file_path: str, 
    user_id: str = None,
    chunk_size: int = 900, 
    chunk_overlap: int = 150, 
    source: str = "single"
) -> Dict:
    """
    Process ONE file and store it in Pinecone with user-specific namespace.
    Supports large PDFs/textbooks via batch processing and chapter detection.
    
    Args:
        file_path: Path to the file
        user_id: User ID for isolation (required for multi-user systems)
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        source: Source identifier
        
    Returns:
        Dictionary with processing results
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_path = os.path.abspath(file_path)
    file_name = os.path.basename(file_path)
    file_type = get_file_type(file_path)
    
    # Create user-specific namespace if user_id provided
    if user_id:
        namespace = create_user_namespace(user_id, file_type)
    else:
        # Legacy mode - no user isolation
        namespace = file_type
    
    print("\n" + "=" * 70)
    print(f"📄 Processing file: {file_name}")
    print(f"📋 File type: {file_type}")
    print(f"👤 User ID: {user_id if user_id else 'None (legacy mode)'}")
    print(f"🔖 Namespace: {namespace}")
    print("=" * 70)
    # Check if this is a multimodal file (image, audio, video)
    MULTIMODAL_TYPES = {
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp',           # images
        'mp3', 'wav', 'ogg', 'flac', 'm4a',                    # audio
        'mp4', 'avi', 'mov', 'mkv', 'webm', 'mpeg', 'mpga'     # video
    }
    
    if file_type in MULTIMODAL_TYPES:
        # Delegate to multimodal processor for non-text files
        from multimodal_dataprocessor import process_multimodal_file
        print(f"🎨 Detected multimodal file type '{file_type}', delegating to multimodal processor...")
        result = process_multimodal_file(file_path)
        # Enrich result with user info
        result["user_id"] = user_id
        result["namespace"] = namespace
        result["chunks_created"] = result.get("chunks_created", 0)
        return result

    # 1. Read file (text-based files only)
    pages, _ = read_file(file_path)
    print(f"✅ Extracted {len(pages)} pages/rows/sections")
    
    # For large files, log chapter info if available
    chapters_found = set()
    for p in pages:
        ch = p.get("chapter", "")
        if ch:
            chapters_found.add(ch)
    if chapters_found:
        print(f"📚 Detected {len(chapters_found)} chapters/sections: {list(chapters_found)[:10]}")
    
    BATCH_SIZE = 50  # Process in batches to avoid memory/timeout issues
    embedded_chunks = []
    total_chunks = 0

    # 2. Process Page by Page to preserve metadata
    for page_obj in pages:
        # Use our fixed chunk_pages function
        chunks_from_this_page = chunk_pages(
            page_obj["text"], 
            chunk_size=chunk_size, 
            chunk_overlap=chunk_overlap
        )
        
        for text_chunk in chunks_from_this_page:
            # 3. Embed this specific chunk
            vector_list = embed_chunks([text_chunk])
            if not vector_list: 
                continue
            
            vector = vector_list[0] 
            
            # 4. Attach Metadata (including chapter and user_id)
            metadata = {
                "text": text_chunk,
                "page": str(page_obj["page"]), 
                "doc_name": page_obj["doc_name"],
                "path": page_obj["path"]
            }
            
            # Add chapter info if available
            chapter = page_obj.get("chapter", "")
            if chapter:
                metadata["chapter"] = chapter
            
            # Add user_id to metadata for additional filtering
            if user_id:
                metadata["user_id"] = user_id
            
            embedded_chunks.append({
                "embedding": vector,
                "metadata": metadata
            })
            total_chunks += 1
            
            # 5. Batch upsert — flush every BATCH_SIZE chunks
            if len(embedded_chunks) >= BATCH_SIZE:
                store_in_pinecone(embedded_chunks, namespace)
                print(f"  📌 Batch stored: {total_chunks} chunks so far...")
                embedded_chunks = []

    # 6. Store remaining chunks
    if embedded_chunks:
        store_in_pinecone(embedded_chunks, namespace)
    
    print(f"📌 Stored {total_chunks} total chunks in namespace '{namespace}'")
    if chapters_found:
        print(f"📚 Chapters indexed: {len(chapters_found)}")

    return {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": file_type,
        "chunks_created": total_chunks,
        "chapters_found": len(chapters_found),
        "namespace": namespace,
        "user_id": user_id
    }


def process_folder(
    folder_path: str,
    user_id: str = None,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
    source: str = "sharepoint"
) -> List[Dict]:
    """
    Process ALL supported documents inside a folder with user context
    
    Args:
        folder_path: Path to folder containing files
        user_id: User ID for isolation
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        source: Source identifier
        
    Returns:
        List of processing results
    """
    folder = Path(folder_path)

    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Invalid folder path: {folder_path}")

    print("\n" + "=" * 70)
    print(f"📂 Processing folder: {folder_path}")
    print(f"👤 User ID: {user_id if user_id else 'None (legacy mode)'}")
    print(f"🔖 Source mode: {source}")
    print("=" * 70)

    results = []

    for file in folder.iterdir():
        if not file.is_file():
            continue

        try:
            result = process_file(
                file_path=str(file),
                user_id=user_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source=source
            )
            results.append(result)
        except Exception as e:
            print(f"⚠️ Failed processing {file.name}: {e}")

    print(f"\n✅ Folder ingestion complete. Files processed: {len(results)}")
    return results


def delete_user_file_vectors(user_id: str, filename: str):
    """
    Delete all vectors for a specific file belonging to a user
    Note: This requires tracking vector IDs or deleting entire user namespace
    
    Args:
        user_id: User ID
        filename: Name of the file to delete
    """
    try:
        # Get all file types to check namespaces
        from file_processor import get_supported_formats
        
        formats = get_supported_formats()
        
        for fmt in formats:
            # Remove the dot from format
            file_type = fmt.lstrip('.')
            namespace = create_user_namespace(user_id, file_type)
            
            print(f"🗑️ Checking namespace {namespace} for file {filename}")
            
            # Note: Pinecone doesn't support easy deletion by metadata
            # Best practice: Track vector IDs in your database
            # For now, we log the intention
            print(f"⚠️ To delete vectors for {filename}, implement ID tracking in database")
        
    except Exception as e:
        print(f"❌ Error deleting vectors: {e}")
        raise


def get_user_vectorstore_info(user_id: str, file_type: str = None) -> Dict:
    """
    Get information about user's vector store
    
    Args:
        user_id: User ID
        file_type: Optional file type filter
        
    Returns:
        Dictionary with namespace information
    """
    if file_type:
        namespace = create_user_namespace(user_id, file_type)
        return {
            "user_id": user_id,
            "file_type": file_type,
            "namespace": namespace
        }
    else:
        # Return info for all possible file types
        from file_processor import get_supported_formats
        
        formats = get_supported_formats()
        namespaces = []
        
        for fmt in formats:
            file_type = fmt.lstrip('.')
            namespace = create_user_namespace(user_id, file_type)
            namespaces.append({
                "file_type": file_type,
                "namespace": namespace
            })
        
        return {
            "user_id": user_id,
            "namespaces": namespaces
        }


# ==========================
# CLI ENTRY POINT
# ==========================

def run(path: str = None, user_id: str = None):
    """
    Entry point:
    - If path is a file → single file mode
    - If path is a folder → folder (SharePoint/Drive) mode
    
    Args:
        path: Path to file or folder
        user_id: Optional user ID for isolation
    """
    if path is None:
        path = "./resources/95c24a5e-3388-480b-b444-3645867bb6ef/snowfall.pdf"

    if os.path.isfile(path):
        return process_file(path, user_id=user_id, source="single")

    if os.path.isdir(path):
        return process_folder(path, user_id=user_id, source="sharepoint")

    raise ValueError(f"Invalid path: {path}")


if __name__ == "__main__":
    # Test with and without user_id
    # Without user_id (legacy mode)
    # run()
    
    # With user_id (user isolation mode)
    run(user_id="95c24a5e-3388-480b-b444-3645867bb6ef")





# """
# Data Processor Module
# Handles:
# 1. Single document ingestion
# 2. Folder-based ingestion (SharePoint / Google Drive style)
# """
# # dataprocessor.py
# import os
# from pathlib import Path
# from typing import Dict, List

# from chunker import chunk_pages  # This now matches chunker.py
# from embedder import embed_chunks
# from vectorstore import store_in_pinecone
# from file_processor import read_file, get_file_type

# def process_file(file_path: str, chunk_size: int = 900, chunk_overlap: int = 150, source: str = "single") -> Dict:
#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     file_path = os.path.abspath(file_path)
#     file_name = os.path.basename(file_path)
#     file_type = get_file_type(file_path)
#     namespace = file_type # DEFINE NAMESPACE HERE

#     # 1. Read file
#     pages, _ = read_file(file_path)
    
#     embedded_chunks = []
#     total_chunks = 0

#     # 2. Process Page by Page to preserve metadata
#     for page_obj in pages:
#         # Use our fixed chunk_pages function
#         chunks_from_this_page = chunk_pages(
#             page_obj["text"], 
#             chunk_size=chunk_size, 
#             chunk_overlap=chunk_overlap
#         )
        
#         for text_chunk in chunks_from_this_page:
#             # 3. Embed this specific chunk
#             vector_list = embed_chunks([text_chunk])
#             if not vector_list: continue
            
#             vector = vector_list[0] 
            
#             # 4. Attach Metadata
#             embedded_chunks.append({
#                 "embedding": vector,
#                 "metadata": {
#                     "text": text_chunk,
#                     "page": str(page_obj["page"]), 
#                     "doc_name": page_obj["doc_name"],
#                     "path": page_obj["path"]
#                 }
#             })
#             total_chunks += 1

#     # 5. Store in Pinecone
#     store_in_pinecone(embedded_chunks, namespace)

#     return {
#         "file_name": file_name,
#         "file_path": file_path,
#         "file_type": file_type,
#         "chunks_created": total_chunks,
#         "namespace": namespace
#     }



# import os
# from pathlib import Path
# from typing import Dict, List

# from chunker import chunk_pages
# from embedder import embed_chunks
# from vectorstore import store_in_pinecone
# from file_processor import read_file, get_file_type


# # ==========================
# # SINGLE FILE MODE
# # ==========================

# def process_file(
#     file_path: str,
#     chunk_size: int = 900,
#     chunk_overlap: int = 150,
#     source: str = "single"
# ) -> Dict:
#     """
#     Process ONE file and store it in Pinecone with page-level metadata.
#     Works for: PDF, Excel, CSV, TXT, Word, XML
#     """

#     if not os.path.exists(file_path):
#         raise FileNotFoundError(f"File not found: {file_path}")

#     file_path = os.path.abspath(file_path)
#     file_name = os.path.basename(file_path)
#     file_type = get_file_type(file_path)

#     print("\n" + "=" * 70)
#     print(f"📄 Processing file: {file_name}")
#     print(f"📋 File type: {file_type}")
#     print(f"🔖 Source mode: {source}")
#     print("=" * 70)

#     # 1️⃣ Read file (returns structured pages with page identifiers)
#     pages, detected_type = read_file(file_path)
#     print(f"✅ Extracted {len(pages)} pages/rows/sections")
#     page_texts = [p["text"] for p in pages]
#     print(f"📄 [page_texts]: {page_texts}")


#     # 2️⃣ Chunk pages (preserves page metadata)
#     print(type(page_texts))
#     chunks_text = chunk_pages(page_texts, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
#     print(f"✂️  Created {len(chunks_text)} chunks_text")
#     chunks = []

#     for i, text in enumerate(chunks_text):
#         src_page = pages[min(i, len(pages) - 1)]

#         chunks.append({
#             "text": text,
#             "page": src_page["page"],
#             "doc_name": src_page["doc_name"],
#             "path": src_page["path"]
#             })
#     # 3️⃣ Embed chunks
#     # 3️⃣ Embed chunks (TEXT ONLY)
#     vectors = embed_chunks([c["text"] for c in chunks])
#     print(f"🧠 Embedded {len(vectors)} chunks")

#     # 4️⃣ Combine embeddings + metadata (CRITICAL STEP)
#     # embedded_chunks = []

#     # for chunk, embedding in zip(chunks, vectors):
#     #     embedded_chunks.append({
#     #         "embedding": embedding,
#     #         "metadata": {
#     #         "text": chunk["text"],
#     #         "page": chunk["page"],
#     #         "doc_name": chunk["doc_name"],
#     #         "path": chunk["path"]
#     #     }
#     # })

#     # # 5️⃣ Store in Pinecone
#     # namespace = file_type
#     # store_in_pinecone(embedded_chunks, namespace)
#     embedded_chunks = []
    
#     for page_obj in pages:
#         # Chunk EACH page individually so we know exactly where the text came from
#         chunks_from_page = chunk_pages(page_obj["text"], chunk_size, chunk_overlap)
        
#         for text_chunk in chunks_from_page:
#             # Get embedding for this specific chunk
#             vector = embed_chunks([text_chunk])[0] 
            
#             embedded_chunks.append({
#                 "embedding": vector,
#                 "metadata": {
#                     "text": text_chunk,
#                     "page": str(page_obj["page"]), # Ensure string
#                     "doc_name": page_obj["doc_name"],
#                     "path": page_obj["path"]
#                 }
#             })

#     # Now store the correctly mapped chunks
#     store_in_pinecone(embedded_chunks, namespace)
#     print(f"📌 Stored in Pinecone (namespace='{namespace}')")

#     return {
#         "file_name": file_name,
#         "file_type": file_type,
#         "source": source,
#         "pages_extracted": len(pages),
#         "chunks_created": len(chunks),
#         "namespace": namespace
#     }


# ==========================
# FOLDER MODE (SharePoint / Drive)
# ==========================

def process_folder(
    folder_path: str,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
    source: str = "sharepoint"
) -> List[Dict]:
    """
    Process ALL supported documents inside a folder.
    This represents SharePoint / Google Drive / S3 ingestion.
    """

    folder = Path(folder_path)

    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Invalid folder path: {folder_path}")

    print("\n" + "=" * 70)
    print(f"📂 Processing folder: {folder_path}")
    print(f"🔖 Source mode: {source}")
    print("=" * 70)

    results = []

    for file in folder.iterdir():
        if not file.is_file():
            continue

        try:
            result = process_file(
                file_path=str(file),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                source=source
            )
            results.append(result)
        except Exception as e:
            print(f"⚠️ Failed processing {file.name}: {e}")

    print(f"\n✅ Folder ingestion complete. Files processed: {len(results)}")
    return results


# ==========================
# CLI ENTRY POINT
# ==========================

def run(path: str = None):
    """
    Entry point:
    - If path is a file → single file mode
    - If path is a folder → folder (SharePoint/Drive) mode
    """

    if path is None:
        path = "./resources/HRPolicy.pdf"

    if os.path.isfile(path):
        return process_file(path, source="single")

    if os.path.isdir(path):
        return process_folder(path, source="sharepoint")

    raise ValueError(f"Invalid path: {path}")


if __name__ == "__main__":
    run()
