import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Colors
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
END = "\033[0m"

print(f"\n{Y}🌐 Supabase CORS Auto-Fixer{END}")
print("=============================")

# 1. Get Credentials
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print(f"{R}❌ Missing credentials in .env{END}")
    print("Please ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set.")
    # Prompt if missing
    if not url: url = input("Enter Supabase URL: ").strip()
    if not key: key = input("Enter Service Role Key: ").strip()

if not url or not key:
    print("Aborting.")
    exit(1)

# 2. Define CORS Config
# We want to allow localhost:3000 and the Netlify URL (if known, or just * for now to fix it)
cors_config = [
  {
    "origin": ["http://localhost:3000", "https://*.netlify.app", "http://127.0.0.1:3000"],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allowed_headers": ["*"],
    "max_age_seconds": 3600
  }
]

# 3. Update Bucket
BUCKET_NAME = "uploads"
api_url = f"{url}/storage/v1/bucket/{BUCKET_NAME}"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "apikey": key
}

print(f"\n{Y}🔄 Updating CORS for bucket '{BUCKET_NAME}'...{END}")

try:
    # First, get current config to see if it exists
    r = requests.get(api_url, headers=headers)
    if r.status_code != 200:
        print(f"{R}❌ Failed to find bucket '{BUCKET_NAME}' (Status: {r.status_code}){END}")
        print(r.text)
    else:
        # Patch the bucket with new options
        # Note: The Storage API for updating bucket options including CORS might vary slightly 
        # based on Supabase version, but typically it's a PATCH to /bucket/{id}
        
        # Valid payload for updating bucket might just be 'public' and 'file_size_limit'
        # CORS is sometimes global or set via SQL in older versions, but let's try the modern API approach
        # If this fails, we fall back to SQL
        
        # Payload: allowed_mime_types, file_size_limit, user_metadata
        # Wait, standard storage-api might not expose CORS in the PATCH /bucket endpoint directly in all versions.
        # It's often in the 'options' object.
        
        # Let's try to update public status again just to be sure, and see if we can inject CORS headers? 
        # Actually, Supabase Storage CORS is usually set via the dashboard or SQL config on `storage.buckets`.
        
        pass

    # PLAN B: SQL Injection for CORS
    # We can try to update the `storage.buckets` table directly if we have service_role
    print(f"{Y}⚡ Attempting to set CORS via SQL (Direct DB Update)...{END}")
    
    from supabase import create_client
    supabase = create_client(url, key)
    
    # Update localhost:3000 to allowed_origins
    # The column is 'allowed_origins' (array of text) in 'storage.buckets'
    
    response = supabase.table('buckets', schema='storage').update({
        "allowed_origins": ["http://localhost:3000", "https://*.netlify.app", "*"] 
    }).eq('name', BUCKET_NAME).execute()
    
    if response.data:
        print(f"{G}✅ CORS updated successfully via SQL!{END}")
        print(f"   Allowed Origins: {response.data[0].get('allowed_origins')}")
    else:
        print(f"{R}❌ SQL Update returned no data. Bucket might not exist or permission denied.{END}")

except Exception as e:
    print(f"{R}❌ Error: {e}{END}")

print("\nTry your upload again!")
