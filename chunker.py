# chunker.py
from typing import List

def chunk_pages(text: str, chunk_size: int = 900, chunk_overlap: int = 150) -> List[str]:
    chunks = []
    start = 0
    if not text:
        return chunks
        
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        if end >= len(text):
            break
            
        # Move start forward, but stay back by the overlap amount
        start += (chunk_size - chunk_overlap)
    return chunks


# def chunk_pages(pages: List[str], chunk_size: int = 900, chunk_overlap: int = 150) -> List[str]:
#     chunks: List[str] = []
#     print(type(pages))
    
#     full_text = " ".join(pages)
#     text_length = len(full_text)
    
#     if text_length == 0:
#         return chunks
    
#     start = 0
#     while start < text_length:
#         # Calculate end position
#         end = min(start + chunk_size, text_length)

#         # Extract chunk
#         chunk = full_text[start:end].strip()
#         if chunk:  # Only add non-empty chunks
#             chunks.append(chunk)

#         # If this was the last chunk (we reached the end), break
#         if end >= text_length:
#             break
        
#         # Calculate next starting position
#         start = end - chunk_overlap
    
#     return chunks
# def chunk_pages(pages: List[dict], chunk_size=900, overlap=150):
#     chunks = []

#     for page in pages:
#         text = page["text"]
#         start = 0
#         while start < len(text):
#             chunk_text = text[start:start+chunk_size]
#             chunks.append({
#                 "text": chunk_text,
#                 "page": page["page"],
#                 "doc_name": page["doc_name"],
#                 ".
#             })
#             start += chunk_size - overlap

#     return chunks
