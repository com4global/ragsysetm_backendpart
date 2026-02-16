
import os
from dataprocessor import process_file
from pathlib import Path

def test_processing():
    resources_dir = Path("./resources")
    for file_path in resources_dir.iterdir():
        if file_path.is_file():
            print(f"Testing {file_path.name}...")
            try:
                # Use a dummy user_id for testing
                process_file(str(file_path), user_id="test_user")
                print(f"✅ Successfully processed {file_path.name}")
            except Exception as e:
                print(f"❌ Failed to process {file_path.name}: {e}")

if __name__ == "__main__":
    test_processing()
