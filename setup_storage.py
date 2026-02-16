import os
import requests
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Colors for clearer output
G = "\033[92m" # Green
R = "\033[91m" # Red
Y = "\033[93m" # Yellow
END = "\033[0m"

print(f"\n{Y}🛠️  Supabase Storage & Database Auto-Fixer{END}")
print("=========================================")

# 1. Get Credentials
url = os.getenv("SUPABASE_URL")
if not url:
    url = input(f"Enter your Supabase URL (e.g., https://xyz.supabase.co): ").strip()

key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not key:
    print(f"\n{R}⚠️  SUPABASE_SERVICE_ROLE_KEY not found in .env{END}")
    print("You MUST provide the 'service_role' key (NOT the anon key) to manage storage buckets.")
    print("Find it here: Dashboard -> Project Settings -> API -> Service Role Secret")
    key = input(f"Enter Service Role Key: ").strip()

if not url or not key:
    print(f"{R}❌ Missing credentials. Aborting.{END}")
    exit(1)

try:
    supabase = create_client(url, key)
    print(f"\n{G}✅ Client initialized.{END}")
except Exception as e:
    print(f"{R}❌ Invalid credentials: {e}{END}")
    exit(1)

# 2. Check/Create Bucket
BUCKET_NAME = "uploads"
print(f"\n{Y}📦 Checking Storage Bucket: '{BUCKET_NAME}'...{END}")

try:
    buckets = supabase.storage.list_buckets()
    bucket_names = [b.name for b in buckets]
    
    if BUCKET_NAME in bucket_names:
        print(f"{G}✅ Bucket '{BUCKET_NAME}' exists.{END}")
        # Check if public
        bucket = next((b for b in buckets if b.name == BUCKET_NAME), None)
        if bucket and bucket.public:
             print(f"{G}✅ Bucket is Public.{END}")
        else:
             print(f"{Y}🔄 Updating bucket to Public...{END}")
             try:
                 supabase.storage.update_bucket(BUCKET_NAME, {"public": True})
                 print(f"{G}✅ Bucket updated to Public.{END}")
             except Exception as e:
                 print(f"{R}❌ Failed to update bucket: {e}{END}")

    else:
        print(f"{Y}⚠️ Bucket '{BUCKET_NAME}' MISSING.{END}")
        print(f"{Y}🔨 Creating public bucket '{BUCKET_NAME}'...{END}")
        try:
            supabase.storage.create_bucket(BUCKET_NAME, options={"public": True})
            print(f"{G}✅ Bucket created successfully.{END}")
        except Exception as e:
            print(f"{R}❌ Failed to create bucket: {e}{END}")
            # If creating fails, subsequent CORS fix might fail too, but we continue to try.

except Exception as e:
    print(f"{R}❌ Failed to list/manage buckets. Check your Service Key permissions.{END}")
    print(f"Error: {e}")

# 3. Fix CORS (Crucial for Localhost 'Failed to Fetch')
print(f"\n{Y}🌐 Configuring CORS for '{BUCKET_NAME}'...{END}")
try:
    # Use valid Supabase Client method to access 'storage' schema
    # allowed_origins must include localhost:3000 and the netlify app
    # We update the 'buckets' table in the 'storage' schema directly
    
    # Note: .schema() is available in newer supabase-py versions. 
    # If this fails, we fall back to printing SQL.
    
    res = supabase.schema('storage').table('buckets').update({
        "allowed_origins": ["http://localhost:3000", "https://*.netlify.app", "*"]
    }).eq('name', BUCKET_NAME).execute()
    
    if res.data:
         print(f"{G}✅ CORS updated. Allowed Origins: {res.data[0].get('allowed_origins')}{END}")
    else:
         print(f"{R}❌ CORS update returned no data (Bucket might not exist?){END}")

except Exception as e:
    print(f"{R}❌ CORS Auto-Fix failed: {e}{END}")
    print(f"{Y}👉 Manual Fix: Go to Storage -> Buckets -> {BUCKET_NAME} -> Settings -> CORS Origins{END}")
    print(f"   Add: http://localhost:3000")


# 4. Check/Add Database Column
print(f"\n{Y}🗄️  Checking Database Schema (table: user_files)...{END}")

try:
    # Diagnostic SELECT
    res = supabase.table('user_files').select("blob_url").limit(1).execute()
    print(f"{G}✅ Column 'blob_url' exists.{END}")
except Exception as e:
    print(f"{Y}⚠️ Column 'blob_url' likely MISSING.{END}")
    print(f"{Y}🔨 Attempting to add column via SQL...{END}")
    print(f"{R}❌ Cannot Auto-Create Column via Client (Requires SQL Editor).{END}")
    print(f"{Y}👉 ACTION REQUIRED: Go to Supabase > SQL Editor and run:{END}")
    print(f"\n{G}ALTER TABLE user_files ADD COLUMN IF NOT EXISTS blob_url TEXT;{END}\n")

print(f"\n{G}✨ Setup Check Complete. Try uploading again!{END}")
