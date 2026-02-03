"""
Data Processor Module
Handles:
1. Single document ingestion
2. Folder-based ingestion (SharePoint / Google Drive style)
"""
# dataprocessor.py
import os
from pathlib import Path
from typing import Dict, List

from chunker import chunk_pages  # This now matches chunker.py
from embedder import embed_chunks
from vectorstore import store_in_pinecone
from file_processor import read_file, get_file_type

def process_file(file_path: str, chunk_size: int = 900, chunk_overlap: int = 150, source: str = "single") -> Dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_path = os.path.abspath(file_path)
    file_name = os.path.basename(file_path)
    file_type = get_file_type(file_path)
    namespace = file_type # DEFINE NAMESPACE HERE

    # 1. Read file
    pages, _ = read_file(file_path)
    
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
            if not vector_list: continue
            
            vector = vector_list[0] 
            
            # 4. Attach Metadata
            embedded_chunks.append({
                "embedding": vector,
                "metadata": {
                    "text": text_chunk,
                    "page": str(page_obj["page"]), 
                    "doc_name": page_obj["doc_name"],
                    "path": page_obj["path"]
                }
            })
            total_chunks += 1

    # 5. Store in Pinecone
    store_in_pinecone(embedded_chunks, namespace)

    return {
        "file_name": file_name,
        "file_path": file_path,
        "file_type": file_type,
        "chunks_created": total_chunks,
        "namespace": namespace
    }



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
