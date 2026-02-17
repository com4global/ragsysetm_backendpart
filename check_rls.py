"""Check Supabase RLS and service role key validity"""
from dotenv import load_dotenv
load_dotenv()
import os, requests, json, base64

url = os.getenv("SUPABASE_URL")
sk = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ak = os.getenv("SUPABASE_KEY")

print("=== Key Analysis ===")

# Decode service role key JWT
try:
    parts = sk.split(".")
    if len(parts) >= 2:
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.b64decode(payload)
        claims = json.loads(decoded)
        role = claims.get("role", "NOT FOUND")
        print(f"Service key role: {role}")
        print(f"Service key issuer: {claims.get('iss', 'N/A')}")
        if role != "service_role":
            print(f"  WARNING: Expected 'service_role' but got '{role}'!")
    else:
        print("Service key is NOT JWT format!")
except Exception as e:
    print(f"Service key decode error: {e}")

# Decode anon key
try:
    parts = ak.split(".")
    if len(parts) >= 2:
        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = base64.b64decode(payload)
        claims = json.loads(decoded)
        print(f"Anon key role: {claims.get('role', 'NOT FOUND')}")
    else:
        print(f"Anon key is NOT JWT format (value starts with: {ak[:20]})")
except Exception as e:
    print(f"Anon key decode error: {e}")

print()
print("=== Admin API Test (service role only) ===")
r = requests.get(
    f"{url}/auth/v1/admin/users?per_page=1",
    headers={"apikey": sk, "Authorization": f"Bearer {sk}"}
)
print(f"Admin API: {r.status_code} (200=valid service_role key)")

print()
print("=== Direct REST INSERT Test ===")
test_data = {
    "user_id": "c3ed23c5-0a1a-4b08-b62c-e6a920cff35b",
    "filename": "__rls_test__.txt",
    "file_type": "text/plain",
    "file_size": 0,
    "chunks_created": 0,
    "processed": False
}
r = requests.post(
    f"{url}/rest/v1/user_files",
    headers={
        "apikey": sk,
        "Authorization": f"Bearer {sk}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    },
    json=test_data
)
print(f"INSERT status: {r.status_code}")
print(f"INSERT response: {r.text[:300]}")

if r.status_code in [200, 201]:
    # Cleanup
    requests.delete(
        f"{url}/rest/v1/user_files?filename=eq.__rls_test__.txt",
        headers={"apikey": sk, "Authorization": f"Bearer {sk}"}
    )
    print("Cleanup done")
