"""
Diagnostic script to test Supabase connectivity and data retrieval.
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

# Write to file for clean reading
out = open("debug_results.txt", "w", encoding="utf-8")

def log(msg):
    print(msg)
    out.write(msg + "\n")
    out.flush()

log("=" * 60)
log("DIAGNOSTIC: Supabase Connection & Data Test")
log("=" * 60)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
log(f"SUPABASE_URL: {SUPABASE_URL}")
log(f"SUPABASE_KEY: {SUPABASE_KEY[:20]}..." if SUPABASE_KEY else "SUPABASE_KEY: NOT SET")

try:
    from supabase import create_client
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    log("Supabase client: OK")
except Exception as e:
    log(f"Supabase client ERROR: {e}")
    out.close()
    sys.exit(1)

# Test user_files table
log("\n--- user_files table ---")
try:
    response = supabase.table('user_files').select("*").limit(10).execute()
    log(f"Records found: {len(response.data)}")
    for f in response.data:
        log(f"  user_id={f.get('user_id','?')}, filename={f.get('filename','?')}, processed={f.get('processed','?')}")
    if not response.data:
        log("TABLE IS EMPTY - no files recorded")
except Exception as e:
    log(f"ERROR: {type(e).__name__}: {e}")

# Test profiles table
log("\n--- profiles table ---")
try:
    response = supabase.table('profiles').select("*").limit(10).execute()
    log(f"Profiles found: {len(response.data)}")
    for p in response.data:
        log(f"  id={p.get('id','?')}, email={p.get('email','?')}")
    if not response.data:
        log("NO PROFILES FOUND")
except Exception as e:
    log(f"ERROR: {type(e).__name__}: {e}")

# Test INSERT into user_files
log("\n--- INSERT test ---")
try:
    test_data = {
        "user_id": "test-user-000",
        "filename": "test_diagnostic.pdf",
        "file_type": "application/pdf",
        "file_size": 1024,
        "blob_url": None,
        "uploaded_at": "2025-01-01T00:00:00",
        "chunks_created": 0,
        "processed": False
    }
    response = supabase.table('user_files').upsert(test_data, on_conflict='user_id, filename').execute()
    log(f"Insert result: {response.data}")
    # Clean up
    supabase.table('user_files').delete().eq('user_id', 'test-user-000').execute()
    log("Cleanup OK")
except Exception as e:
    log(f"INSERT ERROR: {type(e).__name__}: {e}")

log("\n" + "=" * 60)
log("DONE")
out.close()
