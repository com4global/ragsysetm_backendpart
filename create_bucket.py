
from database import supabase

def create_bucket():
    if not supabase:
        print("❌ Supabase client not initialized")
        return

    try:
        # Check if bucket exists first
        buckets = supabase.storage.list_buckets()
        existing = [b.name for b in buckets if b.name == "uploads"]
        
        if existing:
            print("✅ Bucket 'uploads' already exists.")
        else:
            print("Creating 'uploads' bucket...")
            res = supabase.storage.create_bucket("uploads", options={"public": True})
            print(f"✅ Bucket 'uploads' created successfully: {res}")
            
    except Exception as e:
        print(f"❌ Error creating bucket: {e}")

if __name__ == "__main__":
    create_bucket()
