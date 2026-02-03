# """
# DEBUG PIPELINE - Step-by-step verification of file upload → processing → storage → Q&A
# Helps verify that uploaded files are correctly processed and searchable
# """

# import os
# import json
# from pathlib import Path
# from file_processor import read_file, get_file_type, get_supported_formats
# from chunker import chunk_pages
# from embedder import embed_chunks, embed_User_query
# from vectorstore import search_in_pinecone, index
# from llm import query_llm_with_context
# from dataprocessor import process_file
# from file_manager import get_all_files, get_file_stats

# RESOURCES_DIR = Path("./resources")

# # ============ STEP 1: VERIFY FILE EXISTS ============
# def debug_step_1_file_exists(filename: str):
#     """Check if file exists and get basic info"""
#     print("\n" + "="*60)
#     print("STEP 1: VERIFY FILE EXISTS & READABLE")
#     print("="*60)
    
#     file_path = RESOURCES_DIR / filename
    
#     if not file_path.exists():
#         print(f"❌ FILE NOT FOUND: {file_path}")
#         print(f"   Expected location: {RESOURCES_DIR}")
#         print(f"   Available files: {list(RESOURCES_DIR.glob('*'))}")
#         return False
    
#     print(f"✅ File exists: {file_path}")
#     print(f"📊 File size: {file_path.stat().st_size} bytes")
#     print(f"📝 File type: {get_file_type(str(file_path))}")
#     return True


# # ============ STEP 2: VERIFY FILE READING ============
# def debug_step_2_read_file(filename: str):
#     """Verify file content can be extracted"""
#     print("\n" + "="*60)
#     print("STEP 2: VERIFY FILE READING & CONTENT EXTRACTION")
#     print("="*60)
    
#     file_path = RESOURCES_DIR / filename
    
#     try:
#         pages, file_type = read_file(str(file_path))
#         print(f"✅ File read successfully!")
#         print(f"📄 Pages extracted: {len(pages)}")
#         print(f"📋 File type detected: {file_type}")
        
#         # Show sample of first page
#         if pages:
#             first_page = pages[0]
#             sample_length = min(200, len(first_page))
#             print(f"\n📖 Sample of first page (first {sample_length} chars):")
#             print(f"   {first_page[:sample_length]}...")
#             print(f"   Total characters in first page: {len(first_page)}")
        
#         return pages, file_type
#     except Exception as e:
#         print(f"❌ ERROR reading file: {str(e)}")
#         return None, None


# # ============ STEP 3: VERIFY CHUNKING ============
# def debug_step_3_chunking(pages):
#     """Verify text is properly chunked"""
#     print("\n" + "="*60)
#     print("STEP 3: VERIFY TEXT CHUNKING")
#     print("="*60)
    
#     if not pages:
#         print("❌ No pages to chunk!")
#         return None
    
#     try:
#         chunks = chunk_pages(pages, chunk_size=900, chunk_overlap=150)
#         print(f"✅ Chunking successful!")
#         print(f"📦 Total chunks created: {len(chunks)}")
        
#         # Show statistics
#         chunk_sizes = [len(chunk) for chunk in chunks]
#         print(f"📊 Chunk size stats:")
#         print(f"   Min: {min(chunk_sizes)} chars")
#         print(f"   Max: {max(chunk_sizes)} chars")
#         print(f"   Avg: {sum(chunk_sizes)/len(chunk_sizes):.0f} chars")
        
#         # Show samples
#         print(f"\n📝 Sample chunks:")
#         for i, chunk in enumerate(chunks[:3]):
#             print(f"\n   CHUNK {i}:")
#             print(f"   {chunk[:150]}...")
        
#         return chunks
#     except Exception as e:
#         print(f"❌ ERROR during chunking: {str(e)}")
#         return None


# # ============ STEP 4: VERIFY EMBEDDINGS ============
# def debug_step_4_embeddings(chunks):
#     """Verify chunks are converted to embeddings"""
#     print("\n" + "="*60)
#     print("STEP 4: VERIFY EMBEDDINGS GENERATION")
#     print("="*60)
    
#     if not chunks:
#         print("❌ No chunks to embed!")
#         return None
    
#     try:
#         embeddings = embed_chunks(chunks)
#         print(f"✅ Embeddings generated successfully!")
#         print(f"🧠 Total embeddings: {len(embeddings)}")
        
#         if embeddings:
#             print(f"📏 Embedding dimensions: {len(embeddings[0])}")
#             print(f"🔢 First embedding sample (first 10 values):")
#             print(f"   {embeddings[0][:10]}")
        
#         return embeddings
#     except Exception as e:
#         print(f"❌ ERROR generating embeddings: {str(e)}")
#         return None


# # ============ STEP 5: VERIFY PINECONE STORAGE ============
# def debug_step_5_pinecone_storage(filename: str, file_type: str):
#     """Check what's stored in Pinecone"""
#     print("\n" + "="*60)
#     print("STEP 5: VERIFY PINECONE DATABASE STORAGE")
#     print("="*60)
    
#     try:
#         # Get index stats
#         index_stats = index.describe_index_stats()
#         print(f"✅ Connected to Pinecone!")
#         print(f"📊 Total vectors in index: {index_stats.total_vector_count}")
#         print(f"📂 Namespaces in index: {list(index_stats.namespaces.keys())}")
        
#         # Check specific namespace
#         namespace = file_type  # Uses file_type as namespace
#         if namespace in index_stats.namespaces:
#             ns_stats = index_stats.namespaces[namespace]
#             print(f"\n✅ Namespace '{namespace}' found!")
#             print(f"   Vectors in namespace: {ns_stats.vector_count}")
#         else:
#             print(f"\n⚠️  Namespace '{namespace}' NOT found in index")
#             print(f"   This file type may not have been processed yet")
        
#         print(f"\n📋 All namespaces and counts:")
#         for ns, stats in index_stats.namespaces.items():
#             print(f"   {ns}: {stats.vector_count} vectors")
        
#         return True
#     except Exception as e:
#         print(f"❌ ERROR connecting to Pinecone: {str(e)}")
#         return False


# # ============ STEP 6: TEST RETRIEVAL ============
# def debug_step_6_retrieval(query: str, namespace: str = ""):
#     """Test if queries can retrieve relevant chunks"""
#     print("\n" + "="*60)
#     print("STEP 6: TEST QUERY RETRIEVAL FROM PINECONE")
#     print("="*60)
#     print(f"🔍 Testing query: '{query}'")
    
#     try:
#         # Embed the query
#         query_vector = embed_User_query(query)
#         print(f"✅ Query embedded successfully!")
#         print(f"   Query vector dimensions: {len(query_vector)}")
        
#         # Search Pinecone
#         matched_chunks = search_in_pinecone(query_vector, top_k=4, namespace=namespace)
        
#         print(f"✅ Search completed!")
#         print(f"📌 Matched chunks found: {len(matched_chunks)}")
        
#         if matched_chunks:
#             for i, chunk in enumerate(matched_chunks, 1):
#                 print(f"\n   MATCH {i}:")
#                 print(f"   {chunk[:200]}...")
#         else:
#             print(f"⚠️  NO MATCHES FOUND!")
#             print(f"   Try a different query or verify file was processed")
        
#         return matched_chunks
#     except Exception as e:
#         print(f"❌ ERROR during retrieval: {str(e)}")
#         return None


# # ============ STEP 7: TEST LLM RESPONSE ============
# def debug_step_7_llm_response(query: str, matched_chunks):
#     """Test if LLM generates proper response"""
#     print("\n" + "="*60)
#     print("STEP 7: TEST LLM RESPONSE GENERATION")
#     print("="*60)
#     print(f"💬 Query: '{query}'")
    
#     try:
#         response = query_llm_with_context(query, matched_chunks)
#         print(f"✅ LLM response generated!")
#         print(f"\n📝 RESPONSE:")
#         print(f"{response}")
        
#         # Check response quality
#         if not response or response.strip() == "":
#             print(f"\n⚠️  WARNING: Empty response!")
#         elif "don't have" in response.lower() or "no information" in response.lower():
#             print(f"\n⚠️  WARNING: LLM couldn't find relevant information")
#         else:
#             print(f"\n✅ Response looks good!")
        
#         return response
#     except Exception as e:
#         print(f"❌ ERROR generating response: {str(e)}")
#         return None


# # ============ STEP 8: FULL PIPELINE TEST ============
# def debug_step_8_full_pipeline(query: str, filename: str = None, namespace: str = ""):
#     """Test complete end-to-end pipeline"""
#     print("\n" + "="*60)
#     print("STEP 8: FULL END-TO-END PIPELINE TEST")
#     print("="*60)
#     print(f"🔄 Testing complete pipeline for query: '{query}'")
    
#     try:
#         if filename:
#             print(f"\n📥 Using specific file: {filename}")
#             namespace = get_file_type(str(RESOURCES_DIR / filename))
        
#         # Embed query
#         query_vector = embed_User_query(query)
        
#         # Search with namespace if specified
#         matched_chunks = search_in_pinecone(query_vector, top_k=4, namespace=namespace)
        
#         # Generate response
#         response = query_llm_with_context(query, matched_chunks)
        
#         print(f"✅ Pipeline executed successfully!")
#         print(f"📌 Chunks retrieved: {len(matched_chunks)}")
#         print(f"💬 Response: {response[:300]}...")
        
#         return {
#             "query": query,
#             "chunks_retrieved": len(matched_chunks),
#             "response": response,
#             "namespace": namespace
#         }
#     except Exception as e:
#         print(f"❌ ERROR in pipeline: {str(e)}")
#         return None


# # ============ METADATA CHECK ============
# def debug_metadata():
#     """Check file metadata in database"""
#     print("\n" + "="*60)
#     print("FILE METADATA CHECK")
#     print("="*60)
    
#     try:
#         files = get_all_files()
#         stats = get_file_stats()
        
#         print(f"✅ Files uploaded: {len(files)}")
#         for file in files:
#             print(f"   📄 {file['filename']}")
#             print(f"      Type: {file['file_type']}")
#             print(f"      Size: {file['file_size']} bytes")
#             print(f"      Chunks: {file.get('chunks_created', 'N/A')}")
        
#         print(f"\n📊 Statistics:")
#         print(f"   Total files: {stats.get('total_files', 0)}")
#         print(f"   Total chunks: {stats.get('total_chunks', 0)}")
        
#     except Exception as e:
#         print(f"❌ ERROR reading metadata: {str(e)}")


# # ============ MAIN DEBUGGING FLOW ============
# def run_full_debug(filename: str, test_query: str):
#     """Run complete debugging sequence"""
#     print("\n\n")
#     print("╔" + "═"*58 + "╗")
#     print("║" + " "*58 + "║")
#     print("║" + "  RAG PIPELINE DEBUGGING TOOL".center(58) + "║")
#     print("║" + " "*58 + "║")
#     print("╚" + "═"*58 + "╝")
    
#     # Step 1: File exists
#     if not debug_step_1_file_exists(filename):
#         return
    
#     # Step 2: Read file
#     pages, file_type = debug_step_2_read_file(filename)
#     if not pages:
#         return
    
#     # Step 3: Chunk
#     chunks = debug_step_3_chunking(pages)
#     if not chunks:
#         return
    
#     # Step 4: Embed
#     embeddings = debug_step_4_embeddings(chunks)
#     if not embeddings:
#         return
    
#     # Step 5: Check Pinecone storage
#     debug_step_5_pinecone_storage(filename, file_type)
    
#     # Step 6: Test retrieval
#     namespace = file_type
#     matched_chunks = debug_step_6_retrieval(test_query, namespace)
    
#     # Step 7: Test LLM
#     if matched_chunks:
#         debug_step_7_llm_response(test_query, matched_chunks)
    
#     # Step 8: Full pipeline
#     debug_step_8_full_pipeline(test_query, filename, namespace)
    
#     # Metadata check
#     debug_metadata()
    
#     print("\n" + "="*60)
#     print("✅ DEBUGGING COMPLETE")
#     print("="*60)


# if __name__ == "__main__":
#     # Example usage
#     filename = "financial-statements-2021.xlsx"  # Change to your file
#     test_query = "What was the revenue in 2021?"  # Change to your question
    
#     run_full_debug(filename, test_query)




################################# new debugging file #################################
"""
DEBUG PIPELINE - Page-number & citation aware
Run with:
    python3 debug_pipeline.py
"""

import json
from pathlib import Path
from typing import List, Dict

from scipy import stats

from file_processor import read_file, get_file_type
from chunker import chunk_pages
from embedder import embed_chunks, embed_User_query
from vectorstore import search_in_pinecone, index
from llm import query_llm_with_context
from file_manager import get_all_files, get_file_stats

RESOURCES_DIR = Path("./resources")

# -------------------------------------------------------------------
# Utility: Pretty print JSON safely
# -------------------------------------------------------------------
def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# -------------------------------------------------------------------
# Utility: Convert retrieved chunks into LLM-ready context
# -------------------------------------------------------------------
def format_context_for_llm(chunks: List[Dict]) -> str:
    """
    Converts structured chunks into citation-aware text for LLM
    """
    if not chunks:
        return ""

    blocks = []
    for c in chunks:
        blocks.append(
            f"[Source: {c['doc_name']} | Page: {c['page']} | Path: {c['path']}]\n"
            f"{c['text']}"
        )
    return "\n\n".join(blocks)


# -------------------------------------------------------------------
# STEP 1: Verify file exists
# -------------------------------------------------------------------
def step_1_file_exists(filename: str) -> bool:
    print("\n" + "=" * 70)
    print("STEP 1: FILE EXISTS CHECK")
    print("=" * 70)

    file_path = RESOURCES_DIR / filename
    if not file_path.exists():
        print("❌ FILE NOT FOUND")
        print("Expected:", file_path)
        print("Available:", list(RESOURCES_DIR.glob("*")))
        return False

    print("✅ File found:", file_path)
    print("Size:", file_path.stat().st_size, "bytes")
    print("Detected type:", get_file_type(str(file_path)))
    return True


# -------------------------------------------------------------------
# STEP 2: Verify file reading (STRUCTURED pages)
# -------------------------------------------------------------------
def step_2_read_file(filename: str):
    print("\n" + "=" * 70)
    print("STEP 2: FILE READING CHECK")
    print("=" * 70)

    pages, file_type = read_file(str(RESOURCES_DIR / filename))

    print("Pages extracted:", len(pages))
    assert isinstance(pages, list), "Pages must be a list"

    print("\nFIRST PAGE STRUCTURE:")
    pretty(pages[0])

    # Hard assertions (fail fast)
    for key in ["text", "page", "doc_name", "path"]:
        assert key in pages[0], f"Missing key '{key}' in page"

    return pages, file_type


# -------------------------------------------------------------------
# STEP 3: Chunking validation
# -------------------------------------------------------------------
def step_3_chunking(pages):
    print("\n" + "=" * 70)
    print("STEP 3: CHUNKING CHECK")
    print("=" * 70)

    chunks = chunk_pages(pages)
    print("Chunks created:", len(chunks))

    print("\nFIRST CHUNK STRUCTURE:")
    pretty(chunks[0])

    for key in ["text", "page", "doc_name", "path"]:
        assert key in chunks[0], f"Missing key '{key}' in chunk"

    return chunks


# -------------------------------------------------------------------
# STEP 4: Embedding validation
# -------------------------------------------------------------------
def step_4_embeddings(chunks):
    print("\n" + "=" * 70)
    print("STEP 4: EMBEDDING CHECK")
    print("=" * 70)

    embeddings = embed_chunks(chunks)

    print("Embeddings generated:", len(embeddings))
    print("Embedding dimension:", len(embeddings[0]))

    return embeddings


# -------------------------------------------------------------------
# STEP 5: Pinecone storage check
# -------------------------------------------------------------------
def step_5_pinecone_check(file_type: str):
    print("\n" + "=" * 70)
    print("STEP 5: PINECONE STORAGE CHECK")
    print("=" * 70)

    stats = index.describe_index_stats()
    index.delete(delete_all=True, namespace="pdf")
    print("Total vectors:", stats.total_vector_count)
    print("Namespaces:", list(stats.namespaces.keys()))

    if file_type not in stats.namespaces:
        print("❌ Namespace missing:", file_type)
    else:
        print(
            f"✅ Namespace '{file_type}' vectors:",
            stats.namespaces[file_type].vector_count,
        )


# -------------------------------------------------------------------
# STEP 6: Retrieval validation
# -------------------------------------------------------------------
def step_6_retrieval(query: str, namespace: str):
    print("\n" + "=" * 70)
    print("STEP 6: RETRIEVAL CHECK")
    print("=" * 70)
    print("Query:", query)

    qv = embed_User_query(query)
    matches = search_in_pinecone(qv, namespace=namespace)

    print("Matches returned:", len(matches))

    if not matches:
        print("❌ NO MATCHES → STOP HERE")
        return []

    print("\nFIRST MATCH:")
    pretty(matches[0])

    for key in ["text", "page", "doc_name", "path"]:
        assert key in matches[0], f"Missing key '{key}' in retrieved chunk"

    return matches


# -------------------------------------------------------------------
# STEP 7: LLM input & response validation (MOST IMPORTANT)
# -------------------------------------------------------------------
def step_7_llm(query: str, matched_chunks):
    print("\n" + "=" * 70)
    print("STEP 7: LLM CONTEXT & RESPONSE")
    print("=" * 70)

    context = format_context_for_llm(matched_chunks)

    print("\nCONTEXT SENT TO LLM (first 600 chars):\n")
    print(context[:600])

    assert context.strip(), "❌ EMPTY CONTEXT SENT TO LLM"

    response = query_llm_with_context(query, context)

    print("\nLLM RESPONSE:\n")
    print(response)

    return response


# -------------------------------------------------------------------
# STEP 8: Metadata sanity check
# -------------------------------------------------------------------
def step_8_metadata():
    print("\n" + "=" * 70)
    print("STEP 8: FILE METADATA CHECK")
    print("=" * 70)

    files = get_all_files()
    stats = get_file_stats()

    print("Files tracked:", len(files))
    pretty(files)

    print("\nStats:")
    pretty(stats)


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def run_debug(filename: str, query: str):
    print("\n" + "█" * 70)
    print("RAG PIPELINE FULL DEBUG")
    print("█" * 70)

    if not step_1_file_exists(filename):
        return

    pages, file_type = step_2_read_file(filename)
    chunks = step_3_chunking(pages)
    step_4_embeddings(chunks)
    step_5_pinecone_check(file_type)

    matches = step_6_retrieval(query, file_type)
    if matches:
        step_7_llm(query, matches)

    step_8_metadata()

    print("\n✅ DEBUG COMPLETE")


if __name__ == "__main__":
    run_debug(
        filename="financial-statements-2021.xlsx",
        query="What was the revenue in 2021?",
    )
