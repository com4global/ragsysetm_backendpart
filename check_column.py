
from database import supabase

def check_column():
    if not supabase:
        print("❌ Supabase client not initialized")
        return

    try:
        # Try to select the column
        res = supabase.table('user_files').select('blob_url').limit(1).execute()
        print("✅ Column 'blob_url' exists.")
    except Exception as e:
        print(f"❌ Error/Warning checking column: {e}")
        # It usually throws 400 or similar if column missing

if __name__ == "__main__":
    check_column()
