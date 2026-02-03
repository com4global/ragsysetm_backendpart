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
    reader = PdfReader(file_path)

    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text()
        if text:
            pages.append(_page(text, f"Page {i}", file_path))

    return pages


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
