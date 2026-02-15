
import os
import sys
from dotenv import load_dotenv

# Load env from .env
load_dotenv()

print(f"Python executable: {sys.executable}")
print(f"Current working directory: {os.getcwd()}")

try:
    from embedder import embed_User_query
    print("✅ Successfully imported embedder")
except ImportError as e:
    print(f"❌ Failed to import embedder: {e}")
    sys.exit(1)

try:
    from llm import query_llm_with_context
    print("✅ Successfully imported llm")
except ImportError as e:
    print(f"❌ Failed to import llm: {e}")
    sys.exit(1)

def test_embedding():
    print("\n🧪 Testing Embedding...")
    try:
        vec = embed_User_query("hello world")
        print(f"✅ Embedding successful. Vector length: {len(vec)}")
        return True
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        return False

def test_llm():
    print("\n🧪 Testing LLM...")
    try:
        ans = query_llm_with_context("What is 2+2?", "Context: Math is cool.")
        print(f"✅ LLM successful. Answer: {ans}")
        return True
    except Exception as e:
        print(f"❌ LLM failed: {e}")
        return False

if __name__ == "__main__":
    e_ok = test_embedding()
    l_ok = test_llm()
    
    if e_ok and l_ok:
        print("\n🎉 All connectivity tests passed!")
    else:
        print("\n💥 Some tests failed.")
