"""
Advanced Diagnostic: Troubleshoot "No Chunks Created" Issue
Helps identify why the chunking process fails
"""

from pathlib import Path
from file_processor import read_file
from chunker import chunk_pages
import sys

RESOURCES_DIR = Path("./resources")

def diagnose_no_chunks(filename: str):
    """Deep diagnostic for chunk creation failure"""
    
    print(f"\n{'='*70}")
    print(f"DIAGNOSING: NO CHUNKS CREATED")
    print(f"{'='*70}")
    
    file_path = RESOURCES_DIR / filename
    
    # ============ CHECK 1: File Exists ============
    print(f"\n✓ CHECK 1: FILE EXISTS")
    if not file_path.exists():
        print(f"  ❌ FAIL: File not found: {file_path}")
        print(f"  💡 SOLUTION: Upload file to resources folder")
        return False
    
    print(f"  ✅ PASS: File exists")
    print(f"  📊 Size: {file_path.stat().st_size:,} bytes")
    
    # ============ CHECK 2: File Can Be Read ============
    print(f"\n✓ CHECK 2: FILE READABLE")
    try:
        pages, file_type = read_file(str(file_path))
        print(f"  ✅ PASS: File read successfully")
        print(f"  📄 Type: {file_type}")
    except Exception as e:
        print(f"  ❌ FAIL: {str(e)}")
        print(f"  💡 SOLUTION: Check file format or encoding")
        return False
    
    # ============ CHECK 3: Pages Extracted ============
    print(f"\n✓ CHECK 3: PAGES EXTRACTED")
    if not pages:
        print(f"  ❌ FAIL: No pages extracted from file")
        print(f"  💡 POSSIBLE CAUSES:")
        print(f"     - File is empty")
        print(f"     - File corrupted")
        print(f"     - Invalid file format")
        print(f"     - Special encoding issues")
        return False
    
    print(f"  ✅ PASS: Pages extracted")
    print(f"  📊 Number of pages: {len(pages)}")
    
    # ============ CHECK 4: Page Content Analysis ============
    print(f"\n✓ CHECK 4: PAGE CONTENT ANALYSIS")
    for i, page in enumerate(pages):
        page_len = len(page)
        print(f"  Page {i}: {page_len:,} characters")
        
        if page_len == 0:
            print(f"     ⚠️  WARNING: Page is empty!")
        elif page_len < 100:
            print(f"     ⚠️  WARNING: Page very small (< 100 chars)")
        
        # Show sample
        print(f"     Sample: {page[:100]}...")
    
    total_chars = sum(len(p) for p in pages)
    print(f"\n  Total content: {total_chars:,} characters")
    
    # ============ CHECK 5: Chunking Parameters ============
    print(f"\n✓ CHECK 5: CHUNKING PARAMETERS")
    chunk_size = 900
    chunk_overlap = 150
    print(f"  Chunk size: {chunk_size} characters")
    print(f"  Overlap: {chunk_overlap} characters")
    print(f"  Content size: {total_chars:,} characters")
    
    if total_chars < chunk_size:
        print(f"  ⚠️  WARNING: Content smaller than chunk size!")
        print(f"     This might result in fewer chunks than expected")
    
    # ============ CHECK 6: Attempt Chunking ============
    print(f"\n✓ CHECK 6: ATTEMPT CHUNKING")
    try:
        chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        print(f"  ✅ PASS: Chunking successful")
        print(f"  📦 Chunks created: {len(chunks)}")
        
        if len(chunks) == 0:
            print(f"  ❌ FAIL: Zero chunks created despite successful chunking!")
            print(f"  💡 SOLUTION: Check chunk_pages() function logic")
            return False
        
        # Analyze chunks
        print(f"\n  Chunk analysis:")
        chunk_sizes = [len(c) for c in chunks]
        print(f"    Min size: {min(chunk_sizes):,} chars")
        print(f"    Max size: {max(chunk_sizes):,} chars")
        print(f"    Avg size: {sum(chunk_sizes)//len(chunks):,} chars")
        
        # Show samples
        print(f"\n  Sample chunks:")
        for i, chunk in enumerate(chunks[:3]):
            print(f"    Chunk {i}: {len(chunk):,} chars")
            print(f"      {chunk[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"  ❌ FAIL: Chunking error")
        print(f"  Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_different_chunk_sizes(filename: str):
    """Test chunking with different parameters"""
    
    print(f"\n{'='*70}")
    print(f"TESTING: DIFFERENT CHUNK SIZES")
    print(f"{'='*70}")
    
    file_path = RESOURCES_DIR / filename
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    try:
        pages, file_type = read_file(str(file_path))
    except Exception as e:
        print(f"❌ Cannot read file: {str(e)}")
        return
    
    if not pages:
        print(f"❌ No pages extracted")
        return
    
    # Test different parameters
    test_configs = [
        (500, 50),    # Smaller chunks
        (900, 150),   # Default
        (1500, 200),  # Larger chunks
        (2000, 300),  # Very large chunks
    ]
    
    for chunk_size, overlap in test_configs:
        print(f"\n  Testing: chunk_size={chunk_size}, overlap={overlap}")
        try:
            chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=overlap)
            print(f"    ✅ Chunks created: {len(chunks)}")
            
            if chunks:
                sizes = [len(c) for c in chunks]
                print(f"    Size range: {min(sizes)}-{max(sizes)} chars")
            else:
                print(f"    ⚠️  ZERO chunks created!")
                
        except Exception as e:
            print(f"    ❌ Error: {str(e)}")


def suggest_fixes(filename: str):
    """Suggest fixes based on diagnostics"""
    
    print(f"\n{'='*70}")
    print(f"SUGGESTED FIXES")
    print(f"{'='*70}")
    
    file_path = RESOURCES_DIR / filename
    
    print(f"\nIf chunks aren't creating, try these solutions in order:\n")
    
    solutions = [
        {
            "step": 1,
            "problem": "File is empty or very small",
            "solution": "Upload a larger file with substantial content"
        },
        {
            "step": 2,
            "problem": "File format issue",
            "solution": f"Verify file is valid {Path(file_path).suffix} format. Try re-saving the file."
        },
        {
            "step": 3,
            "problem": "Text extraction failed",
            "solution": "Check if file contains readable text (not just images or metadata)"
        },
        {
            "step": 4,
            "problem": "Encoding issue",
            "solution": "Try converting file to UTF-8 encoding"
        },
        {
            "step": 5,
            "problem": "Chunking function issue",
            "solution": "Review chunker.py to ensure chunk_pages() function is working correctly"
        },
        {
            "step": 6,
            "problem": "Still not working",
            "solution": "Test with sample HR Policy file first to isolate the issue"
        }
    ]
    
    for sol in solutions:
        print(f"  STEP {sol['step']}: {sol['problem']}")
        print(f"    → {sol['solution']}\n")


if __name__ == "__main__":
    # Change to your file
    filename = "financial-statements-2021.xlsx"
    
    # Run full diagnostic
    success = diagnose_no_chunks(filename)
    
    if not success:
        print(f"\n❌ Diagnostic found issues. See solutions above.")
        suggest_fixes(filename)
    else:
        print(f"\n✅ Diagnostic passed! File is processing correctly.")
        print(f"\nOptional: Test different chunk sizes?")
        # Uncomment to test different sizes:
        # test_different_chunk_sizes(filename)
