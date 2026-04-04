# Project Explanation

## What This Project Is

This is a local enterprise-style RAG chatbot. It lets a user:

- upload PDF and Excel files
- convert those files into searchable text chunks
- store those chunks in a persistent vector database
- ask questions against the uploaded knowledge base
- stream answers back into a chat UI

The app is designed to run fully on a local machine with a local LLM served by Ollama.

## High-Level Architecture

The project has two main applications:

- `backend/`: FastAPI service that handles upload, parsing, indexing, retrieval, reranking, metadata tracking, and LLM response streaming
- `frontend/my-app/`: Next.js app that provides the UI and acts as a lightweight proxy to the backend API

There are also three important storage areas:

- `backend/uploads/`: keeps the original uploaded files
- `backend/chroma_data/`: stores vector embeddings and chunk documents in ChromaDB
- `backend/metadata.db`: SQLite database that stores document metadata such as filename, status, upload time, and chunk count

## Main Technologies Used

### Frontend

- Next.js 16 with App Router
- React 19
- TypeScript
- Tailwind CSS 4

### Backend

- FastAPI
- Uvicorn
- SQLAlchemy
- Requests
- NumPy

### AI / RAG Stack

- Ollama for local LLM serving
- `llama3` as the configured generation model
- `sentence-transformers/all-MiniLM-L6-v2` for embeddings
- `cross-encoder/ms-marco-MiniLM-L-6-v2` for reranking
- ChromaDB for persistent vector search

### Document Processing

- PyMuPDF for PDF text extraction
- Pandas + OpenPyXL for Excel parsing

## End-to-End Flow

The request flow looks like this:

1. The user opens the Next.js UI.
2. The user uploads a PDF or Excel file.
3. The frontend sends the file to a Next.js API route.
4. The Next.js API route forwards the file to FastAPI.
5. FastAPI saves the file and starts a background indexing task.
6. The backend extracts text, chunks it, embeds it, and stores it in ChromaDB.
7. Metadata such as status and chunk count is stored in SQLite.
8. The user asks a question in the chat UI.
9. The frontend sends that question to a Next.js query route.
10. The query route forwards it to FastAPI.
11. FastAPI embeds the question, retrieves similar chunks from ChromaDB, reranks them, builds context, and sends the prompt to Ollama.
12. Ollama streams the answer back through FastAPI, then through Next.js, and finally into the chat interface.

## Frontend Flow

The main UI lives in `frontend/my-app/app/page.tsx`.

It manages:

- chat messages
- document list
- selected single-document scope
- upload state
- delete state
- streaming answer updates

### Frontend API Routes

The frontend does not directly call FastAPI from the browser. Instead, it uses internal Next.js routes:

- `app/api/upload/route.ts`
- `app/api/query/route.ts`
- `app/api/documents/route.ts`
- `app/api/documents/[filename]/route.ts`

These routes forward requests to the backend URL:

- `BACKEND_API_BASE_URL`
- fallback: `NEXT_PUBLIC_API_BASE_URL`
- default: `http://127.0.0.1:8000`

This setup keeps the browser code simple and gives one place to manage backend connection behavior.

## Backend Flow

The FastAPI app lives in `backend/main.py`.

### Main Backend Responsibilities

- accept uploads
- validate file types
- save files locally
- launch background indexing
- expose status and document list APIs
- delete documents from all storage layers
- answer questions using retrieval + reranking + generation

### Backend Endpoints

- `GET /`
  - health-style root message
- `POST /upload/`
  - uploads a file and starts background indexing
- `GET /status/{filename}`
  - checks indexing status
- `GET /documents/`
  - lists uploaded documents
- `DELETE /documents/{filename}`
  - removes file, vectors, and metadata
- `POST /query/`
  - retrieves context and streams an answer

## Upload and Indexing Pipeline

When a user uploads a file:

1. FastAPI validates the filename and extension.
2. The file is saved into `backend/uploads/`.
3. A background task runs `index_file_task`.
4. SQLite marks the document as `processing`.
5. The backend extracts raw text depending on file type.
6. The text is split into overlapping chunks.
7. Existing chunks for the same filename are deleted from ChromaDB.
8. New embeddings are generated for every chunk.
9. Chunks and embeddings are stored in ChromaDB with filename metadata.
10. SQLite updates the document status to `processed` and stores chunk count.

If indexing fails:

- Chroma entries for that file are removed
- chunk count is reset to `0`
- status becomes `error`

## File Parsing Logic

### PDF Parsing

`backend/ingestion/pdf_parser.py` uses PyMuPDF.

Behavior:

- opens the PDF
- loops through each page
- extracts page text
- adds page separators like `--- Page N ---`

This helps preserve some structure before chunking.

### Excel Parsing

`backend/ingestion/excel_parser.py` uses Pandas.

Behavior:

- opens the workbook
- loops through each sheet
- converts each sheet into CSV text
- adds sheet separators like `--- Sheet: name ---`

This is useful because row and column relationships stay readable in plain text, which improves retrieval for table-style questions.

## Chunking Strategy

Chunking is handled in `backend/processing/chunking.py`.

The logic uses character-based chunking with overlap.

Current settings:

- PDFs: `chunk_size=500`, `overlap=100`
- Excel files: `chunk_size=1400`, `overlap=250`

Why different sizes:

- PDFs usually contain prose, so smaller chunks help precision
- Excel files often contain tabular data, so larger chunks help preserve row groups and sheet structure

## Embeddings

Embeddings are created in `backend/processing/embeddings.py` using:

- `SentenceTransformer("all-MiniLM-L6-v2")`

This converts each chunk and each user question into dense numeric vectors so semantic search can happen.

## Vector Storage with ChromaDB

ChromaDB integration lives in `backend/processing/chroma_store.py`.

What it stores:

- chunk text as `documents`
- embedding vectors
- metadata, especially `filename`
- generated chunk IDs

Key operations:

- `index_chunks(...)`
- `search_chunks(...)`
- `delete_chunks_by_filename(...)`
- `get_collection_size()`

Persistence matters here: uploaded knowledge remains available across app restarts because ChromaDB writes to `backend/chroma_data/`.

## Metadata Tracking with SQLite

The database layer lives in:

- `backend/db/database.py`
- `backend/db/models.py`

The `Document` table stores:

- `filename`
- `upload_date`
- `chunks_count`
- `status`

This database is not the knowledge base itself. It is the document registry that helps the UI show whether a file is processing, ready, or failed.

## Query and Retrieval Pipeline

When the user asks a question:

1. FastAPI validates that the question is not empty.
2. It checks that ChromaDB has indexed data.
3. The question is embedded with the same embedding model.
4. The backend decides how many chunks to retrieve using `choose_retrieval_k(...)`.
5. It performs vector similarity search in ChromaDB.
6. If the user selected one file in the UI, retrieval is filtered by filename.
7. Retrieved chunks are reranked with a cross-encoder model.
8. Top reranked chunks are joined into one context block.
9. The context and question are sent to Ollama.
10. The model output is streamed back to the user.

## Broad vs Narrow Question Handling

`choose_retrieval_k(...)` in `backend/main.py` tries to detect broad queries such as:

- "all"
- "every"
- "complete"
- "entire"
- "list"
- student-list style prompts

If a question looks broad, the backend increases retrieval depth up to `20` chunks.

Otherwise it uses a smaller cap, up to `8` chunks.

This is a practical optimization so list-style questions have a better chance of seeing enough context.

## Reranking

Reranking happens in `backend/rag/reranker.py`.

Model used:

- `cross-encoder/ms-marco-MiniLM-L-6-v2`

Why reranking exists:

- vector search is fast and good at rough retrieval
- reranking is slower but better at ordering the best chunks for the exact question

So the project first retrieves candidate chunks from ChromaDB, then reranks them to improve answer quality before generation.

## Generation with Ollama

Generation is handled in `backend/rag/generator.py`.

The backend calls:

- `http://localhost:11434/api/generate`

with:

- model: `llama3`
- streaming enabled

The prompt instructs the model to:

- answer only from the provided context
- return all relevant rows/items for broad questions
- clearly say when information is missing

This is the final stage of the RAG pipeline:

- retrieve relevant context
- inject it into the prompt
- generate an answer grounded in that context

## Streaming Response Path

One nice part of this project is the streamed answer path.

Flow:

1. Ollama streams tokens.
2. FastAPI yields them through `StreamingResponse`.
3. The Next.js query route returns the stream as plain text.
4. The React page reads the stream with `response.body.getReader()`.
5. The UI appends incoming chunks to the current assistant message.

This gives the user a live answer instead of waiting for a full response at the end.

## Document Scope Feature

The UI lets the user choose:

- all processed documents
- one specific processed document

If one file is selected, its filename is sent with the question and used as a Chroma metadata filter during retrieval.

This is helpful when multiple uploaded documents might contain overlapping topics.

## Delete Flow

When a user removes a document:

1. The frontend calls the Next.js delete route.
2. The delete route forwards the request to FastAPI.
3. FastAPI deletes matching chunks from ChromaDB.
4. FastAPI removes the physical file from `backend/uploads/` if present.
5. FastAPI deletes the document metadata row from SQLite.

That keeps file storage, vector storage, and document registry in sync.

## Why This Counts as a RAG System

RAG means Retrieval-Augmented Generation.

This project does all core RAG steps:

- ingests source documents
- transforms them into chunks
- embeds them into vectors
- retrieves relevant chunks for a question
- reranks those chunks
- augments the LLM prompt with retrieved context
- generates a grounded answer

Without retrieval, the model would rely only on its pretrained knowledge. With RAG, it can answer from the uploaded files.

## Strengths of the Current Design

- fully local architecture
- persistent vector storage
- persistent document metadata
- support for both PDF and Excel inputs
- streaming responses
- optional single-document filtering
- lightweight but practical reranking stage
- background indexing after upload

## Current Limitations

Based on the current codebase, a few limitations are worth noting:

- no user authentication
- no multi-user isolation
- no citation UI showing which chunks were used
- chunking is simple character-based chunking, not semantic chunking
- retrieval is filename-filtered only, not tag- or collection-based
- status polling exists in the backend, but the current page mainly refreshes documents list manually after actions
- `backend/rag/retriever.py` and `backend/config.py` are currently empty
- frontend root `frontend/package.json` only includes `axios`, while the actual app is inside `frontend/my-app`

## Folder Guide

### `backend/`

- `main.py`: main API server and orchestration layer
- `ingestion/`: document parsing for PDF and Excel
- `processing/`: chunking, embeddings, and Chroma operations
- `rag/`: reranking and answer generation
- `db/`: SQLite model and session setup
- `uploads/`: original uploaded files
- `chroma_data/`: persistent vector store files

### `frontend/my-app/`

- `app/page.tsx`: main chat and document management UI
- `app/api/*`: proxy routes between browser and FastAPI
- `app/layout.tsx`, `app/globals.css`: application shell and styling

## Typical User Journey

1. Start Ollama.
2. Start FastAPI.
3. Start Next.js.
4. Open the frontend in the browser.
5. Upload a PDF or Excel file.
6. Wait for indexing to finish.
7. Ask a question.
8. Read the streamed answer.
9. Optionally narrow the scope to one document or remove old files.

## Summary

This project is a local document-question-answering system built around a clean RAG pipeline:

- Next.js handles the UI and browser-facing API routes
- FastAPI handles document ingestion and question answering
- PyMuPDF and Pandas extract text from uploaded documents
- Sentence Transformers creates embeddings
- ChromaDB stores searchable vectors
- a CrossEncoder reranks retrieved chunks
- Ollama streams the final grounded answer using `llama3`

In short, the system turns uploaded business documents into a searchable local knowledge base and wraps that in a chat interface.
