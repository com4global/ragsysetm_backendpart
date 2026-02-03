# HR Assistant - RAG Powered Chat Interface

A modern, user-friendly chat interface for querying company HR policies using Retrieval-Augmented Generation (RAG) with FastAPI backend and React.js frontend.

## 🎯 Features

- ✅ **RAG Pipeline**: Query embeddings searched against Pinecone vector database
- ✅ **AI-Powered Responses**: OpenAI LLM generates contextual answers
- ✅ **Modern Chat UI**: Real-time messaging interface with React
- ✅ **FastAPI Backend**: High-performance RESTful API
- ✅ **CORS Enabled**: Easy frontend-backend integration
- ✅ **Loading States**: Visual feedback during query processing
- ✅ **Responsive Design**: Works on desktop and mobile
- ✅ **Error Handling**: Graceful error messages

## 📋 Prerequisites

- Python 3.8+
- Node.js 14+ and npm
- Active OpenAI API key with available credits
- Pinecone account with vector index
- HR Policy PDF (in `resources/HRPolicy.pdf`)

## 🚀 Quick Start

### Option 1: Using Batch File (Windows)
```bash
start.bat
```
Choose option 3 to start both backend and frontend

### Option 2: Using PowerShell
```powershell
.\start.ps1
```

### Option 3: Manual Setup

**Terminal 1 - Backend:**
```bash
# Activate virtual environment
.\.myenv\Scripts\Activate.ps1

# Start FastAPI server
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm install
npm start
```

## 📍 Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **API ReDoc**: http://localhost:8000/redoc

## 🏗️ Project Structure

```
RAG_HR_ASSISTANT/
├── backend files (Python)
│   ├── main.py              # FastAPI server
│   ├── QueryProcessor.py    # RAG query processor
│   ├── embedder.py          # Query embeddings
│   ├── vectorstore.py       # Pinecone integration
│   ├── llm.py               # OpenAI integration
│   ├── pdfreader.py         # PDF extraction
│   ├── chunker.py           # Text chunking
│   └── requirements.txt      # Python dependencies
│
├── frontend/                # React application
│   ├── public/
│   │   └── index.html       # Entry HTML
│   ├── src/
│   │   ├── ChatInterface.js # Chat component
│   │   ├── ChatInterface.css# Chat styles
│   │   ├── App.js           # Main app component
│   │   ├── App.css          # App styles
│   │   └── index.js         # React entry point
│   └── package.json         # NPM dependencies
│
├── resources/               # Data files
│   └── HRPolicy.pdf        # HR policy document
│
├── start.bat               # Windows batch launcher
├── start.ps1               # PowerShell launcher
├── SETUP_GUIDE.md          # Detailed setup guide
└── README.md               # This file
```

## 💻 How It Works

### Query Flow
```
User Query (React UI)
    ↓
FastAPI /chat endpoint
    ↓
embed_user_query() - OpenAI embeddings
    ↓
search_in_pinecone() - Vector search
    ↓
query_llm_with_context() - OpenAI generates response
    ↓
Response displayed in Chat (React UI)
```

### Data Pipeline (One-time)
```
HRPolicy.pdf
    ↓
read_pdf() - Extract text
    ↓
chunk_pages() - Split into chunks
    ↓
embed_chunks() - OpenAI embeddings
    ↓
store_in_pinecone() - Store in vector DB
```

## 🔧 Installation

### Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd frontend
npm install
```

## ⚙️ Configuration

### Environment Variables (.env)
```env
OPENAI_API_KEY=sk-proj-your_key_here
PINECONE_API_KEY=pcsk_your_key_here
PINECONE_INDEX_NAME=hr-assistant-index
```

### Backend (main.py)
- Port: 8000
- CORS: Enabled for all origins (restrict in production)

### Frontend (package.json)
- Port: 3000
- API Base URL: http://localhost:8000

## 🧪 Testing

### Test Backend API
```bash
# Using curl
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the work timing policy?"}'

# Using Python
import requests
response = requests.post(
    "http://localhost:8000/chat",
    json={"query": "What is the work timing policy?"}
)
print(response.json())
```

### Test Frontend
1. Open http://localhost:3000
2. Type a query like "What is the work timing policy?"
3. Click Send
4. Wait for response

## 📚 Sample Queries

- "What is the work timing policy?"
- "How many days of leave am I entitled to?"
- "What is the salary payment schedule?"
- "Tell me about the separation process"
- "What are overtime compensation rules?"
- "What is the casual leave policy?"
- "How are salaries processed?"

## 🛠️ Troubleshooting

### Backend Won't Start
```bash
# Check Python version
python --version  # Should be 3.8+

# Check virtual environment
.\.myenv\Scripts\python.exe --version

# Check FastAPI installation
pip show fastapi
```

### Frontend Won't Start
```bash
# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -r node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 14+
```

### Connection Issues
- **CORS Error**: Verify CORS middleware in main.py
- **Port Already in Use**: Kill process on port 8000 or 3000
- **API Not Responding**: Check FastAPI logs for errors

### Query Issues
- **No Response**: Check Pinecone vector count (should be > 0)
- **Rate Limit Error**: Check OpenAI quota and billing
- **Empty Vectors**: Re-run dataprocessor.py to re-embed

## 📦 Dependencies

### Python (Backend)
- fastapi: Web framework
- uvicorn: ASGI server
- openai: LLM API
- pinecone: Vector database
- pypdf: PDF reading
- python-dotenv: Environment variables

### JavaScript (Frontend)
- react: UI library
- react-dom: React rendering
- axios: HTTP client

## 🔐 Security Notes

### Development
- CORS is open to all origins
- No authentication required

### Production
- Restrict CORS to specific frontend URL
- Add API key authentication
- Use HTTPS only
- Set rate limiting
- Sanitize user inputs

## 📖 API Reference

### POST /chat
**Request:**
```json
{
  "query": "What is the work timing policy?"
}
```

**Response:**
```json
{
  "response": "The standard working hours are from Monday to Friday, 9:00 AM to 6:00 PM...",
  "query": "What is the work timing policy?"
}
```

**Status Codes:**
- 200: Success
- 400: Invalid request
- 500: Server error

### GET /
**Response:**
```json
{
  "message": "HR Assistant RAG API is running"
}
```

## 🐛 Known Issues

- Initial query may take longer (LLM cold start)
- Long responses may not fit in single message bubble
- Scrolling on very long conversations can be slow

## 🚀 Future Enhancements

- [ ] User authentication
- [ ] Query history/saved conversations
- [ ] PDF upload functionality
- [ ] Multi-language support
- [ ] Voice input/output
- [ ] Export conversations
- [ ] Admin dashboard for policy management
- [ ] Analytics and usage tracking

## 📝 License

This project is part of an HR Assistant system.

## 🤝 Support

For issues or questions:
1. Check SETUP_GUIDE.md
2. Review API documentation at http://localhost:8000/docs
3. Check FastAPI and React logs

## 📞 Contact

For more information about setup and deployment, see SETUP_GUIDE.md

---

**Made with ❤️ for Better HR Management**
