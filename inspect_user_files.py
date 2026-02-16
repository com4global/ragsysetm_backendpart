
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not url or not key:
    print("❌ Missing Supabase credentials")
    exit(1)

supabase = create_client(url, key)

print("--- Checking user_files ---")
try:
    response = supabase.table('user_files').select("*").execute()
    files = response.data
    print(f"Total Files: {len(files)}")
    
    # Check for duplicates
    seen = {}
    duplicates = []
    for f in files:
        key = (f.get('user_id'), f.get('filename'))
        if key in seen:
            duplicates.append(key)
        seen[key] = True
        
    if duplicates:
        print(f"❌ Found {len(duplicates)} duplicates (user_id, filename):")
        for d in duplicates:
            print(f"  - {d}")
    else:
        print("✅ No duplicates found based on (user_id, filename).")
        
    # Check if we can upsert
    print("\n--- Testing Upsert Constraint ---")
    try:
        # Try to upsert a dummy record to see if it fails on constraint
        # We won't actually insert if we can avoiding it, or we delete it after.
        # Actually, let's just print the error if we try to add a duplicate of an existing file.
        if files:
            f = files[0]
            print(f"Attempting to upsert duplicate for: {f.get('filename')}")
            # This should succeed and UPDATE if constraint exists.
            # It will INSERT A NEW ROW if constraint is missing (and we'll see count + 1)
            
            initial_count = len(files)
            
            # Upsert
            supabase.table('user_files').upsert({
                "user_id": f['user_id'],
                "filename": f['filename'],
                "file_type": f['file_type'],
                "file_size": f['file_size'],
                "blob_url": f.get('blob_url')
            }, on_conflict='user_id, filename').execute()
            
            # Check count again
            new_count = supabase.table('user_files').select("*", count='exact').execute().count
            
            if new_count == initial_count:
                print("✅ Upsert worked (Count unchanged). Constraint likely exists.")
            else:
                print(f"❌ Upsert INSERTED a new row (Count: {initial_count} -> {new_count}). CONSTRAINT MISSING!")
                
    except Exception as e:
        print(f"⚠️ Upsert failed with error: {e}")

except Exception as e:
    print(f"Error: {e}")
