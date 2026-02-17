"""
Fix RLS policies on user_files table.
Run this script once to add INSERT/UPDATE/DELETE policies for authenticated users.

The SUPABASE_SERVICE_ROLE_KEY in .env is actually the anon key, so we need
to use the Supabase Management API or run this SQL via the Supabase Dashboard.
"""
from dotenv import load_dotenv
load_dotenv()
import os, requests, json, base64

url = os.getenv("SUPABASE_URL")
sk = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ak = os.getenv("SUPABASE_KEY")

print("=" * 60)
print("SUPABASE KEY CONFIGURATION CHECK")
print("=" * 60)

# Check which key is the real anon key
for name, key in [("SUPABASE_SERVICE_ROLE_KEY", sk), ("SUPABASE_KEY", ak)]:
    try:
        parts = key.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            claims = json.loads(decoded)
            role = claims.get("role", "?")
            print(f"  {name}: role={role}")
        else:
            print(f"  {name}: NOT a JWT (starts with {key[:15]}...)")
    except Exception as e:
        print(f"  {name}: decode error ({e})")

print()
print("=" * 60)
print("FIX: You need to add RLS policies to the user_files table.")
print("=" * 60)
print()
print("Go to your Supabase Dashboard -> SQL Editor, and run this SQL:")
print()

sql = """
-- ============================================
-- Add RLS policies for user_files table
-- ============================================

-- Make sure RLS is enabled (it probably already is)
ALTER TABLE user_files ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to SELECT their own files
CREATE POLICY IF NOT EXISTS "Users can view own files"
  ON user_files FOR SELECT
  USING (auth.uid()::text = user_id);

-- Allow authenticated users to INSERT their own files
CREATE POLICY IF NOT EXISTS "Users can insert own files"
  ON user_files FOR INSERT
  WITH CHECK (auth.uid()::text = user_id);

-- Allow authenticated users to UPDATE their own files
CREATE POLICY IF NOT EXISTS "Users can update own files"
  ON user_files FOR UPDATE
  USING (auth.uid()::text = user_id)
  WITH CHECK (auth.uid()::text = user_id);

-- Allow authenticated users to DELETE their own files
CREATE POLICY IF NOT EXISTS "Users can delete own files"
  ON user_files FOR DELETE
  USING (auth.uid()::text = user_id);

-- Also add a service_role bypass policy (for when you get a real service role key)
CREATE POLICY IF NOT EXISTS "Service role full access"
  ON user_files FOR ALL
  USING (auth.role() = 'service_role');
"""

print(sql)
print()
print("=" * 60)
print("ALSO FIX YOUR .env FILE:")
print("=" * 60)
print()
print("Your SUPABASE_SERVICE_ROLE_KEY is actually an anon key (role='anon').")
print("Go to Supabase Dashboard -> Settings -> API -> Service Role Key")
print("and update your .env with the correct service role key.")
print()
print("If you don't want to use the service role key, the RLS policies above")
print("will allow authenticated users to manage their own files.")

# Try to run the SQL if we have any working key
print()
print("=" * 60)
print("ATTEMPTING TO APPLY SQL FIX...")
print("=" * 60)

# Try with each key to see if either can run SQL
for key_name, key in [("SUPABASE_SERVICE_ROLE_KEY", sk), ("SUPABASE_KEY", ak)]:
    try:
        r = requests.post(
            f"{url}/rest/v1/rpc/",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={}
        )
        # We can't run arbitrary SQL via REST API
        # User needs to do this in the Supabase Dashboard
    except:
        pass

print()
print("Cannot apply SQL via REST API. Please run the SQL above")
print("in your Supabase Dashboard -> SQL Editor.")
