import os
import asyncio
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_SERVICE_KEY:
    print("⚠️ SUPABASE_SERVICE_ROLE_KEY not found in .env! Using anon key (RLS will block usage).")
else:
    print("✅ SUPABASE_SERVICE_ROLE_KEY found.")

# Use service key to bypass RLS for diagnostics
key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
try:
    supabase = create_client(SUPABASE_URL, key)
except Exception as e:
    print(f"❌ Failed to init Supabase: {e}")
    exit(1)

def check_buckets():
    print("\n🔍 Checking Storage Buckets...")
    try:
        # Puts/Gets might fail but listing buckets usually requires service key or specific perms
        res = supabase.storage.list_buckets()
        bucket_names = [b.name for b in res]
        if 'uploads' in bucket_names:
            print("✅ 'uploads' bucket EXISTS.")
        else:
            print("❌ 'uploads' bucket MISSING!")
            print(f"   found buckets: {bucket_names}")
    except Exception as e:
        print(f"❌ Bucket check failed: {e}")

def check_schema():
    print("\n🔍 Checking Schema (Column 'blob_url')...")
    try:
        # Try to select ONLY blob_url. If column missing, this should error 400/PGRST204?
        res = supabase.table('user_files').select("blob_url").limit(1).execute()
        print("✅ 'blob_url' column found (Query success).")
    except Exception as e:
        print(f"❌ 'blob_url' column likely MISSING. Error: {e}")

def check_files():
    print("\n🔍 Checking File Records (Top 5)...")
    try:
        # We need service key or this will return [] due to RLS
        res = supabase.table('user_files').select("*").order('uploaded_at', desc=True).limit(5).execute()
        files = res.data
        if not files:
            print("⚠️ No files found (Table empty or RLS blocking).")
            return

        print(f"Found {len(files)} recent files:")
        for f in files:
            fname = f.get('filename')
            burl = f.get('blob_url')
            processed = f.get('processed')
            print(f" - {fname}:")
            print(f"   processed: {processed}")
            print(f"   blob_url: {burl if burl else '❌ NULL'}")
            
    except Exception as e:
         print(f"❌ File check failed: {e}")

if __name__ == "__main__":
    check_buckets()
    check_schema()
    check_files()
