# Complete Testing Guide for RAG.AI

## 🎯 Your Issue: File Upload Returns 401 Unauthorized

**Problem**: When you try to upload a file, you get:
```json
{
  "detail": "Not authenticated"
}
```

**Why**: The Swagger UI doesn't automatically add your Bearer token to the request.

**Solution**: You have 3 options below.

---

## 🔧 Solution 1: Use Swagger UI with Authentication (Easiest)

### Step 1: Get Your Token
1. In Swagger UI, go to `POST /api/auth/login`
2. Use your credentials:
   ```json
   {
     "email": "dddd@gmail.com",
     "password": "Abcd@1998"
   }
   ```
3. Copy the `access_token` from the response

### Step 2: Authorize Swagger UI
1. **Click the "Authorize" button** at the top right of Swagger UI (🔓 icon)
2. In the popup, paste your token in the "Value" field:
   ```
   Bearer YOUR_ACCESS_TOKEN_HERE
   ```
   (Make sure to include the word "Bearer" followed by a space)
3. Click "Authorize"
4. Click "Close"

### Step 3: Test File Upload
1. Now go to `POST /api/upload`
2. Click "Try it out"
3. Upload your file
4. Execute

**It should now work!** ✅

---

## 🔧 Solution 2: Use Python Script (Automated Testing)

I've created a complete testing script for you.

### Setup:
```bash
# Install requests if not already installed
pip install requests

# Run the test script
python test_endpoints.py
```

### What it does:
- ✅ Tests all your endpoints automatically
- ✅ Handles authentication for you
- ✅ Tests file upload with proper Bearer token
- ✅ Shows you exactly what's working and what's not

### Usage:
```bash
python test_endpoints.py
```

Follow the prompts:
1. Choose to login with existing user
2. Test file operations
3. Upload a file (it will handle the token for you!)

---

## 🔧 Solution 3: Use curl with Bearer Token

### Step 1: Login and Get Token
```bash
curl -X POST http://127.0.0.1:10000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"dddd@gmail.com\",\"password\":\"Abcd@1998\"}"
```

**Copy the access_token from the response.**

### Step 2: Upload File with Token
```bash
curl -X POST http://127.0.0.1:10000/api/upload \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE" \
  -F "file=@snowfall.pdf"
```

**Replace `YOUR_ACCESS_TOKEN_HERE` with your actual token!**

---

## 📊 Check Your Database

To see all your data in SQLite:

```bash
python database_viewer.py
```

This will show you:
- ✅ All registered users
- ✅ All uploaded files (per user)
- ✅ Chat history
- ✅ Refresh tokens
- ✅ Statistics

### Manual Database Check (Alternative)

**Windows:**
```bash
# Install DB Browser for SQLite (GUI tool)
# Download from: https://sqlitebrowser.org/

# Or use command line
sqlite3 users.db
```

**Once in sqlite3:**
```sql
-- View all tables
.tables

-- View users
SELECT * FROM users;

-- View files
SELECT * FROM user_files;

-- View chat history
SELECT * FROM chat_history;

-- Count records
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM user_files;
```

---

## 🧪 Complete Testing Workflow

### 1. Start Your Server
```bash
python main.py
```

### 2. Check Database
```bash
python database_viewer.py
```

### 3. Test All Endpoints
```bash
python test_endpoints.py
```

---

## 📋 Quick Reference: All Endpoints

### ✅ Public Endpoints (No Auth Required)
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /` - Health check

### 🔒 Protected Endpoints (Need Bearer Token)
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Logout user
- `POST /api/upload` - Upload file ⚠️ **This is where you had the issue**
- `GET /api/files` - Get user's files
- `POST /api/process-file` - Process uploaded file
- `DELETE /api/files/{filename}` - Delete file
- `POST /chat` - Send chat message
- `GET /api/chat/history` - Get chat history

---

## 🔍 How to Debug Your Specific Issue

### Check 1: Is the user in the database?
```bash
python database_viewer.py
```
Look for `dddd@gmail.com` in the USERS table.

### Check 2: Does login work?
```bash
curl -X POST http://127.0.0.1:10000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"dddd@gmail.com\",\"password\":\"Abcd@1998\"}"
```
You should get tokens back.

### Check 3: Can you access protected endpoint?
```bash
# First, get your token from login above, then:
curl -X GET http://127.0.0.1:10000/api/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```
You should see your user info.

### Check 4: Test file upload with token
```bash
curl -X POST http://127.0.0.1:10000/api/upload \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -F "file=@snowfall.pdf"
```
This should work now!

---

## 🎓 Understanding the Error

**Your error:**
```json
{
  "detail": "Not authenticated",
  "www-authenticate": "Bearer"
}
```

**What it means:**
- The endpoint requires authentication (Bearer token)
- You didn't include the Authorization header
- OR the token is invalid/expired

**The fix:**
Always include the Authorization header:
```
Authorization: Bearer {your_access_token}
```

---

## 📱 Testing from React Frontend

If you want to test from your React app:

1. **Make sure AuthContext is properly set up**
2. **Login through the UI**
3. **The token will be stored automatically in localStorage**
4. **All API calls will include the token**

To verify:
```javascript
// In browser console (F12)
console.log(localStorage.getItem('access_token'));
```

You should see your token!

---

## 🐛 Common Issues & Solutions

### Issue: "Not authenticated" when uploading
**Solution**: Add Bearer token to request (see Solution 1-3 above)

### Issue: "Token expired"
**Solution**: Login again or use refresh token endpoint

### Issue: "Database is locked"
**Solution**: Close any other programs accessing the database

### Issue: "File not found"
**Solution**: Check that file exists at the specified path

### Issue: Can't find users.db
**Solution**: The database viewer will search common locations automatically

---

## 📞 Need More Help?

1. **Run the automated tests**: `python test_endpoints.py`
2. **Check the database**: `python database_viewer.py`
3. **Check server logs** for detailed error messages
4. **Use Swagger UI with proper authorization** (easiest for manual testing)

---

## 🎯 TL;DR - Quick Fix for Your Issue

**Your file upload fails because Swagger UI doesn't auto-add the token.**

**Quick fix:**
1. Login in Swagger UI
2. Copy the access_token
3. Click "Authorize" button (top right)
4. Paste: `Bearer {your_token}`
5. Now file upload will work!

**Better fix:**
```bash
python test_endpoints.py
```
Let the script handle everything for you!