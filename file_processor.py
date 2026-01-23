"""
File Processor Module
Handles reading and processing multiple file formats
Supports: PDF, Excel, CSV, TXT, Word, XML
"""

from pathlib import Path
from typing import List, Tuple
import os

# PDF
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# Excel
try:
    import openpyxl
except ImportError:
    openpyxl = None

# CSV
import csv

# Word
try:
    from docx import Document
except ImportError:
    Document = None

# XML
import xml.etree.ElementTree as ET


def read_pdf_file(file_path: str) -> List[str]:
    """Read PDF file and extract text"""
    if not PdfReader:
        raise ImportError("pypdf is required for PDF processing")
    
    pages = []
    try:
        pdf_reader = PdfReader(file_path)
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")
    
    return pages


def read_excel_file(file_path: str) -> List[str]:
    """Read Excel file and extract text"""
    if not openpyxl:
        raise ImportError("openpyxl is required for Excel processing")
    
    pages = []
    try:
        workbook = openpyxl.load_workbook(file_path)
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            sheet_text = f"Sheet: {sheet_name}\n"
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join(str(cell) if cell is not None else "" for cell in row)
                sheet_text += row_text + "\n"
            if sheet_text.strip():
                pages.append(sheet_text)
    except Exception as e:
        raise Exception(f"Error reading Excel: {str(e)}")
    
    return pages


def read_csv_file(file_path: str) -> List[str]:
    """Read CSV file and extract text"""
    pages = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            csv_text = ""
            for row in csv_reader:
                csv_text += " | ".join(row) + "\n"
            if csv_text.strip():
                pages.append(csv_text)
    except Exception as e:
        raise Exception(f"Error reading CSV: {str(e)}")
    
    return pages


def read_txt_file(file_path: str) -> List[str]:
    """Read TXT file and extract text"""
    pages = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if content.strip():
                # Split into pages by size (for consistency)
                page_size = 4000  # characters per page
                for i in range(0, len(content), page_size):
                    pages.append(content[i:i+page_size])
    except Exception as e:
        raise Exception(f"Error reading TXT: {str(e)}")
    
    return pages


def read_word_file(file_path: str) -> List[str]:
    """Read Word (.docx) file and extract text"""
    if not Document:
        raise ImportError("python-docx is required for Word processing")
    
    pages = []
    try:
        doc = Document(file_path)
        doc_text = ""
        for para in doc.paragraphs:
            if para.text.strip():
                doc_text += para.text + "\n"
        if doc_text.strip():
            pages.append(doc_text)
    except Exception as e:
        raise Exception(f"Error reading Word: {str(e)}")
    
    return pages


def read_xml_file(file_path: str) -> List[str]:
    """Read XML file and extract text"""
    pages = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        def extract_text_from_element(elem, depth=0):
            text = ""
            if elem.text and elem.text.strip():
                text += "  " * depth + elem.text.strip() + "\n"
            for child in elem:
                text += extract_text_from_element(child, depth + 1)
            return text
        
        xml_text = extract_text_from_element(root)
        if xml_text.strip():
            pages.append(xml_text)
    except Exception as e:
        raise Exception(f"Error reading XML: {str(e)}")
    
    return pages


def get_file_type(file_path: str) -> str:
    """Determine file type from extension"""
    ext = Path(file_path).suffix.lower()
    
    file_types = {
        '.pdf': 'pdf',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.csv': 'csv',
        '.txt': 'txt',
        '.docx': 'word',
        '.doc': 'word',
        '.xml': 'xml'
    }
    
    return file_types.get(ext, 'unknown')


def read_file(file_path: str) -> Tuple[List[str], str]:
    """
    Read any supported file type and return extracted text
    Returns: (list of text pages, file type)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_type = get_file_type(file_path)
    
    readers = {
        'pdf': read_pdf_file,
        'excel': read_excel_file,
        'csv': read_csv_file,
        'txt': read_txt_file,
        'word': read_word_file,
        'xml': read_xml_file
    }
    
    if file_type not in readers:
        raise ValueError(f"Unsupported file type: {file_type}")
    
    pages = readers[file_type](file_path)
    return pages, file_type


def get_supported_formats() -> List[str]:
    """Return list of supported file formats"""
    return ['.pdf', '.xlsx', '.xls', '.csv', '.txt', '.docx', '.doc', '.xml']
