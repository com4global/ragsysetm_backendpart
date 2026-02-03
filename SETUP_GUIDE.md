# HR Assistant RAG Chat Interface

A user-friendly chat interface for the HR Assistant RAG system with FastAPI backend and React frontend.

## Architecture

- **Backend**: FastAPI (Python) - Handles RAG queries
- **Frontend**: React.js - Chat interface
- **Vector DB**: Pinecone
- **LLM**: OpenAI

## Setup Instructions

### 1. Backend Setup (FastAPI)

```bash
# Install additional dependencies
pip install -r requirements.txt

# Run the FastAPI server
python main.py
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 2. Frontend Setup (React)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start the development server
npm start
```

The React app will open at `http://localhost:3000`

## How It Works

1. **User Input**: User types a query in the chat interface
2. **API Call**: React frontend sends the query to FastAPI backend via POST request
3. **RAG Pipeline**: 
   - Query is embedded using OpenAI embeddings
   - Vectors are searched in Pinecone
   - Matching chunks are retrieved
   - Query + context sent to LLM for response generation
4. **Response**: Generated response displayed in chat UI

## API Endpoints

### POST /chat
Send a user query and get a response

**Request:**
```json
{
  "query": "What is the work timing policy?"
}
```

**Response:**
```json
{
  "response": "The standard working hours are...",
  "query": "What is the work timing policy?"
}
```

### GET /
Health check endpoint

## Usage

1. Start the backend: `python main.py`
2. In another terminal, start frontend: `cd frontend && npm start`
3. Open chat interface and type your query
4. Get AI-powered responses based on company HR policies

## Features

- 💬 Real-time chat interface
- 🤖 AI-powered responses using RAG
- 📚 Context-aware answers from vector database
- 🎨 Modern, responsive UI
- ⚡ Fast response times
- 🔄 Async API calls

## Sample Queries

- "What is the work timing policy?"
- "How many days of leave am I entitled to?"
- "What is the salary payment schedule?"
- "What is the separation process?"
- "Tell me about overtime policies"

## Environment Variables

Make sure you have `.env` file set up with:
```
OPENAI_API_KEY=your_key_here
PINECONE_API_KEY=your_key_here
PINECONE_INDEX_NAME=hr-assistant-index
```

## Troubleshooting

- **Backend not responding**: Make sure FastAPI is running on port 8000
- **CORS errors**: Check that CORS middleware is enabled in main.py
- **Empty responses**: Verify Pinecone has embeddings stored (check vector count)
- **OpenAI errors**: Check API key and quota

## Development Notes

- Backend runs on: `http://localhost:8000`
- Frontend runs on: `http://localhost:3000`
- Modify `ChatInterface.js` for UI customization
- Modify `main.py` for backend logic changes
