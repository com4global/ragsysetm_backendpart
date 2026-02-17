
import os
from typing import Optional, Dict, List
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")

# Use service role key if available (bypasses RLS), otherwise anon key
_effective_key = SUPABASE_SERVICE_KEY or SUPABASE_KEY
_key_type = "service_role" if SUPABASE_SERVICE_KEY else "anon"
print(f"Supabase client using {_key_type} key")

try:
    supabase: Client = create_client(SUPABASE_URL, _effective_key)
except Exception as e:
    print(f"Failed to initialize Supabase client: {e}")
    supabase = None

class UserDatabase:
    def __init__(self):
        pass # Client is global

    def _get_client_with_token(self, user_token: str = None):
        """Get a Supabase client with the user's JWT set for RLS.
        If using service_role key, token is not needed (RLS bypassed).
        If using anon key, we need to set the user's JWT for RLS policies.
        """
        if _key_type == "service_role":
            return supabase
        
        if not user_token:
            print("⚠️ No user token provided and using anon key — RLS may block writes!")
            print("   Set SUPABASE_SERVICE_ROLE_KEY in your environment to bypass RLS.")
            return supabase
        
        # For anon key + user token: set the auth header so RLS sees auth.uid()
        try:
            client = create_client(SUPABASE_URL, SUPABASE_KEY)
            
            # Method 1: Set PostgREST auth token
            client.postgrest.auth(user_token)
            
            # Method 2: Also set the Authorization header directly on the PostgREST session
            # This ensures auth.uid() resolves in RLS policies
            if hasattr(client.postgrest, 'session') and client.postgrest.session:
                client.postgrest.session.headers.update({
                    "Authorization": f"Bearer {user_token}"
                })
            
            # Method 3: Set headers on the client's internal _headers dict if available
            if hasattr(client, '_headers'):
                client._headers["Authorization"] = f"Bearer {user_token}"
            
            # Method 4: Set on options if available (supabase-py v2+)
            if hasattr(client, 'options') and hasattr(client.options, 'headers'):
                client.options.headers["Authorization"] = f"Bearer {user_token}"
            
            return client
        except Exception as e:
            print(f"Error creating authenticated client: {e}")
            print(f"⚠️ Falling back to global client — RLS may block writes!")
            return supabase
    
    # User Management
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email from profiles table"""
        try:
            response = supabase.table('profiles').select("*").eq('email', email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        try:
            response = supabase.table('profiles').select("*").eq('id', user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error getting user by id: {e}")
            return None

    def update_last_login(self, user_id: str):
        """Update user's last login timestamp"""
        try:
            supabase.table('profiles').update({'last_login': datetime.utcnow().isoformat()}).eq('id', user_id).execute()
        except Exception as e:
            print(f"Error updating last login: {e}")

    # File Management
    def add_user_file(self, user_id: str, filename: str, file_type: str, file_size: int, blob_url: str = None, user_token: str = None) -> Dict:
        """Add a file record for a user"""
        data = {
            "user_id": user_id,
            "filename": filename,
            "file_type": file_type,
            "file_size": file_size,
            "uploaded_at": datetime.utcnow().isoformat(),
            "chunks_created": 0,
            "processed": False
        }
        # Only include blob_url if provided (column may not exist in older schemas)
        if blob_url:
            data["blob_url"] = blob_url
        
        try:
            client = self._get_client_with_token(user_token)
            # Upsert based on (user_id, filename) unique constraint
            response = client.table('user_files').upsert(data, on_conflict='user_id, filename').execute()
            # Return the inserted data
            result = response.data[0] if response.data else data
            print(f"✅ add_user_file success: {filename} for user {user_id}")
            return result
        except Exception as e:
            error_str = str(e)
            print(f"❌ Error adding user file '{filename}': {e}")
            
            # Retry Strategy 1: If RLS violation, retry with service-role client
            if "row-level security" in error_str.lower() or "42501" in error_str:
                print(f"⚠️ RLS blocked insert — retrying with service-role client...")
                if SUPABASE_SERVICE_KEY:
                    try:
                        service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
                        response = service_client.table('user_files').upsert(data, on_conflict='user_id, filename').execute()
                        result = response.data[0] if response.data else data
                        print(f"✅ add_user_file success via service-role: {filename}")
                        return result
                    except Exception as sr_err:
                        # If blob_url column fails in service-role too, retry without it
                        if blob_url and ("blob_url" in str(sr_err) or "column" in str(sr_err).lower()):
                            try:
                                data.pop("blob_url", None)
                                response = service_client.table('user_files').upsert(data, on_conflict='user_id, filename').execute()
                                result = response.data[0] if response.data else data
                                print(f"✅ add_user_file success via service-role (without blob_url): {filename}")
                                return result
                            except Exception as sr_retry_err:
                                print(f"❌ Service-role retry also failed: {sr_retry_err}")
                                raise sr_retry_err
                        print(f"❌ Service-role retry failed: {sr_err}")
                        raise sr_err
                else:
                    print("❌ No SUPABASE_SERVICE_ROLE_KEY set — cannot bypass RLS!")
                    print("   Please add SUPABASE_SERVICE_ROLE_KEY to your environment variables.")
                    raise
            
            # Retry Strategy 2: If blob_url column doesn't exist, retry without it
            if blob_url and ("blob_url" in error_str or "column" in error_str.lower()):
                print(f"⚠️ Retrying without blob_url column...")
                try:
                    data.pop("blob_url", None)
                    client = self._get_client_with_token(user_token)
                    response = client.table('user_files').upsert(data, on_conflict='user_id, filename').execute()
                    result = response.data[0] if response.data else data
                    print(f"✅ add_user_file retry success (without blob_url): {filename}")
                    return result
                except Exception as retry_err:
                    print(f"❌ Retry also failed: {retry_err}")
                    raise retry_err
            raise

    def get_user_files(self, user_id: str, user_token: str = None) -> List[Dict]:
        """Get all files for a specific user"""
        try:
            client = self._get_client_with_token(user_token)
            response = client.table('user_files').select("*").eq('user_id', user_id).order('uploaded_at', desc=True).execute()
            files = response.data
            # Map status
            for f in files:
                f['status'] = 'completed' if f.get('processed') else 'pending'
                f['file_name'] = f.get('filename') # Frontend expects file_name
            return files
        except Exception as e:
            print(f"Error getting user files: {e}")
            return []

    def update_file_processed(self, user_id: str, filename: str, chunks_created: int, user_token: str = None):
        """Mark file as processed"""
        try:
            client = self._get_client_with_token(user_token)
            client.table('user_files').update({
                'processed': True, 
                'chunks_created': chunks_created
            }).eq('user_id', user_id).eq('filename', filename).execute()
        except Exception as e:
            print(f"Error updating file status: {e}")

    def delete_user_file(self, user_id: str, filename: str, user_token: str = None):
        """Delete a file record for a user"""
        try:
            client = self._get_client_with_token(user_token)
            client.table('user_files').delete().eq('user_id', user_id).eq('filename', filename).execute()
        except Exception as e:
            print(f"Error deleting user file: {e}")

    def file_belongs_to_user(self, user_id: str, filename: str, user_token: str = None) -> bool:
        """Check if a file belongs to a user"""
        try:
            client = self._get_client_with_token(user_token)
            response = client.table('user_files').select('id').eq('user_id', user_id).eq('filename', filename).execute()
            return len(response.data) > 0
        except Exception:
            return False

    # Chat History
    def add_chat_message(self, user_id: str, session_id: str, query: str, response: str, sources: List[str] = None, user_token: str = None):
        """Add a chat message to history"""
        try:
            data = {
                "user_id": user_id,
                "session_id": session_id,
                "query": query,
                "response": response,
                "sources": sources or [],
                "timestamp": datetime.utcnow().isoformat()
            }
            client = self._get_client_with_token(user_token)
            client.table('chat_history').insert(data).execute()
        except Exception as e:
            print(f"Error adding chat message: {e}")

    def get_chat_history(self, user_id: str, session_id: Optional[str] = None, limit: int = 50, user_token: str = None) -> List[Dict]:
        """Get chat history for a user"""
        try:
            client = self._get_client_with_token(user_token)
            query = client.table('chat_history').select("*").eq('user_id', user_id)
            if session_id:
                query = query.eq('session_id', session_id)
            
            response = query.order('timestamp', desc=True).limit(limit).execute()
            return response.data
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    # Token Management (Not needed if using Supabase Auth completely, but kept for interface compatibility)
    def save_refresh_token(self, user_id: str, token: str, expires_at: datetime):
        pass # Supabase handles this

    def verify_refresh_token(self, token: str) -> Optional[str]:
        return None # Supabase handles this

    def revoke_refresh_token(self, token: str):
        pass # Supabase handles this

    # Statistics
    def get_user_stats(self, user_id: str, user_token: str = None) -> Dict:
        """Get statistics for a user"""
        try:
            client = self._get_client_with_token(user_token)
            
            # Count files
            files_res = client.table('user_files').select('*', count='exact').eq('user_id', user_id).execute()
            file_count = files_res.count or 0

            # Count chats
            chats_res = client.table('chat_history').select('*', count='exact').eq('user_id', user_id).execute()
            chat_count = chats_res.count or 0
            
            files_data = files_res.data
            total_chunks = sum(f.get('chunks_created', 0) for f in files_data) if files_data else 0
            total_size = sum(f.get('file_size', 0) for f in files_data) if files_data else 0

            return {
                "total_files": file_count,
                "processed_files": sum(1 for f in files_data if f.get('processed')) if files_data else 0,
                "total_chats": chat_count,
                "total_chunks": total_chunks,
                "total_size_bytes": total_size,
                "files_this_week": 0
            }
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {"total_files": 0, "processed_files": 0, "total_chats": 0, "total_chunks": 0, "total_size_bytes": 0, "files_this_week": 0}

# Global instance
user_db = UserDatabase()