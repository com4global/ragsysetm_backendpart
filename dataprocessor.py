from pdfreader import read_pdf
from chunker import chunk_pages
from embedder import embed_chunks
from vectorstore import store_in_pinecone
from file_processor import read_file, get_file_type
from typing import List
import os

def process_file(file_path: str, chunk_size: int = 900, chunk_overlap: int = 150):
    """
    Process a file (any supported format) and store in vector DB
    Supports: PDF, Excel, CSV, TXT, Word, XML
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_name = os.path.basename(file_path)
    file_type = get_file_type(file_path)
    
    print(f"📄 Processing file: {file_name}")
    print(f"📋 File type: {file_type}")
    
    # Read file
    pages, detected_type = read_file(file_path)
    print(f"✅ Extracted {len(pages)} pages from {file_name}")
    
    # Chunk the text
    hunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    print(f"✂️  Created {len(hunks)} chunks")
    
    # Embed chunks
    embedded_chunks = embed_chunks(hunks)
    print(f"🧠 Embedded {len(embedded_chunks)} chunks")
    
    # Store in Pinecone
    namespace = file_type  # Use file type as namespace for organization
    store_in_pinecone(hunks, embedded_chunks, namespace=namespace)
    print(f"📌 Stored in Pinecone (namespace: {namespace})")
    
    return {
        "file_name": file_name,
        "file_type": file_type,
        "pages_extracted": len(pages),
        "chunks_created": len(hunks),
        "namespace": namespace
    }


def run(file_path: str = None):
    """
    Main function - process file dynamically
    If no file_path provided, uses default HR policy
    """
    if file_path is None:
        file_path = "./resources/HRPolicy.pdf"
    
    try:
        result = process_file(file_path)
        print(f"\n✨ Successfully processed: {result['file_name']}")
        return result
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

    
if __name__ == "__main__":
    # Default: process HR policy PDF
    run()