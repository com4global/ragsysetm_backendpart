"""
SQLite Database Viewer
View all data in your users.db database
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

def connect_db(db_path="users.db"):
    """Connect to the SQLite database"""
    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def view_users(conn):
    """View all users"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    
    print("\n" + "="*80)
    print("👥 USERS TABLE")
    print("="*80)
    
    if not users:
        print("No users found.")
        return
    
    for user in users:
        print(f"\nUser ID: {user['user_id']}")
        print(f"Email: {user['email']}")
        print(f"Full Name: {user['full_name']}")
        print(f"Company: {user['company']}")
        print(f"Role: {user['role']}")
        print(f"Active: {'Yes' if user['is_active'] else 'No'}")
        print(f"Created: {user['created_at']}")
        print(f"Last Login: {user['last_login']}")
        print("-" * 80)
    
    print(f"\nTotal Users: {len(users)}")

def view_user_files(conn):
    """View all user files"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT uf.*, u.email 
        FROM user_files uf
        LEFT JOIN users u ON uf.user_id = u.user_id
        ORDER BY uf.uploaded_at DESC
    """)
    files = cursor.fetchall()
    
    print("\n" + "="*80)
    print("📁 USER FILES TABLE")
    print("="*80)
    
    if not files:
        print("No files found.")
        return
    
    for file in files:
        print(f"\nFile ID: {file['id']}")
        print(f"User: {file['email']}")
        print(f"Filename: {file['filename']}")
        print(f"Type: {file['file_type']}")
        print(f"Size: {file['file_size']:,} bytes")
        print(f"Chunks: {file['chunks_created']}")
        print(f"Processed: {'Yes' if file['processed'] else 'No'}")
        print(f"Uploaded: {file['uploaded_at']}")
        print("-" * 80)
    
    print(f"\nTotal Files: {len(files)}")

def view_chat_history(conn):
    """View chat history"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT ch.*, u.email 
        FROM chat_history ch
        LEFT JOIN users u ON ch.user_id = u.user_id
        ORDER BY ch.timestamp DESC
        LIMIT 20
    """)
    chats = cursor.fetchall()
    
    print("\n" + "="*80)
    print("💬 CHAT HISTORY (Last 20)")
    print("="*80)
    
    if not chats:
        print("No chat history found.")
        return
    
    for chat in chats:
        print(f"\nChat ID: {chat['id']}")
        print(f"User: {chat['email']}")
        print(f"Session: {chat['session_id']}")
        print(f"Query: {chat['query'][:100]}...")
        print(f"Response: {chat['response'][:100]}...")
        print(f"Timestamp: {chat['timestamp']}")
        print("-" * 80)
    
    print(f"\nShowing last 20 chats")

def view_refresh_tokens(conn):
    """View refresh tokens"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rt.*, u.email 
        FROM refresh_tokens rt
        LEFT JOIN users u ON rt.user_id = u.user_id
        ORDER BY rt.created_at DESC
    """)
    tokens = cursor.fetchall()
    
    print("\n" + "="*80)
    print("🔑 REFRESH TOKENS")
    print("="*80)
    
    if not tokens:
        print("No refresh tokens found.")
        return
    
    for token in tokens:
        is_expired = datetime.fromisoformat(token['expires_at']) < datetime.now()
        print(f"\nToken ID: {token['id']}")
        print(f"User: {token['email']}")
        print(f"Token: {token['token'][:50]}...")
        print(f"Expires: {token['expires_at']}")
        print(f"Status: {'EXPIRED' if is_expired else 'VALID'}")
        print(f"Created: {token['created_at']}")
        print("-" * 80)
    
    print(f"\nTotal Tokens: {len(tokens)}")

def get_statistics(conn):
    """Get database statistics"""
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("📊 DATABASE STATISTICS")
    print("="*80)
    
    # Total users
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    print(f"\nTotal Users: {total_users}")
    
    # Active users
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = 1")
    active_users = cursor.fetchone()['count']
    print(f"Active Users: {active_users}")
    
    # Total files
    cursor.execute("SELECT COUNT(*) as count FROM user_files")
    total_files = cursor.fetchone()['count']
    print(f"Total Files: {total_files}")
    
    # Processed files
    cursor.execute("SELECT COUNT(*) as count FROM user_files WHERE processed = 1")
    processed_files = cursor.fetchone()['count']
    print(f"Processed Files: {processed_files}")
    
    # Total chats
    cursor.execute("SELECT COUNT(*) as count FROM chat_history")
    total_chats = cursor.fetchone()['count']
    print(f"Total Chats: {total_chats}")
    
    # Total refresh tokens
    cursor.execute("SELECT COUNT(*) as count FROM refresh_tokens")
    total_tokens = cursor.fetchone()['count']
    print(f"Total Refresh Tokens: {total_tokens}")
    
    # Files by user
    cursor.execute("""
        SELECT u.email, COUNT(uf.id) as file_count
        FROM users u
        LEFT JOIN user_files uf ON u.user_id = uf.user_id
        GROUP BY u.user_id
    """)
    print(f"\nFiles by User:")
    for row in cursor.fetchall():
        print(f"  {row['email']}: {row['file_count']} files")
    
    print("="*80)

def main():
    """Main function"""
    print("\n" + "="*80)
    print("🔍 RAG.AI DATABASE VIEWER")
    print("="*80)
    
    # Try different possible database locations
    db_paths = [
        "users.db",
        "database/users.db",
        "./database/users.db",
        "../users.db",
        "C:\\Startup\\GenAISample\\RAG_HR_ASSISTANT\\users.db"
    ]
    
    conn = None
    for db_path in db_paths:
        if Path(db_path).exists():
            print(f"\n✅ Found database at: {db_path}")
            conn = connect_db(db_path)
            break
    
    if not conn:
        print("\n❌ Database not found in common locations.")
        print("Please provide the path to your users.db file:")
        custom_path = input("> ")
        conn = connect_db(custom_path)
    
    if not conn:
        print("Exiting...")
        return
    
    try:
        # Show all data
        get_statistics(conn)
        view_users(conn)
        view_user_files(conn)
        view_chat_history(conn)
        view_refresh_tokens(conn)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        conn.close()
        print("\n✅ Database connection closed.")

if __name__ == "__main__":
    main()