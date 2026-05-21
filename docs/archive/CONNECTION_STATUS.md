# Frontend to Backend Connection - Setup Complete

## Services Status

### ✅ Frontend (React + Vite)
- **URL**: http://localhost:8080
- **Status**: Running
- **Port**: 8080
- **Framework**: React + TypeScript + TailwindCSS
- **UI Components**: shadcn/ui

### ✅ Upload Service (Backend)
- **URL**: http://localhost:8001
- **Status**: Running
- **Port**: 8001
- **API Docs**: http://localhost:8001/docs (Swagger UI)
- **Endpoints**:
  - `POST /upload` - Upload a document
  - `GET /documents` - List all documents
  - `DELETE /documents/{id}` - Delete a document

### ⚠️ Query Service (Backend)
- **URL**: http://localhost:8002
- **Status**: Initialized but requires OpenAI API key
- **Port**: 8002
- **Endpoints**:
  - `POST /query` - Query documents with AI
  - `GET /metrics` - Get query metrics
  - `GET /health` - Health check

## Frontend Setup

### Environment Configuration
Created `.env.local` in `frontend/` directory:
```
VITE_API_URL=http://localhost:8001
VITE_QUERY_API_URL=http://localhost:8002
```

### API Integration
Created `src/lib/api.ts` with:
- **uploadAPI.uploadDocument()** - Upload files to backend
- **queryAPI.queryDocuments()** - Query documents with AI
- **queryAPI.getMetrics()** - Fetch analytics
- **queryAPI.healthCheck()** - Check service status

### Components Updated
- **UploadZone.tsx** - Integrated with backend upload API
  - Real file upload to backend
  - Error handling
  - Progress tracking
  - Success feedback

## How to Use

### 1. Access the Frontend
Open your browser and go to:
```
http://localhost:8080
```

### 2. Upload a Document
1. Navigate to the Upload page (default)
2. Drag and drop a file (PDF, DOCX, TXT)
3. Add a title
4. Click "Upload Document"
5. The file will be sent to the backend upload service on port 8001

### 3. Query Documents
1. Click "Query" in the navigation
2. Enter your question
3. The query service (port 8002) will search uploaded documents
4. **Note**: Requires OpenAI API key to be configured in `backend/.env`

## Testing the Connection

### Test Upload API
```bash
curl -X POST http://localhost:8001/upload \
  -F "file=@sample.txt" \
  -F "title=Company Policy"
```

### Test Query API
```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the leave policy?"}'
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (8080)                        │
│  React + TypeScript + TailwindCSS + shadcn/ui              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Upload Page                                          │  │
│  │ - UploadZone (integrated with API)                   │  │
│  │ - DocumentList (shows uploaded files)                │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Query Page                                           │  │
│  │ - Search interface                                   │  │
│  │ - Results display with citations                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                  │
└─────────────────────────────────────────────────────────────┘
         │                          │
         │                          │
         ▼                          ▼
┌──────────────────────┐  ┌──────────────────────┐
│ Upload Service (8001)│  │ Query Service (8002) │
│                      │  │                      │
│ - PDF processing     │  │ - Vector search     │
│ - Chunk storage      │  │ - AI responses      │
│ - PostgreSQL         │  │ - Metrics           │
│ - Qdrant vectors     │  │ - OpenAI API        │
└──────────────────────┘  └──────────────────────┘
         │                          │
         └──────────┬───────────────┘
                    │
         ┌──────────▼──────────┐
         │  Docker Containers  │
         │                     │
         │ - PostgreSQL (5432) │
         │ - Qdrant (6333)     │
         │ - Redis (6379)      │
         └─────────────────────┘
```

## Next Steps

### To enable Query Service fully:
1. Get an OpenAI API key from https://platform.openai.com
2. Add it to `backend/.env`:
   ```
   OPENAI_API_KEY=<your-openrouter-api-key>
   ```
3. Restart the query service

### To test the full workflow:
1. Upload a document via the frontend
2. Query the document using the AI search feature
3. View analytics on the Dashboard page

## Troubleshooting

### Frontend not connecting to backend?
- Check that upload service is running: `http://localhost:8001/docs`
- Check browser console for CORS errors
- Verify `.env.local` has correct API URLs

### Upload service not responding?
- Ensure Docker containers are running: `docker ps`
- Check service logs: Terminal showing port 8001

### Query service keeps crashing?
- Add OpenAI API key to `backend/.env`
- Restart the query service

---

**Setup completed!** Your frontend is now connected to your backend services. 🎉
