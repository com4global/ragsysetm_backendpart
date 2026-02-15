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


