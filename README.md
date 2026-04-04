# Enterprise RAG Chatbot

This project is a local Retrieval-Augmented Generation (RAG) chatbot with:

- a FastAPI backend for document upload, indexing, retrieval, and response streaming
- a Next.js frontend for uploading files and asking questions
- Ollama as the local LLM runtime
- ChromaDB for persistent vector storage

## Project Structure

- `backend/` FastAPI app, document parsing, embeddings, reranking, and Chroma storage
- `frontend/my-app/` Next.js UI
- `backend/uploads/` uploaded files
- `backend/chroma_data/` persistent vector database
- `backend/metadata.db` SQLite metadata store

## Prerequisites

Install these before running the app:

- Python 3.10 or newer
- Node.js 18 or newer
- Ollama

## 1. Start Ollama

Install Ollama, then pull the model used by the backend:

```powershell
ollama pull llama3
```

Start Ollama if it is not already running:

```powershell
ollama serve
```

The backend streams responses from:

```text
http://localhost:11434/api/generate
```

## 2. Run the Backend

Open a terminal in the project root:

```powershell
cd C:\Users\User\Desktop\enterprise-rag-chatbot
```

If you want to use the existing virtual environment in this repo:

```powershell
.\backend\venv\Scripts\Activate.ps1
```

If you need to install dependencies manually:

```powershell
pip install -r .\backend\requirement.txt
```

Start the FastAPI server:

```powershell
cd .\backend
uvicorn main:app --reload
```

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

## 3. Run the Frontend

Open a second terminal:

```powershell
cd C:\Users\User\Desktop\enterprise-rag-chatbot\frontend\my-app
```

Install frontend dependencies if needed:

```powershell
npm install
```

Optional: create `.env.local` if you want to point the frontend to a custom backend URL.

```env
BACKEND_API_BASE_URL=http://127.0.0.1:8000
```

Start the frontend:

```powershell
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## 4. How to Use the App

1. Open `http://localhost:3000`
2. Upload a `.pdf`, `.xlsx`, or `.xls` file
3. Wait for the file to finish indexing
4. Ask a question about the uploaded content

The backend supports these main endpoints:

- `POST /upload/` upload a document
- `GET /status/{filename}` check indexing status
- `GET /documents/` list uploaded documents
- `POST /query/?question=...` ask a question

## 5. Quick Backend Test Without Frontend

Upload a file from PowerShell:

```powershell
curl.exe -X POST http://127.0.0.1:8000/upload/ -F "file=@C:\path\to\your\file.pdf"
```

Ask a question:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/query/?question=Summarize%20this%20document"
```

Check document status:

```powershell
curl.exe http://127.0.0.1:8000/status/yourfile.pdf
```

## Notes

- The backend stores embeddings and metadata locally, so uploads remain available between restarts.
- Uploading a file with the same name re-indexes it and replaces old stored chunks for that filename.
- If responses fail, first confirm Ollama is running and that `llama3` is installed.
- If the frontend cannot reach the backend, confirm `BACKEND_API_BASE_URL` points to `http://127.0.0.1:8000`.

## Common Problems

`ModuleNotFoundError`

- Activate the backend virtual environment or reinstall dependencies with `pip install -r .\backend\requirement.txt`.

`Cannot reach backend at http://127.0.0.1:8000`

- Make sure `uvicorn main:app --reload` is running in `backend/`.

`The local LLM service is unavailable right now`

- Start Ollama with `ollama serve`.
- Pull the required model with `ollama pull llama3`.

`No indexed document found`

- Upload a supported file and wait until indexing completes.
