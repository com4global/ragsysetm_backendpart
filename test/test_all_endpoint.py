"""
API Endpoint Tester
Test all your FastAPI endpoints with authentication
"""

import requests
import json
from pathlib import Path
import time

BASE_URL = "http://127.0.0.1:10000"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class APITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        
    def print_header(self, title):
        print(f"\n{'='*80}")
        print(f"{Colors.BLUE}{title}{Colors.END}")
        print('='*80)
    
    def print_success(self, message):
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")
    
    def print_error(self, message):
        print(f"{Colors.RED}❌ {message}{Colors.END}")
    
    def print_info(self, message):
        print(f"{Colors.YELLOW}ℹ️  {message}{Colors.END}")
    
    # ==================== AUTH ENDPOINTS ====================
    
    def test_register(self, email, password, full_name, company=None):
        """Test registration endpoint"""
        self.print_header("TEST: Register User")
        
        url = f"{self.base_url}/api/auth/register"
        data = {
            "email": email,
            "password": password,
            "full_name": full_name,
            "company": company
        }
        
        try:
            response = requests.post(url, json=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 201:
                result = response.json()
                self.access_token = result['access_token']
                self.refresh_token = result['refresh_token']
                self.print_success("Registration successful!")
                print(f"Access Token: {self.access_token[:50]}...")
                print(f"Refresh Token: {self.refresh_token[:50]}...")
                return True
            else:
                self.print_error(f"Registration failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_login(self, email, password):
        """Test login endpoint"""
        self.print_header("TEST: Login User")
        
        url = f"{self.base_url}/api/auth/login"
        data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(url, json=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result['access_token']
                self.refresh_token = result['refresh_token']
                self.print_success("Login successful!")
                print(f"Access Token: {self.access_token[:50]}...")
                print(f"Refresh Token: {self.refresh_token[:50]}...")
                return True
            else:
                self.print_error(f"Login failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_get_current_user(self):
        """Test get current user endpoint"""
        self.print_header("TEST: Get Current User")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        url = f"{self.base_url}/api/auth/me"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                user = response.json()
                self.user_id = user['user_id']
                self.print_success("User info retrieved!")
                print(f"User ID: {user['user_id']}")
                print(f"Email: {user['email']}")
                print(f"Name: {user['full_name']}")
                print(f"Company: {user.get('company', 'N/A')}")
                print(f"Role: {user['role']}")
                print(f"Total Files: {user.get('total_files', 0)}")
                print(f"Total Chats: {user.get('total_chats', 0)}")
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_refresh_token(self):
        """Test token refresh endpoint"""
        self.print_header("TEST: Refresh Access Token")
        
        if not self.refresh_token:
            self.print_error("No refresh token available.")
            return False
        
        url = f"{self.base_url}/api/auth/refresh"
        data = {"refresh_token": self.refresh_token}
        
        try:
            response = requests.post(url, json=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.access_token = result['access_token']
                self.print_success("Token refreshed!")
                print(f"New Access Token: {self.access_token[:50]}...")
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    # ==================== FILE ENDPOINTS ====================
    
    def test_upload_file(self, file_path):
        """Test file upload endpoint"""
        self.print_header("TEST: Upload File")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        if not Path(file_path).exists():
            self.print_error(f"File not found: {file_path}")
            return False
        
        url = f"{self.base_url}/api/upload"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f)}
                response = requests.post(url, headers=headers, files=files)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.print_success("File uploaded!")
                print(f"File: {result['file']}")
                return True
            else:
                self.print_error(f"Upload failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_get_files(self):
        """Test get files endpoint"""
        self.print_header("TEST: Get User Files")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        url = f"{self.base_url}/api/files"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                files = result['files']
                stats = result['stats']
                
                self.print_success(f"Retrieved {len(files)} files")
                print(f"\nStatistics:")
                print(f"  Total Files: {stats.get('total_files', 0)}")
                print(f"  Total Chats: {stats.get('total_chats', 0)}")
                print(f"  Total Chunks: {stats.get('total_chunks', 0)}")
                
                if files:
                    print(f"\nFiles:")
                    for file in files:
                        print(f"  - {file['filename']} ({file['file_type']}, {file['file_size']} bytes)")
                
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_process_file(self, filename):
        """Test process file endpoint"""
        self.print_header("TEST: Process File")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        url = f"{self.base_url}/api/process-file"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"filename": filename}
        
        try:
            response = requests.post(url, headers=headers, params=params)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.print_success("File processed!")
                print(f"Result: {result}")
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    # ==================== CHAT ENDPOINTS ====================
    
    def test_chat(self, query):
        """Test chat endpoint"""
        self.print_header("TEST: Send Chat Message")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        url = f"{self.base_url}/chat"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        data = {"query": query}
        
        try:
            response = requests.post(url, headers=headers, json=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.print_success("Chat response received!")
                print(f"\nQuery: {result['query']}")
                print(f"Response: {result['response'][:200]}...")
                print(f"Sources: {len(result.get('sources', []))} sources")
                print(f"Session ID: {result.get('session_id', 'N/A')}")
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    def test_chat_history(self):
        """Test get chat history endpoint"""
        self.print_header("TEST: Get Chat History")
        
        if not self.access_token:
            self.print_error("No access token. Please login first.")
            return False
        
        url = f"{self.base_url}/api/chat/history"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(url, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                history = result['history']
                self.print_success(f"Retrieved {len(history)} chat messages")
                
                if history:
                    print(f"\nRecent chats:")
                    for chat in history[:5]:
                        print(f"  - {chat['query'][:50]}...")
                
                return True
            else:
                self.print_error(f"Failed: {response.json()}")
                return False
        except Exception as e:
            self.print_error(f"Error: {e}")
            return False
    
    # ==================== HEALTH CHECK ====================
    
    def test_health(self):
        """Test health endpoint"""
        self.print_header("TEST: Health Check")
        
        url = f"{self.base_url}/"
        
        try:
            response = requests.get(url)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self.print_success("Server is healthy!")
                print(f"Message: {result.get('message', 'N/A')}")
                print(f"Status: {result.get('status', 'N/A')}")
                return True
            else:
                self.print_error("Server unhealthy")
                return False
        except Exception as e:
            self.print_error(f"Server not reachable: {e}")
            return False

def main():
    """Main test runner"""
    print("\n" + "="*80)
    print(f"{Colors.BLUE}🧪 RAG.AI API ENDPOINT TESTER{Colors.END}")
    print("="*80)
    
    tester = APITester(BASE_URL)
    
    # Test server health
    tester.test_health()
    time.sleep(1)
    
    # Test authentication flow
    print("\n\n📝 TESTING AUTHENTICATION FLOW")
    print("-"*80)
    
    # Option 1: Register new user
    print("\nOption 1: Register new user")
    print("Option 2: Login with existing user")
    choice = input("\nChoose option (1 or 2): ")
    
    if choice == "1":
        email = input("Email: ")
        password = input("Password: ")
        full_name = input("Full Name: ")
        company = input("Company (optional): ")
        
        if tester.test_register(email, password, full_name, company or None):
            time.sleep(1)
            tester.test_get_current_user()
    else:
        # Use your existing credentials
        email = "dddd@gmail.com"
        password = "Abcd@1998"
        
        if tester.test_login(email, password):
            time.sleep(1)
            tester.test_get_current_user()
    
    if not tester.access_token:
        print("\n❌ Authentication failed. Cannot proceed with protected endpoints.")
        return
    
    # Test file operations
    print("\n\n📁 TESTING FILE OPERATIONS")
    print("-"*80)
    
    time.sleep(1)
    tester.test_get_files()
    
    # Ask if user wants to upload a file
    upload_choice = input("\n\nDo you want to test file upload? (y/n): ")
    if upload_choice.lower() == 'y':
        file_path = input("Enter file path: ")
        if tester.test_upload_file(file_path):
            time.sleep(1)
            # Get filename from path
            filename = Path(file_path).name
            process_choice = input(f"\nProcess {filename}? (y/n): ")
            if process_choice.lower() == 'y':
                tester.test_process_file(filename)
    
    # Test chat
    print("\n\n💬 TESTING CHAT OPERATIONS")
    print("-"*80)
    
    time.sleep(1)
    chat_choice = input("\nDo you want to test chat? (y/n): ")
    if chat_choice.lower() == 'y':
        query = input("Enter your question: ")
        tester.test_chat(query)
        time.sleep(1)
        tester.test_chat_history()
    
    # Test token refresh
    print("\n\n🔄 TESTING TOKEN REFRESH")
    print("-"*80)
    time.sleep(1)
    tester.test_refresh_token()
    
    print("\n\n" + "="*80)
    print(f"{Colors.GREEN}✅ ALL TESTS COMPLETED{Colors.END}")
    print("="*80)

if __name__ == "__main__":
    main()