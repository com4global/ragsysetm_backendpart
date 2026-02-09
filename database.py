"""
User Database Manager
Handles user CRUD operations with secure data isolation
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional, Dict, List
from contextlib import contextmanager
from pathlib import Path

# This gets the directory where database.py actually lives
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "users.db"

print(f"Database is located at: {DATABASE_PATH}")
DATABASE_PATH.parent.mkdir(exist_ok=True)

class UserDatabase:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self._initialize_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def _initialize_database(self):
        """Create database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    company TEXT,
                    role TEXT DEFAULT 'user',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    preferences TEXT DEFAULT '{}'
                )
            """)
            
            # User files table - links files to users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT,
                    file_size INTEGER,
                    chunks_created INTEGER DEFAULT 0,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, filename)
                )
            """)
            
            # Chat history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL,
                    sources TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Refresh tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_files_user ON user_files(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_session ON chat_history(user_id, session_id)")
    
    # User Management
    def create_user(self, email: str, password_hash: str, full_name: str, 
                   company: Optional[str] = None) -> Dict:
        """Create a new user"""
        user_id = str(uuid.uuid4())
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (user_id, email, password_hash, full_name, company)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, email, password_hash, full_name, company))
        
        return self.get_user_by_id(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_last_login(self, user_id: str):
        """Update user's last login timestamp"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET last_login = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            """, (user_id,))
    
    # File Management
    def add_user_file(self, user_id: str, filename: str, file_type: str, 
                     file_size: int) -> Dict:
        """Add a file record for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_files (user_id, filename, file_type, file_size)
                VALUES (?, ?, ?, ?)
            """, (user_id, filename, file_type, file_size))
            
            return {
                "filename": filename,
                "file_type": file_type,
                "file_size": file_size,
                "uploaded_at": datetime.now().isoformat()
            }
    
    # ✅ FIXED: Move fetchall() inside the context manager
    def get_user_files(self, user_id: str) -> List[Dict]:
        """Get all files for a specific user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id,
                    user_id,
                    filename as file_name,
                    file_type,
                    file_size,
                    chunks_created,
                    uploaded_at,
                    CASE 
                        WHEN processed = 1 THEN 'completed'
                        ELSE 'pending'
                    END as status
                FROM user_files 
                WHERE user_id = ? 
                ORDER BY uploaded_at DESC
            """, (user_id,))
            # ✅ Fetch data BEFORE the connection closes
            rows = cursor.fetchall()
            return [dict(row) for row in rows]  # ✅ Now inside the context
    
    def update_file_processed(self, user_id: str, filename: str, chunks_created: int):
        """Mark file as processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_files 
                SET processed = 1, chunks_created = ?
                WHERE user_id = ? AND filename = ?
            """, (chunks_created, user_id, filename))
    
    def delete_user_file(self, user_id: str, filename: str):
        """Delete a file record for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM user_files 
                WHERE user_id = ? AND filename = ?
            """, (user_id, filename))
    
    def file_belongs_to_user(self, user_id: str, filename: str) -> bool:
        """Check if a file belongs to a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_files 
                WHERE user_id = ? AND filename = ?
            """, (user_id, filename))
            return cursor.fetchone()['count'] > 0
    
    # Chat History
    def add_chat_message(self, user_id: str, session_id: str, query: str, 
                        response: str, sources: List[str] = None):
        """Add a chat message to history"""
        import json
        sources_json = json.dumps(sources or [])
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_history (user_id, session_id, query, response, sources)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, session_id, query, response, sources_json))
    
    def get_chat_history(self, user_id: str, session_id: Optional[str] = None, 
                        limit: int = 50) -> List[Dict]:
        """Get chat history for a user"""
        import json
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT * FROM chat_history 
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (user_id, session_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM chat_history 
                    WHERE user_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (user_id, limit))
            
            # ✅ Fetch inside context manager
            rows = cursor.fetchall()
            history = []
            for row in rows:
                row_dict = dict(row)
                row_dict['sources'] = json.loads(row_dict['sources'])
                history.append(row_dict)
            
            return history
    
    # Token Management
    def save_refresh_token(self, user_id: str, token: str, expires_at: datetime):
        """Save a refresh token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO refresh_tokens (user_id, token, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, token, expires_at.isoformat()))
    
    def verify_refresh_token(self, token: str) -> Optional[str]:
        """Verify refresh token and return user_id"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM refresh_tokens 
                WHERE token = ? AND expires_at > CURRENT_TIMESTAMP
            """, (token,))
            row = cursor.fetchone()
            return row['user_id'] if row else None
    
    def revoke_refresh_token(self, token: str):
        """Revoke a refresh token"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM refresh_tokens WHERE token = ?", (token,))
    
    # Statistics
    def get_user_stats(self, user_id: str) -> Dict:
        """Get statistics for a user"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # File count
            cursor.execute("""
                SELECT COUNT(*) as count FROM user_files WHERE user_id = ?
            """, (user_id,))
            file_count = cursor.fetchone()['count']
            
            # Chat count
            cursor.execute("""
                SELECT COUNT(*) as count FROM chat_history WHERE user_id = ?
            """, (user_id,))
            chat_count = cursor.fetchone()['count']
            
            # Total chunks
            cursor.execute("""
                SELECT COALESCE(SUM(chunks_created), 0) as total 
                FROM user_files WHERE user_id = ?
            """, (user_id,))
            total_chunks = cursor.fetchone()['total']
            
            return {
                "total_files": file_count,
                "total_chats": chat_count,
                "total_chunks": total_chunks
            }

# Global instance
user_db = UserDatabase()