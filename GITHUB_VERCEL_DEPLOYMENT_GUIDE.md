# 🚀 GITHUB & VERCEL DEPLOYMENT GUIDE

## PART 1: PUSH CODE TO GITHUB

### Step 1: Verify Git is Initialized
```bash
cd C:\Startup\GenAISample\RAG_HR_ASSISTANT
git status
```

If you see: `fatal: not a git repository` → Initialize git:
```bash
git init
```

### Step 2: Configure Git (First Time Only)
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@gmail.com"
```

### Step 3: Add Files to Git
```bash
# Add all files
git add .

# Verify files are staged
git status
```

### Step 4: Create Initial Commit
```bash
git commit -m "Initial commit: Multimodal RAG System with text, image, audio, video support"
```

### Step 5: Create Main Branch
```bash
git branch -M main
```

### Step 6: Add GitHub Remote Repository
```bash
# Replace with YOUR repository URL
git remote add origin https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT.git

# Verify remote was added
git remote -v
```

### Step 7: Push to GitHub
```bash
git push -u origin main
```

**Expected Output:**
```
Counting objects: 150+
Delta compression using up to 8 threads
Compressing objects: 100%
Writing objects: 100%
Creating deltas: 100%

To https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

---

## PART 2: PREPARE BACKEND FOR VERCEL DEPLOYMENT

### Step 1: Create Vercel Configuration Files

**File: `vercel.json`**
```json
{
  "version": 2,
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "main.py"
    }
  ],
  "env": {
    "OPENAI_API_KEY": "@openai_api_key",
    "PINECONE_API_KEY": "@pinecone_api_key",
    "PINECONE_INDEX_NAME": "hr-assistant-index"
  }
}
```

**File: `.vercelignore`**
```
.git
.myenv
__pycache__
*.pyc
.pytest_cache
node_modules
.env.local
frontend
resources
test_*.py
debug_*.py
```

**File: `api/index.py`** (Vercel-compatible entry point)
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from main import app as fastapi_app

# Export for Vercel
app = fastapi_app

# Ensure CORS is configured
if not any(isinstance(middleware, type(CORSMiddleware)) for middleware in app.user_middleware):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### Step 2: Create `.env.example` (No Real Keys)
```
OPENAI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=hr-assistant-index
```

### Step 3: Update `requirements.txt` for Production
Verify it contains all dependencies (already done ✅)

---

## PART 3: SETUP VERCEL DEPLOYMENT

### Step 1: Create Vercel Account
1. Go to https://vercel.com
2. Sign up with GitHub account
3. Authorize Vercel to access your repositories

### Step 2: Create New Project
1. Click "New Project"
2. Select your GitHub repository: "RAG_HR_ASSISTANT"
3. Select framework: **Other** (Python)
4. Configure settings:
   - **Root Directory:** ./ (or leave default)
   - **Build Command:** `pip install -r requirements.txt`
   - **Output Directory:** (leave empty)
   - **Install Command:** `pip install -r requirements.txt`

### Step 3: Add Environment Variables in Vercel
1. Click **Settings** → **Environment Variables**
2. Add each variable:

```
OPENAI_API_KEY = sk-proj-xxxxxxxx...
PINECONE_API_KEY = pcaxxxxxxxx...
PINECONE_INDEX_NAME = hr-assistant-index
```

⚠️ **IMPORTANT:** Use the same keys as your local .env

### Step 4: Deploy
1. Click **Deploy**
2. Wait for deployment (usually 2-5 minutes)
3. You'll get a URL like: `https://your-project.vercel.app`

### Step 5: Get API Endpoint
After deployment, your API endpoint is:
```
https://your-project.vercel.app
```

Your endpoints will be:
```
POST   https://your-project.vercel.app/chat
POST   https://your-project.vercel.app/api/upload
POST   https://your-project.vercel.app/api/process-file
GET    https://your-project.vercel.app/api/files
GET    https://your-project.vercel.app/docs
```

---

## PART 4: UPDATE FRONTEND WITH CLOUD ENDPOINT

### Step 1: Locate Frontend Configuration
File: `frontend/src/App.js` or `frontend/src/config.js`

### Step 2: Find API Base URL
Look for:
```javascript
const API_BASE_URL = "http://127.0.0.1:8000"
// OR
const API_URL = "http://localhost:8000"
```

### Step 3: Update to Vercel URL
Replace with:
```javascript
// For development (local)
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000"

// OR for production
const API_BASE_URL = "https://your-project.vercel.app"
```

### Step 4: Create Frontend Environment File
**File: `frontend/.env.local`**
```
REACT_APP_API_URL=https://your-project.vercel.app
```

### Step 5: Update All API Calls
Find all axios/fetch calls and ensure they use the base URL:

```javascript
// ❌ BEFORE (hardcoded localhost)
fetch("http://127.0.0.1:8000/chat", {...})

// ✅ AFTER (uses environment variable)
fetch(`${API_BASE_URL}/chat`, {...})
```

### Step 6: Specific Files to Update

**File: `frontend/src/ChatInterface.js`**
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

// Update all API calls
const response = await fetch(`${API_BASE_URL}/chat`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query: userMessage })
});
```

**File: `frontend/src/AdminDashboard.js`**
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

// File upload
const formData = new FormData();
formData.append("file", file);
const uploadResponse = await fetch(`${API_BASE_URL}/api/upload`, {
  method: "POST",
  body: formData
});
```

---

## PART 5: COMPLETE DEPLOYMENT WORKFLOW

### Backend Deployment (First Time)
```bash
# 1. Push code to GitHub
cd C:\Startup\GenAISample\RAG_HR_ASSISTANT
git add .
git commit -m "Add vercel configuration"
git push origin main

# 2. Deploy to Vercel (done via Web UI)
# Visit https://vercel.com/dashboard

# 3. Get your API endpoint from Vercel dashboard
# Example: https://rag-hr-assistant.vercel.app
```

### Frontend Deployment
```bash
# 1. Create Vercel-ready React app (if not already)
cd frontend

# 2. Create .env.local with API endpoint
echo "REACT_APP_API_URL=https://your-vercel-backend.vercel.app" > .env.local

# 3. Build frontend
npm run build

# 4. Initialize frontend git (if separate repo)
git init
git add .
git commit -m "Frontend with Vercel API integration"
git remote add origin https://github.com/YOUR_USERNAME/rag-hr-frontend.git
git push -u origin main

# 5. Deploy to Vercel
# Visit https://vercel.com and create new project from github/YOUR_USERNAME/rag-hr-frontend
```

---

## PART 6: VERIFY DEPLOYMENT

### Test Backend Endpoint
```bash
# Test from PowerShell
$url = "https://your-project.vercel.app/chat"
$body = @{query="Hello"} | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method POST -Body $body -ContentType "application/json"
```

### Test from Frontend
```bash
# In browser console
fetch("https://your-project.vercel.app/chat", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({query: "Test query"})
}).then(r => r.json()).then(console.log)
```

### Check Vercel Logs
1. Go to Vercel Dashboard
2. Select your project
3. Click **Deployments**
4. Click latest deployment
5. View **Function Logs**

---

## TROUBLESHOOTING

### Issue: 502 Bad Gateway
**Solution:** Check Vercel logs for Python errors

### Issue: CORS Error
**Solution:** Ensure CORS is enabled in main.py:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Environment Variables Not Working
**Solution:** 
1. Verify in Vercel dashboard → Settings → Environment Variables
2. Redeploy after adding variables
3. Check that keys match exactly

### Issue: Dependencies Not Installing
**Solution:** 
1. Check requirements.txt syntax
2. Remove problematic packages
3. Check Vercel build logs

### Issue: Frontend Can't Connect to Backend
**Solution:**
1. Verify API_BASE_URL is correct
2. Check CORS is enabled on backend
3. Verify frontend .env.local has correct URL
4. Check network tab in browser DevTools

---

## FILE CHECKLIST FOR GITHUB

Before pushing, ensure these files exist:

```
✅ Backend Files:
  ├── main.py
  ├── QueryProcessor.py
  ├── embedder.py
  ├── vectorstore.py
  ├── file_processor.py
  ├── file_manager.py
  ├── pdfreader.py
  ├── chunker.py
  ├── llm.py
  ├── dataprocessor.py
  ├── image_processor.py
  ├── audio_processor.py
  ├── video_processor.py
  ├── multimodal_dataprocessor.py
  ├── requirements.txt
  ├── .env (with REAL keys - DON'T commit)
  ├── .env.example (with dummy values - DO commit)
  ├── vercel.json
  ├── .vercelignore
  └── api/index.py

✅ Frontend Files:
  ├── frontend/src/App.js
  ├── frontend/src/ChatInterface.js
  ├── frontend/src/AdminDashboard.js
  ├── frontend/package.json
  ├── frontend/.env.local (with API endpoint)
  ├── frontend/.env.example
  └── frontend/public/index.html

✅ Configuration:
  ├── .gitignore (to exclude .env, __pycache__)
  └── README.md (with deployment instructions)
```

---

## QUICK COMMAND REFERENCE

### Push Backend to GitHub
```powershell
cd C:\Startup\GenAISample\RAG_HR_ASSISTANT
git add .
git commit -m "Production ready: Multimodal RAG + Vercel config"
git push origin main
```

### Update Frontend Endpoint
```bash
# In frontend/.env.local
REACT_APP_API_URL=https://your-project.vercel.app
```

### Redeploy After Changes
```bash
# Backend
git push origin main  # Vercel auto-deploys

# Frontend  
npm run build
git push origin main  # Vercel auto-deploys
```

---

## FINAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│          GitHub Repository                          │
│  (github.com/YOUR_USERNAME/RAG_HR_ASSISTANT)       │
│  ├── Backend (Python/FastAPI)                       │
│  ├── Frontend (React)                               │
│  └── Configuration files                            │
└─────────────────────────────────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
   ┌─────────────┐          ┌──────────────┐
   │  Vercel     │          │  Vercel      │
   │  Backend    │          │  Frontend    │
   │  (Python)   │          │  (React)     │
   └──────┬──────┘          └────────┬─────┘
          │                          │
API:      │                          │
https://  │                          │
your-     │                    Frontend URL:
project.  │                    https://
vercel.   │                    your-frontend.
app       │                    vercel.app
          │                          │
          └──────────────┬───────────┘
                         │
                    Browser Request
                    (User Interface)
```

---

## NEXT STEPS

1. ✅ **Push Backend to GitHub**
   ```bash
   git add .
   git commit -m "Initial commit"
   git push -u origin main
   ```

2. ✅ **Deploy Backend to Vercel**
   - Visit vercel.com
   - Import GitHub repository
   - Add environment variables
   - Deploy

3. ✅ **Get API Endpoint**
   - From Vercel dashboard
   - Example: https://rag-hr-assistant.vercel.app

4. ✅ **Update Frontend .env**
   - Add REACT_APP_API_URL=https://your-endpoint.vercel.app

5. ✅ **Deploy Frontend**
   - Push frontend code to GitHub
   - Deploy to Vercel

6. ✅ **Test End-to-End**
   - Visit https://your-frontend.vercel.app
   - Upload files
   - Query the system
   - Verify responses

---

## 🎉 DEPLOYMENT COMPLETE!

Your system will be:
- **Backend:** Cloud-hosted on Vercel (serverless)
- **Frontend:** Cloud-hosted on Vercel (static)
- **Database:** Pinecone (already cloud-based)
- **LLM:** OpenAI (already cloud-based)

**Full end-to-end cloud deployment! 🚀**
