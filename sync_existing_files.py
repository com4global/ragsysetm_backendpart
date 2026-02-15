"""
Sync existing files from .file_metadata.json into Supabase user_files table.
Uses direct PostgreSQL connection to bypass RLS.
"""
import os, json
import psycopg2
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
USER_ID = "c3ed23c5-0a1a-4b08-b62c-e6a920cff35b"  # From backend logs

# Load existing file metadata
with open("resources/.file_metadata.json", "r") as f:
    metadata = json.load(f)

print(f"Found {len(metadata.get('files', []))} files in metadata")

# Connect to PostgreSQL directly (bypasses RLS)
try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    print("Connected to PostgreSQL directly")
except Exception as e:
    print(f"PostgreSQL connection failed: {e}")
    print("Trying with sslmode=require...")
    try:
        conn = psycopg2.connect(DATABASE_URL + "?sslmode=require")
        conn.autocommit = True
        cur = conn.cursor()
        print("Connected with SSL")
    except Exception as e2:
        print(f"Still failed: {e2}")
        exit(1)

# Check if profile exists
cur.execute("SELECT id, email FROM profiles WHERE id = %s", (USER_ID,))
profile = cur.fetchone()
if profile:
    print(f"User profile found: id={profile[0]}, email={profile[1]}")
else:
    print(f"WARNING: No profile for user_id={USER_ID}")
    print("Checking all profiles...")
    cur.execute("SELECT id, email FROM profiles LIMIT 10")
    profiles = cur.fetchall()
    for p in profiles:
        print(f"  id={p[0]}, email={p[1]}")
    if profiles:
        USER_ID = profiles[0][0]
        print(f"Using first profile: {USER_ID}")
    else:
        print("No profiles found! Cannot sync.")
        exit(1)

# Check existing records
cur.execute("SELECT COUNT(*) FROM user_files WHERE user_id = %s", (USER_ID,))
count = cur.fetchone()[0]
print(f"Existing records for user: {count}")

# File type mapping
def get_file_type(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    type_map = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain',
        'mp4': 'video/mp4',
    }
    return type_map.get(ext, 'application/octet-stream')

# Sync files
synced = 0
for file_meta in metadata.get("files", []):
    filename = file_meta.get("file_name", "")
    if not filename:
        continue
    
    file_type = get_file_type(filename)
    file_size = file_meta.get("file_size", 0)
    chunks = file_meta.get("chunks_created", 0)
    processed = file_meta.get("processed", False)
    uploaded_at = file_meta.get("uploaded_at", "2025-01-01T00:00:00")
    
    # Get actual file size from disk if available
    filepath = os.path.join("resources", filename)
    if os.path.exists(filepath) and file_size == 0:
        file_size = os.path.getsize(filepath)
    
    try:
        cur.execute("""
            INSERT INTO user_files (user_id, filename, file_type, file_size, chunks_created, processed, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, filename) DO UPDATE SET
                chunks_created = EXCLUDED.chunks_created,
                processed = EXCLUDED.processed
        """, (USER_ID, filename, file_type, file_size, chunks, processed, uploaded_at))
        synced += 1
        print(f"  ✅ Synced: {filename} (chunks={chunks}, processed={processed})")
    except Exception as e:
        print(f"  ❌ Failed: {filename}: {e}")

print(f"\nSynced {synced} files")

# Verify
cur.execute("SELECT COUNT(*) FROM user_files WHERE user_id = %s", (USER_ID,))
final_count = cur.fetchone()[0]
print(f"Total files in user_files for user: {final_count}")

# Also check files query
cur.execute("SELECT filename, processed, chunks_created FROM user_files WHERE user_id = %s ORDER BY uploaded_at DESC", (USER_ID,))
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]}: processed={r[1]}, chunks={r[2]}")

cur.close()
conn.close()
print("\nDone!")
