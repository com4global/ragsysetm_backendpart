import os
from pypdf import PdfReader
from typing import List, Dict

def read_pdf(pdf_path: str) -> List[Dict]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file {pdf_path} does not exist.")

    reader = PdfReader(pdf_path)
    pages = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text and text.strip():
            pages.append({
                "text": text,
                "page": page_num,
                "doc_name": os.path.basename(pdf_path),
                "path": pdf_path
            })

    return pages
