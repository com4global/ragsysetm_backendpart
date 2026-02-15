from pypdf import PdfReader, PdfWriter
import io

file_path = "c:/Startup/GenAISample/RAG_HR_ASSISTANT/resources/BMW_Coverages.pdf"

def test_extraction():
    try:
        reader = PdfReader(file_path)
        print(f"Processing {len(reader.pages)} pages...")
        
        for i, page in enumerate(reader.pages):
            try:
                # Standard extraction
                text = page.extract_text()
                print(f"Page {i+1}: Success (Standard) - {len(text)} chars")
            except Exception as e:
                print(f"Page {i+1}: Failed (Standard) - {e}")
                
                # Attempt workaround: clear annotations
                try:
                    if '/Annots' in page:
                        del page['/Annots']
                    text = page.extract_text()
                    print(f"Page {i+1}: Success (Workaround) - {len(text)} chars")
                except Exception as e2:
                    print(f"Page {i+1}: Failed (Workaround) - {e2}")

    except Exception as e:
        print(f"Major error: {e}")

test_extraction()
