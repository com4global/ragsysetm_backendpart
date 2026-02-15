from pypdf import PdfReader
import sys

file_path = "c:/Startup/GenAISample/RAG_HR_ASSISTANT/resources/BMW_Coverages.pdf"

print(f"Deep inspection of {file_path}")
try:
    reader = PdfReader(file_path)
    print(f"Total pages: {len(reader.pages)}")
    
    for i, page in enumerate(reader.pages):
        print(f"\n--- Page {i+1} ---")
        
        # 1. Standard Extraction
        try:
            text = page.extract_text()
            print(f"Standard: {len(text)} chars")
            if len(text) < 100: print(f"Content: {text!r}")
        except Exception as e:
            print(f"Standard Error: {e}")
            
        # 2. Annotation Strip Workaround
        try:
            if "/Annots" in page:
                print("Found /Annots - attempting removal")
                del page["/Annots"]
                text = page.extract_text()
                print(f"Workaround: {len(text)} chars")
            else:
                print("No /Annots found")
        except Exception as e:
            print(f"Workaround Error: {e}")
            
        # 3. Content Stream Inspection
        try:
            contents = page.get_contents()
            if contents:
                print(f"Content stream size: {len(contents)}")
            else:
                print("Content stream is empty/None")
        except Exception as e:
            print(f"Content Inspection Error: {e}")

except Exception as e:
    print(f"Fatal Error: {e}")
