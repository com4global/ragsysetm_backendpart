"""
Apply RLS policies to user_files table using Supabase SQL RPC.
This script attempts to add INSERT/UPDATE/DELETE policies via the Management API.
If it fails, it prints the SQL for you to run manually in the Supabase Dashboard.
"""
from dotenv import load_dotenv
load_dotenv()
import os, json, base64, requests

url = os.getenv("SUPABASE_URL")
sk = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
ak = os.getenv("SUPABASE_KEY")

# Find both keys
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
    except:
        pass

best_key = anon_key or sk or ak

# First check existing policies
print("=== Checking existing RLS policies ===\n")

# Get current policies via information_schema
try:
    # Check if table exists and RLS is enabled
    r = requests.get(
        f"{url}/rest/v1/user_files?select=*&limit=0",
        headers={
            "apikey": best_key,
            "Authorization": f"Bearer {best_key}"
        }
    )
    print(f"Table check: {r.status_code}")
except Exception as e:
    print(f"Table check error: {e}")

# The SQL we need to run
policies_sql = [
    # Check if user_id is UUID or text
    """
DO $$
DECLARE
    col_type text;
BEGIN
    SELECT data_type INTO col_type 
    FROM information_schema.columns 
    WHERE table_name = 'user_files' AND column_name = 'user_id';
    
    RAISE NOTICE 'user_id column type: %', col_type;
    
    -- Drop existing restrictive policies if any
    BEGIN
        DROP POLICY IF EXISTS "Users can view own files" ON user_files;
        DROP POLICY IF EXISTS "Users can insert own files" ON user_files;
        DROP POLICY IF EXISTS "Users can update own files" ON user_files;
        DROP POLICY IF EXISTS "Users can delete own files" ON user_files;
        DROP POLICY IF EXISTS "Service role full access" ON user_files;
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;
    
    -- Ensure RLS is enabled
    ALTER TABLE user_files ENABLE ROW LEVEL SECURITY;
    
    -- Create policies based on column type
    IF col_type = 'uuid' THEN
        -- UUID type: direct comparison
        CREATE POLICY "Users can view own files"
            ON user_files FOR SELECT
            USING (auth.uid() = user_id);
            
        CREATE POLICY "Users can insert own files"
            ON user_files FOR INSERT
            WITH CHECK (auth.uid() = user_id);
            
        CREATE POLICY "Users can update own files"
            ON user_files FOR UPDATE
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id);
            
        CREATE POLICY "Users can delete own files"
            ON user_files FOR DELETE
            USING (auth.uid() = user_id);
    ELSE
        -- Text type: cast auth.uid() to text
        CREATE POLICY "Users can view own files"
            ON user_files FOR SELECT
            USING (auth.uid()::text = user_id);
            
        CREATE POLICY "Users can insert own files"
            ON user_files FOR INSERT
            WITH CHECK (auth.uid()::text = user_id);
            
        CREATE POLICY "Users can update own files"
            ON user_files FOR UPDATE
            USING (auth.uid()::text = user_id)
            WITH CHECK (auth.uid()::text = user_id);
            
        CREATE POLICY "Users can delete own files"
            ON user_files FOR DELETE
            USING (auth.uid()::text = user_id);
    END IF;
    
    RAISE NOTICE 'RLS policies created successfully!';
END
$$;
""".strip()
]

print(f"\n{'='*60}")
print("RLS POLICY SQL")  
print(f"{'='*60}")
print("\nPlease run the following SQL in your Supabase Dashboard")
print("(Dashboard -> SQL Editor -> New Query):\n")
for sql in policies_sql:
    print(sql)
print(f"\n{'='*60}")

# Also provide a simpler version in case the DO block doesn't work
print("\nIf the above doesn't work, try this simpler version:")
print("""
-- Simple version (assumes user_id is text type)
ALTER TABLE user_files ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view own files" ON user_files;
DROP POLICY IF EXISTS "Users can insert own files" ON user_files;
DROP POLICY IF EXISTS "Users can update own files" ON user_files;
DROP POLICY IF EXISTS "Users can delete own files" ON user_files;

CREATE POLICY "Users can view own files"
    ON user_files FOR SELECT
    USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own files"
    ON user_files FOR INSERT
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can update own files"
    ON user_files FOR UPDATE
    USING (auth.uid()::text = user_id)
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "Users can delete own files"
    ON user_files FOR DELETE
    USING (auth.uid()::text = user_id);
""")
