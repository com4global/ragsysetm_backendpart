"""
Test: authenticate and try to insert into user_files with the user's JWT.
This verifies whether the RLS policies allow authenticated user writes.
"""
from dotenv import load_dotenv
load_dotenv()
import os, json, base64, requests

url = os.getenv("SUPABASE_URL")
sk = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Actually the anon key
ak = os.getenv("SUPABASE_KEY")

# Find the actual anon JWT key
anon_key = None
for key in [sk, ak]:
    if not key:
        continue
    try:
        parts = key.split(".")
        if len(parts) >= 2:
            payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
            claims = json.loads(base64.b64decode(payload))
            if claims.get("role") == "anon":
                anon_key = key
                break
    except:
        pass

if not anon_key:
    print("ERROR: No anon key found!")
    exit(1)

print(f"Using anon key for test")

# Step 1: Sign in to get a real user JWT
print("\n=== Step 1: Sign in ===")
email = input("Enter your Supabase email: ").strip()
password = input("Enter your password: ").strip()

r = requests.post(
    f"{url}/auth/v1/token?grant_type=password",
    headers={"apikey": anon_key, "Content-Type": "application/json"},
    json={"email": email, "password": password}
)
if r.status_code != 200:
    print(f"Login failed: {r.status_code} {r.text[:200]}")
    exit(1)

auth_data = r.json()
user_id = auth_data["user"]["id"]
access_token = auth_data["access_token"]
print(f"Logged in as user_id: {user_id}")
print(f"Token starts with: {access_token[:20]}...")

# Step 2: Try SELECT with user JWT
print("\n=== Step 2: SELECT with user JWT ===")
r = requests.get(
    f"{url}/rest/v1/user_files?user_id=eq.{user_id}",
    headers={
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token}",
    }
)
print(f"SELECT status: {r.status_code}")
print(f"SELECT response: {r.text[:200]}")

# Step 3: Try INSERT with user JWT
print("\n=== Step 3: INSERT with user JWT ===")
from datetime import datetime
test_data = {
    "user_id": user_id,
    "filename": "__rls_test_auth__.txt",
    "file_type": "text/plain",
    "file_size": 100,
    "uploaded_at": datetime.utcnow().isoformat(),
    "chunks_created": 0,
    "processed": False
}
r = requests.post(
    f"{url}/rest/v1/user_files",
    headers={
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    },
    json=test_data
)
print(f"INSERT status: {r.status_code}")
print(f"INSERT response: {r.text[:300]}")

if r.status_code in [200, 201]:
    print("\n✅ RLS INSERT POLICY WORKS!")
    # Cleanup
    requests.delete(
        f"{url}/rest/v1/user_files?filename=eq.__rls_test_auth__.txt",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {access_token}"
        }
    )
    print("Cleanup done")
else:
    print("\n❌ RLS INSERT POLICY IS MISSING!")
    print("\nYou need to add INSERT policy. Go to Supabase Dashboard -> SQL Editor and run:")
    print("""
-- Add INSERT policy for authenticated users
CREATE POLICY "Users can insert own files"
  ON user_files FOR INSERT
  WITH CHECK (auth.uid()::text = user_id);

-- If user_id is UUID type instead of text:
-- CREATE POLICY "Users can insert own files"
--   ON user_files FOR INSERT
--   WITH CHECK (auth.uid() = user_id);
""")
