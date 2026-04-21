# Enterprise RAG Chatbot

This project is a local Retrieval-Augmented Generation chatbot with:

- a FastAPI backend for upload, indexing, retrieval, reranking, and streaming answers
- a Streamlit UI for document management and chat
- Ollama as the local LLM runtime
- ChromaDB for persistent vector storage

## What Changed

- The main UI now runs in `streamlit_app.py`
- The old `frontend/my-app` Next.js app is legacy and no longer required
- Document processing is faster because parsing and chunking are more structured, embedding runs in tuned batches, and retrieval uses tighter query-time limits

## Project Structure

- `backend/` FastAPI app, parsing, chunking, embeddings, reranking, and storage
- `streamlit_app.py` Streamlit chat UI
- `backend/uploads/` uploaded source files
- `backend/chroma_data/` persistent vector database
- `backend/metadata.db` SQLite metadata store

## Prerequisites

- Python 3.10 or newer
- Ollama

## 1. Start Ollama

```powershell
ollama pull llama3
ollama serve
```

Ollama should be reachable at `http://localhost:11434`.

## 2. Install Python Dependencies

From the repo root:

```powershell
cd C:\Users\User\Desktop\enterprise-rag-chatbot
.\backend\venv\Scripts\Activate.ps1
pip install -r .\backend\requirement.txt
```

## 3. Run the Backend

```powershell
cd .\backend
uvicorn main:app --reload
```

Backend URLs:

- API: `http://127.0.0.1:8000`
- Docs: `http://127.0.0.1:8000/docs`

## 4. Run the Streamlit UI

Open a second terminal in the repo root:

```powershell
cd C:\Users\User\Desktop\enterprise-rag-chatbot
.\backend\venv\Scripts\Activate.ps1
streamlit run .\streamlit_app.py
```

Streamlit URL:

- `http://localhost:8501`

Optional backend override:

```powershell
$env:RAG_API_BASE_URL="http://127.0.0.1:8000"
```

## 5. How To Use It

1. Open `http://localhost:8501`
2. Upload a `.pdf`, `.xlsx`, or `.xls` file
3. Wait until the document status becomes `processed`
4. Optionally scope answers to one processed file
5. Ask questions in the chat panel

Main backend endpoints:

- `POST /upload/`
- `GET /status/{filename}`
- `GET /documents/`
- `DELETE /documents/{filename}`
- `POST /query/?question=...`

## 6. Quick Backend Smoke Test

Upload a file:

```powershell
curl.exe -X POST http://127.0.0.1:8000/upload/ -F "file=@C:\path\to\your\file.pdf"
```

Check status:

```powershell
curl.exe http://127.0.0.1:8000/status/yourfile.pdf
```

Ask a question:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/query/?question=Summarize%20this%20document"
```

## Performance Notes

- PDF extraction now uses sorted text and joins pages once at the end
- Excel extraction keeps row structure while avoiding full CSV serialization overhead
- Chunking is structure-aware instead of pure fixed-width slicing
- Embeddings are generated in normalized batches for faster indexing and more stable retrieval
- Query scope is validated so the chatbot does not waste work on missing or still-processing files

## Troubleshooting

`ModuleNotFoundError`

- Activate the backend virtual environment or reinstall with `pip install -r .\backend\requirement.txt`

`Cannot reach backend at http://127.0.0.1:8000`

- Make sure `uvicorn main:app --reload` is running in `backend/`

`The local LLM service is unavailable right now`

- Make sure Ollama is running with `ollama serve`
- Confirm `llama3` is installed with `ollama pull llama3`

`No indexed document found for that scope`

- Wait for indexing to finish or switch the scope back to `All documents`
