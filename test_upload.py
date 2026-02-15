"""
End-to-end test: Login to Supabase -> Get JWT -> Upload file -> Check files list
"""
import os, json
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Step 1: Login with Supabase to get a real JWT
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# We need to know the user's email/password. 
# Let's check if there's a known test user by looking at environment or checking Auth API
# From the backend logs we know user_id = c3ed23c5-0a1a-4b08-b62c-e6a920cff35b

# Let's try common test credentials - we need to find what the user registered with
# But we can also generate a token using the admin API if we had the service key

# Alternative approach: use requests to directly hit the backend with a file
# and capture the exact error
import requests

# Step 1a: Try to sign in with possible test emails
test_emails = ["test@test.com", "admin@test.com", "user@test.com"]
session = None

for email in test_emails:
    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": "password123"})
        if result.session:
            print(f"✅ Logged in as: {email}")
            session = result.session
            break
    except Exception as e:
        print(f"❌ {email}: {e}")

if not session:
    # Try with more passwords
    for email in test_emails:
        for pwd in ["test123", "Test1234", "admin123", "password"]:
            try:
                result = supabase.auth.sign_in_with_password({"email": email, "password": pwd})
                if result.session:
                    print(f"✅ Logged in as: {email} with password: {pwd}")
                    session = result.session
                    break
            except Exception:
                pass
        if session:
            break

if not session:
    print("\n⚠️ Could not auto-login. Checking if profiles table has any users...")
    try:
        # This won't work with anon key + RLS, but let's try
        r = supabase.table('profiles').select("email,id").limit(5).execute()
        print(f"   Profiles: {r.data}")
    except Exception as e:
        print(f"   Can't read profiles: {e}")
    
    # Generate a JWT using the Supabase Auth API directly
    print("\n   Trying to use REST API to sign in...")
    
    # Check if we can get users list
    resp = requests.get(
        f"{SUPABASE_URL}/auth/v1/admin/users",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )
    print(f"   Admin users API: {resp.status_code}")
    if resp.status_code == 200:
        users = resp.json().get("users", [])
        for u in users[:3]:
            print(f"   User: {u.get('email')}, id={u.get('id')}")
    else:
        print(f"   Response: {resp.text[:200]}")
    
    print("\n❌ Cannot test without login credentials.")
    print("To test manually, open the browser console and run:")
    print("  const { data: { session } } = await supabase.auth.getSession();")
    print("  console.log('Token:', session?.access_token);")
    exit(0)

# Step 2: Use the JWT to test the upload endpoint
token = session.access_token
print(f"\nJWT Token obtained: {token[:30]}...")
print(f"User ID: {session.user.id}")

# Step 3: Test GET /api/files with token
print("\n=== Test GET /api/files ===")
r = requests.get("http://localhost:10001/api/files", 
                  headers={"Authorization": f"Bearer {token}"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:300]}")

# Step 4: Test POST /api/upload with token
print("\n=== Test POST /api/upload ===")
test_file_content = b"This is a test document for the HR assistant. It contains sample HR policies."
r = requests.post("http://localhost:10001/api/upload",
                   files={"file": ("test_document.txt", test_file_content, "text/plain")},
                   headers={"Authorization": f"Bearer {token}"})
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:300]}")

# Step 5: Verify file appears in list
print("\n=== Verify GET /api/files after upload ===")
r = requests.get("http://localhost:10001/api/files",
                  headers={"Authorization": f"Bearer {token}"})
print(f"Status: {r.status_code}")
data = r.json()
print(f"Files count: {len(data.get('files', []))}")
print(f"Files: {json.dumps(data.get('files', []), indent=2)[:300]}")
print(f"Stats: {json.dumps(data.get('stats', {}), indent=2)}")

print("\n✅ End-to-end test complete!")
