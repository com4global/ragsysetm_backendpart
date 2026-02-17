"""
File Processor Module (STRICT STRUCTURED OUTPUT)
Every reader returns:
{
  text: str,
  page: str,
  doc_name: str,
  path: str
}
"""

from pathlib import Path
from typing import List, Tuple
import os
import csv
import xml.etree.ElementTree as ET

# PDF
from pypdf import PdfReader

# Excel
import openpyxl

# Word
from docx import Document


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def _page(text: str, page: str, file_path: str):
    return {
        "text": text.strip(),
        "page": page,
        "doc_name": os.path.basename(file_path),
        "path": file_path,
    }


# -------------------------------------------------
# PDF
# -------------------------------------------------
def read_pdf_file(file_path: str) -> List[dict]:
    pages = []
    
    # Method 1: Try pypdf (fast, standard)
    try:
        reader = PdfReader(file_path, strict=False)
        for i, page in enumerate(reader.pages, start=1):
            text = ""
            try:
                text = page.extract_text()
            except Exception:
                # Retry workaround: remove annotations
                try:
                    if "/Annots" in page:
                        del page["/Annots"]
                    text = page.extract_text()
                except Exception:
                    pass
            
            if text and len(text.strip()) > 10:  # Valid text found
                pages.append(_page(text, f"Page {i}", file_path))
    except Exception as e:
        print(f"pypdf failed: {e}")

    # Method 2: Fallback to pdfplumber (slower, robust) if pypdf failed or yielded no pages
    if not pages:
        print(f"pypdf yielded no text for {file_path}, switching to pdfplumber...")
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if text and text.strip():
                        pages.append(_page(text, f"Page {i}", file_path))
        except ImportError:
            print("pdfplumber not installed. Cannot use fallback.")
        except Exception as e:
            print(f"pdfplumber failed: {e}")

    # Post-process: detect chapters/sections for each page
    _detect_chapters(pages)
    
    return pages


def _detect_chapters(pages: List[dict]):
    """
    Scan pages for chapter/section headings and add 'chapter' metadata.
    Supports patterns like:
      - Chapter 1: Introduction
      - CHAPTER 1 – OVERVIEW  
      - Section 2.1: Data Processing
      - 1. Introduction
      - 1.1 Getting Started
      - INTRODUCTION (all-caps lines at start of page)
      - Part I: Foundations
      - Unit 3: Neural Networks
    """
    import re
    
    chapter_patterns = [
        # Chapter N: Title or Chapter N — Title  
        re.compile(r'^(?:chapter|ch\.?)\s*(\d+)\s*[:\-–—.]\s*(.+)', re.IGNORECASE | re.MULTILINE),
        # Part N: Title
        re.compile(r'^(?:part|unit|module|lesson)\s*(\d+|[IVXLC]+)\s*[:\-–—.]\s*(.+)', re.IGNORECASE | re.MULTILINE),
        # Section N.N: Title
        re.compile(r'^(?:section)\s*([\d.]+)\s*[:\-–—.]\s*(.+)', re.IGNORECASE | re.MULTILINE),
        # Numbered heading: 1. Introduction or 1.1 Getting Started
        re.compile(r'^(\d+(?:\.\d+)?)\s*[.):\-–—]\s+([A-Z][A-Za-z\s]{3,50})$', re.MULTILINE),
    ]
    
    current_chapter = "Introduction"
    
    for page_obj in pages:
        text = page_obj["text"]
        # Check first 500 chars for heading patterns
        header_text = text[:500]
        
        found = False
        for pattern in chapter_patterns:
            match = pattern.search(header_text)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    num, title = groups[0], groups[1].strip()
                    current_chapter = f"{num}. {title}" if title else f"Section {num}"
                else:
                    current_chapter = groups[0].strip()
                found = True
                break
        
        # Fallback: check for ALL-CAPS title at the very start of the page
        if not found:
            first_line = text.strip().split('\n')[0].strip()
            if (first_line.isupper() and 
                5 < len(first_line) < 80 and 
                not first_line.startswith('PAGE') and
                not first_line.startswith('TABLE')):
                current_chapter = first_line.title()
        
        page_obj["chapter"] = current_chapter


# -------------------------------------------------
# Excel
# -------------------------------------------------
def read_excel_file(file_path: str) -> List[dict]:
    pages = []
    wb = openpyxl.load_workbook(file_path, data_only=True)

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            row_text = " | ".join(str(cell) for cell in row if cell is not None)
            if row_text.strip():
                pages.append(
                    _page(
                        row_text,
                        f"{sheet_name} - Row {row_idx}",
                        file_path,
                    )
                )
    return pages


# -------------------------------------------------
# CSV
# -------------------------------------------------
def read_csv_file(file_path: str) -> List[dict]:
    pages = []
    with open(file_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, start=1):
            row_text = " | ".join(row)
            if row_text.strip():
                pages.append(_page(row_text, f"Row {i}", file_path))
    return pages


# -------------------------------------------------
# TXT
# -------------------------------------------------
def read_txt_file(file_path: str) -> List[dict]:
    pages = []
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    chunk_size = 4000
    for i in range(0, len(content), chunk_size):
        pages.append(
            _page(
                content[i : i + chunk_size],
                f"Chunk {i // chunk_size + 1}",
                file_path,
            )
        )
    return pages


# -------------------------------------------------
# Word
# -------------------------------------------------
def read_word_file(file_path: str) -> List[dict]:
    pages = []
    doc = Document(file_path)

    for i, para in enumerate(doc.paragraphs, start=1):
        if para.text.strip():
            pages.append(_page(para.text, f"Paragraph {i}", file_path))
    return pages


# -------------------------------------------------
# XML
# -------------------------------------------------
def read_xml_file(file_path: str) -> List[dict]:
    pages = []
    tree = ET.parse(file_path)
    root = tree.getroot()

    def walk(elem, depth=0):
        if elem.text and elem.text.strip():
            pages.append(
                _page(elem.text, f"XML depth {depth}", file_path)
            )
        for child in elem:
            walk(child, depth + 1)

    walk(root)
    return pages


# -------------------------------------------------
# Routing
# -------------------------------------------------
def get_file_type(file_path: str) -> str:
    return Path(file_path).suffix.lower().lstrip(".")


def read_file(file_path: str) -> Tuple[List[dict], str]:
    file_type = get_file_type(file_path)

    readers = {
        "pdf": read_pdf_file,
        "xlsx": read_excel_file,
        "xls": read_excel_file,
        "csv": read_csv_file,
        "txt": read_txt_file,
        "docx": read_word_file,
        "doc": read_word_file,
        "xml": read_xml_file,
    }

    if file_type not in readers:
        raise ValueError(f"Unsupported file type: {file_type}")

    return readers[file_type](file_path), file_type


def get_supported_formats():
    return [".pdf", ".xlsx", ".xls", ".csv", ".txt", ".docx", ".doc", ".xml"]
