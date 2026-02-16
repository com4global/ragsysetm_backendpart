
import os
from dataprocessor import process_file

# Create an empty file
with open("test_empty.txt", "w") as f:
    f.write("")

print("Created test_empty.txt")

try:
    print("Processing test_empty.txt...")
    result = process_file("test_empty.txt", user_id="test_user")
    print(f"✅ Result: {result}")
except Exception as e:
    print(f"❌ Failed: {e}")
finally:
    if os.path.exists("test_empty.txt"):
        os.remove("test_empty.txt")
        print("Cleaned up test_empty.txt")
