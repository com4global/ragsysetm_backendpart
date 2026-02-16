
import sys
import unittest
from unittest.mock import MagicMock

# Mock embedder module
mock_embedder = MagicMock()
mock_embedder.embed_chunks.return_value = [] 
sys.modules['embedder'] = mock_embedder

# Mock vectorstore module
mock_vectorstore = MagicMock()
sys.modules['vectorstore'] = mock_vectorstore

# Mock file_processor module
mock_file_processor = MagicMock()
# Mock read_file to return empty list (simulating empty file)
mock_file_processor.read_file.return_value = ([], "txt") 
mock_file_processor.get_file_type.return_value = "txt"
sys.modules['file_processor'] = mock_file_processor

# Mock chunker module - though not used if pages empty
mock_chunker = MagicMock()
sys.modules['chunker'] = mock_chunker

# Now import dataprocessor
# It will use the mocks
import dataprocessor
import os

class TestEmptyFileProcessing(unittest.TestCase):
    def test_process_empty_file(self):
        # Create a dummy file path (doesn't need to exist if we mocked read_file, 
        # but process_file checks existence)
        with open("test_empty_mock.txt", "w") as f:
            f.write("")
            
        try:
            # Call process_file
            print("Running process_file with mocked modules...")
            result = dataprocessor.process_file("test_empty_mock.txt", user_id="test")
            
            print(f"Result: {result}")
            
            # Assertions
            self.assertEqual(result['chunks_created'], 0)
            
            # Verify store_in_pinecone was NOT called
            mock_vectorstore.store_in_pinecone.assert_not_called()
            print("✅ store_in_pinecone was properly skipped!")
            
        finally:
            if os.path.exists("test_empty_mock.txt"):
                os.remove("test_empty_mock.txt")

if __name__ == "__main__":
    unittest.main()
