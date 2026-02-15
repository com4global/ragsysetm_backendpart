
import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv()

# Add current dir to path
sys.path.append(os.getcwd())

from QueryProcessor import process_user_query

USER_ID = "95c24a5e-3388-480b-b444-3645867bb6ef"
QUERY = "What does the document say about snow?"

print(f"🚀 Starting Debug Chat for User: {USER_ID}")
print(f"❓ Query: {QUERY}")

try:
    print("\n[Step 1] Calling process_user_query...")
    result = process_user_query(QUERY, user_id=USER_ID)
    
    print("\n✅ Result received!")
    print(f"🤖 Answer: {result.get('answer')}")
    print(f"📚 Sources: {len(result.get('sources', []))}")
    for s in result.get('sources', []):
        print(f"   - {s.get('doc_name')} (Page {s.get('page')})")

except Exception as e:
    print(f"\n❌ Error during processing: {e}")
    import traceback
    traceback.print_exc()

print("\n🏁 Debug finished.")
