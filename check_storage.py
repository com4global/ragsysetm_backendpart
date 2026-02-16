
from database import supabase

def check_buckets():
    if not supabase:
        print("❌ Supabase client not initialized")
        return

    try:
        res = supabase.storage.list_buckets()
        print(f"✅ Found {len(res)} buckets:")
        for bucket in res:
            print(f"- {bucket.name} (public: {bucket.public})")
    except Exception as e:
        print(f"❌ Error listing buckets: {e}")

if __name__ == "__main__":
    check_buckets()
