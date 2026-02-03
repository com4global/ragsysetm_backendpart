# 📋 STEP-BY-STEP DEPLOYMENT INSTRUCTIONS

## 🎯 YOUR DEPLOYMENT PATH

1. **Push Backend to GitHub** ← Start here
2. **Deploy Backend to Vercel** 
3. **Get Cloud Endpoint URL**
4. **Update Frontend with Cloud URL**
5. **Deploy Frontend to Vercel**
6. **Test End-to-End**

---

## ✅ STEP 1: PUSH BACKEND TO GITHUB (10 minutes)

### 1.1 Open PowerShell and Navigate to Project
```powershell
cd C:\Startup\GenAISample\RAG_HR_ASSISTANT
```

### 1.2 Initialize Git Repository (if not already done)
```powershell
git init
```

### 1.3 Configure Git (First Time Only)
```powershell
git config --global user.name "Your Name"
git config --global user.email "your.email@gmail.com"
```

### 1.4 Verify Files to Commit
```powershell
git status
```

Expected: ~100+ files to be staged

### 1.5 Add All Files
```powershell
git add .
```

### 1.6 Create Initial Commit
```powershell
git commit -m "Initial commit: Multimodal RAG HR Assistant with Image, Audio, Video support - Backend with FastAPI, Vector DB integration, and Vercel deployment ready"
```

### 1.7 Rename Branch to Main
```powershell
git branch -M main
```

### 1.8 Add GitHub Remote (Replace with YOUR repo URL)

**First, create a repository on GitHub:**
1. Go to https://github.com/new
2. Repository name: `RAG_HR_ASSISTANT`
3. Description: "Multimodal RAG System for HR Assistant"
4. Make it **Public** (for easier access)
5. Click "Create repository"

**Then run this command:**
```powershell
git remote add origin https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT.git
```

Replace `YOUR_USERNAME` with your actual GitHub username!

### 1.9 Push to GitHub
```powershell
git push -u origin main
```

🎉 **Expected Success Message:**
```
Enumerating objects: 150, done.
Counting objects: 100% (150/150)
Delta compression using up to 8 threads
Compressing objects: 100%
Writing objects: 100%
Creating deltas: 100%

To https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT.git
 * [new branch]      main -> main
Branch 'main' set up to track remote branch 'main' from 'origin'.
```

**Verify on GitHub:**
- Visit: https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT
- You should see all your files!

---

## ✅ STEP 2: DEPLOY BACKEND TO VERCEL (15 minutes)

### 2.1 Create Vercel Account
1. Go to https://vercel.com
2. Click "Sign Up"
3. Select "GitHub"
4. Authorize Vercel to access your GitHub account

### 2.2 Import Project into Vercel
1. Click "New Project"
2. Search for: `RAG_HR_ASSISTANT`
3. Click "Import"

### 2.3 Configure Project Settings
- **Project Name:** `rag-hr-assistant` (auto-filled, you can customize)
- **Root Directory:** `.` (default)
- **Framework Preset:** Other (Python)
- **Build Command:** `pip install -r requirements.txt`
- **Output Directory:** (leave empty)

### 2.4 Add Environment Variables

Click "Environment Variables" and add these THREE variables:

**Variable 1:**
```
Name: OPENAI_API_KEY
Value: sk-proj-XXXXXXXXXXXXX (your real OpenAI key)
```

**Variable 2:**
```
Name: PINECONE_API_KEY
Value: pcaXXXXXXXXXXXXX (your real Pinecone key)
```

**Variable 3:**
```
Name: PINECONE_INDEX_NAME
Value: hr-assistant-index
```

⚠️ **IMPORTANT:** Use the SAME keys as your local `.env` file!

### 2.5 Deploy
1. Click "Deploy"
2. Wait for deployment (2-5 minutes)
3. See deployment log

🎉 **Success!** You'll see a URL like:
```
rag-hr-assistant.vercel.app
```

### 2.6 Copy Your Backend URL
Write down (or copy) your URL:
```
https://rag-hr-assistant.vercel.app
```

### 2.7 Test Backend Endpoint
Open browser and visit:
```
https://rag-hr-assistant.vercel.app/docs
```

You should see **Swagger UI** with all your API endpoints! ✅

---

## ✅ STEP 3: UPDATE FRONTEND WITH CLOUD ENDPOINT (10 minutes)

### 3.1 Create Frontend Environment File
Go to your frontend directory:
```powershell
cd frontend
```

### 3.2 Create `.env.local` File
Create a new file: `frontend/.env.local`

Add this single line (replace with YOUR Vercel backend URL):
```
REACT_APP_API_URL=https://rag-hr-assistant.vercel.app
```

### 3.3 Verify Frontend Code

**File: `frontend/src/ChatInterface.js`**

Find this line:
```javascript
const API_URL = "http://127.0.0.1:8000"
```

Replace with:
```javascript
const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000"
```

**File: `frontend/src/AdminDashboard.js`**

Find:
```javascript
const API_BASE = "http://127.0.0.1:8000"
```

Replace with:
```javascript
const API_BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000"
```

### 3.4 Test Locally (Optional)
```powershell
npm start
```

Visit http://localhost:3000 and test chat functionality.

---

## ✅ STEP 4: PUSH FRONTEND TO GITHUB (5 minutes)

### 4.1 Navigate to Frontend Directory
```powershell
cd frontend
git add .
git commit -m "Frontend with cloud API integration"
git push origin main
```

---

## ✅ STEP 5: DEPLOY FRONTEND TO VERCEL (10 minutes)

### 5.1 Create New Vercel Project for Frontend
1. Go to https://vercel.com/dashboard
2. Click "New Project"
3. Search for and import the same `RAG_HR_ASSISTANT` repo
4. **Important:** Select "frontend" as root directory in settings
   - Click "Edit" in Root Directory
   - Type: `frontend`
   - Save

### 5.2 Add Environment Variable
Add the same `.env` variable in Vercel project settings:
```
REACT_APP_API_URL=https://rag-hr-assistant.vercel.app
```

### 5.3 Deploy Frontend
1. Click "Deploy"
2. Wait for deployment

🎉 **Success!** You'll get a frontend URL like:
```
rag-hr-assistant-frontend.vercel.app
```

---

## ✅ STEP 6: END-TO-END TESTING

### 6.1 Test Backend API
Open in browser:
```
https://rag-hr-assistant.vercel.app/docs
```

Try POST `/chat` with:
```json
{
  "query": "What is the HR policy?"
}
```

Should return an answer! ✅

### 6.2 Test Frontend
Open in browser:
```
https://rag-hr-assistant-frontend.vercel.app
```

1. Try uploading a PDF
2. Try asking a question in chat
3. Verify response comes back

Should work end-to-end! ✅

### 6.3 Check Network Requests
In browser, open DevTools (F12):
1. Go to "Network" tab
2. Try sending a chat message
3. Verify API calls go to your Vercel backend URL
4. Verify responses are received

---

## 🚨 TROUBLESHOOTING

### Issue: "502 Bad Gateway" or "Function Error"
**Solution:**
1. Go to Vercel Dashboard → Your Backend Project
2. Click "Deployments" → Latest deployment
3. Scroll down to "Function Logs"
4. Read the error message
5. Common causes:
   - Missing environment variable
   - Python dependency not installed
   - Import error in main.py

### Issue: Frontend Can't Connect to Backend
**Solution:**
1. Check that `.env.local` in frontend has correct backend URL
2. Verify backend is running (test /docs endpoint)
3. Check CORS is enabled in main.py
4. Open browser DevTools → Network → see actual error

### Issue: Environment Variables Not Working
**Solution:**
1. Verify variables are added in Vercel dashboard
2. **Redeploy** after adding variables (critical!)
3. Check variable names match exactly (case-sensitive)
4. Don't include `=` in variable name

### Issue: Build Fails
**Solution:**
1. Check requirements.txt for syntax errors
2. Remove any problematic packages
3. Check Python version compatibility
4. Look at Vercel build logs for specific error

---

## 📋 FINAL VERIFICATION CHECKLIST

After deployment, verify:

- [ ] Backend URL works: `https://your-backend.vercel.app/docs`
- [ ] Can see Swagger UI with all endpoints
- [ ] Frontend URL works: `https://your-frontend.vercel.app`
- [ ] Can upload files via frontend
- [ ] Can send chat messages
- [ ] Responses are received
- [ ] No console errors in browser DevTools
- [ ] Network requests go to correct backend URL

---

## 📊 YOUR FINAL DEPLOYMENT

```
┌─────────────────────────────────┐
│  Your Local Machine             │
│  (Development)                  │
│  • Backend: :8000               │
│  • Frontend: :3000              │
└──────────────────┬──────────────┘
                   │
              git push
                   │
        ┌──────────▼──────────┐
        │  GitHub Repository  │
        │  (Version Control)  │
        └──────┬──────────────┘
               │
          ┌────┴─────┐
          │           │
          ▼           ▼
    ┌──────────┐  ┌──────────────┐
    │ Vercel   │  │ Vercel       │
    │ Backend  │  │ Frontend     │
    │ Cloud    │  │ Cloud        │
    └────┬─────┘  └────┬─────────┘
         │             │
    https://        https://
    your-backend    your-frontend
    .vercel.app     .vercel.app
         │             │
         └─────┬───────┘
               │
        Browser/Users
        (Production Access)
```

---

## 🎉 SUCCESS!

Your system is now:
✅ Pushed to GitHub (version control)
✅ Backend deployed on Vercel (cloud API)
✅ Frontend deployed on Vercel (cloud UI)
✅ Accessible worldwide 24/7
✅ Using cloud Pinecone DB
✅ Using cloud OpenAI API

**You now have a fully cloud-hosted RAG system!** 🚀

---

## 💡 QUICK REFERENCE URLS

After deployment, you'll have:

| Service | URL |
|---------|-----|
| **Backend API** | https://rag-hr-assistant.vercel.app |
| **API Docs** | https://rag-hr-assistant.vercel.app/docs |
| **Frontend** | https://rag-hr-assistant-frontend.vercel.app |
| **GitHub** | https://github.com/YOUR_USERNAME/RAG_HR_ASSISTANT |

---

## 📞 NEXT SUPPORT

If you encounter issues:
1. Check "TROUBLESHOOTING" section above
2. Look at Vercel build/function logs
3. Check browser console (F12)
4. Review GITHUB_VERCEL_DEPLOYMENT_GUIDE.md

**Congratulations on your cloud deployment! 🎊**
