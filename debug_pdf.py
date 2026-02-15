from file_processor import read_pdf_file
import os

pdf_path = "resources/BMW_Coverages.pdf"
if os.path.exists(pdf_path):
    print(f"Testing PDF: {pdf_path}")
    try:
        pages = read_pdf_file(pdf_path)
        print(f"Extracted {len(pages)} pages")
        for i, p in enumerate(pages):
            print(f"Page {i+1} length: {len(p['text'])}")
            print(f"Sample: {p['text'][:100]}...")
    except Exception as e:
        print(f"Error reading PDF: {e}")
else:
    print(f"File not found: {pdf_path}")
