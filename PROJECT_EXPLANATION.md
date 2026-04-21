# Project Explanation

## Overview

This repository is a local RAG chatbot for PDFs and Excel files. The app lets a user:

- upload documents
- index them into a persistent vector store
- ask grounded questions against the indexed content
- stream answers from a local Ollama model

The current architecture is:

- `backend/`: FastAPI service for ingestion, indexing, retrieval, reranking, and answer streaming
- `streamlit_app.py`: Streamlit UI for uploads, document management, and chat

The old `frontend/my-app` Next.js app is now legacy and is no longer part of the main flow.

## End-To-End Flow

1. The user opens the Streamlit UI.
2. The user uploads a PDF or Excel file.
3. Streamlit sends the file to FastAPI.
4. FastAPI stores the file and starts a background indexing task.
5. The backend extracts text, chunks it, creates embeddings, and stores the results in ChromaDB.
6. SQLite stores document metadata such as filename, status, upload time, and chunk count.
7. The user asks a question in the chat UI.
8. FastAPI embeds the question, retrieves relevant chunks, reranks them, and sends the context to Ollama.
9. Ollama streams the answer back through FastAPI to Streamlit.

## Backend Responsibilities

`backend/main.py` is the orchestration layer. It:

- accepts uploads
- validates file type and filename
- schedules indexing in the background
- exposes document status and listing endpoints
- deletes documents from all storage layers
- answers questions with retrieval, reranking, and streamed generation

Main API endpoints:

- `POST /upload/`
- `GET /status/{filename}`
- `GET /documents/`
- `DELETE /documents/{filename}`
- `POST /query/`

## Storage Layers

The project uses three local storage areas:

- `backend/uploads/`: original uploaded files
- `backend/chroma_data/`: persistent vector database
- `backend/metadata.db`: SQLite metadata database

The `Document` table stores:

- `filename`
- `upload_date`
- `chunks_count`
- `status`

## Parsing

### PDF Parsing

`backend/ingestion/pdf_parser.py` uses PyMuPDF.

Behavior:

- opens the PDF
- extracts sorted text per page
- skips empty pages
- preserves page markers like `--- Page N ---`
- joins the final text once at the end for better performance

### Excel Parsing

`backend/ingestion/excel_parser.py` uses Pandas with OpenPyXL.

Behavior:

- opens the workbook
- loops through each sheet
- converts rows into line-oriented text with `|` separators
- preserves headers and row boundaries
- adds sheet markers like `--- Sheet: name ---`

This keeps tables readable for retrieval while avoiding some of the overhead of writing whole sheets out as CSV strings.

## Chunking

Chunking lives in `backend/processing/chunking.py`.

The chunker now:

- normalizes whitespace
- splits content into paragraph-like sections first
- tries to split oversized sections near sentence boundaries
- carries overlap from the tail of the previous chunk

Current defaults:

- PDFs: `chunk_size=500`, `overlap=100`
- Excel: `chunk_size=1400`, `overlap=250`

This is more retrieval-friendly than the original pure fixed-character slicing.

## Embeddings And Retrieval

Embeddings are created in `backend/processing/embeddings.py` using:

- `SentenceTransformer("all-MiniLM-L6-v2")`

Performance improvements:

- chunk embeddings run in batches
- embeddings are normalized before storage and querying
- the query embedding path is separated from the chunk embedding path

ChromaDB integration lives in `backend/processing/chroma_store.py`.

It supports:

- adding chunk embeddings and documents
- deleting all chunks for a filename
- semantic search with optional filename filtering
- counting all chunks or the chunks for a single file

## Reranking

Reranking lives in `backend/rag/reranker.py` using:

- `cross-encoder/ms-marco-MiniLM-L-6-v2`

Why it exists:

- vector search is fast for finding candidates
- reranking improves the final ordering before generation

The reranker now skips unnecessary work for single-result cases and uses batched prediction.

## Generation

Generation lives in `backend/rag/generator.py`.

The backend calls Ollama at:

- `http://localhost:11434/api/generate`

with:

- model: `llama3`
- streaming enabled

The prompt is constrained to:

- answer only from retrieved context
- say clearly when context is missing
- include all relevant rows or records when the user asks for a complete list

## Query Pipeline

When a user asks a question:

1. FastAPI validates the question.
2. It checks whether indexed data exists for the selected scope.
3. If a specific document is selected, the backend confirms it exists and is fully processed.
4. The question is embedded.
5. ChromaDB retrieves candidate chunks.
6. The reranker orders those chunks.
7. The best chunks are joined into one context string.
8. Ollama generates a streamed answer from that context.

Broad questions such as "list all rows" or "show the complete table" retrieve more context than narrow questions.

## Streamlit UI

`streamlit_app.py` provides the user-facing workflow.

It handles:

- file upload
- document listing
- delete actions
- single-document scope selection
- chat history in session state
- live streaming of assistant responses

It talks directly to FastAPI using `requests`, so there is no extra web proxy layer anymore.

## Why This Is Faster

Compared with the earlier setup, the main gains come from:

- removing the extra Next.js proxy layer from the primary user flow
- more efficient PDF and Excel text assembly
- structure-aware chunking that reduces noisy chunk boundaries
- batched normalized embeddings
- tighter retrieval sizing
- avoiding unnecessary reranker work in trivial cases

## Current Limits

The system is still intentionally local and lightweight, so a few limits remain:

- no multi-user isolation
- no authentication
- no explicit citations in the UI yet
- no semantic table extraction beyond text conversion
- no incremental indexing for partially changed files

## Summary

This project is now a cleaner local RAG stack:

- Streamlit for the UI
- FastAPI for orchestration
- PyMuPDF and Pandas for ingestion
- Sentence Transformers for embeddings
- ChromaDB for persistence
- CrossEncoder reranking for better relevance
- Ollama for local answer generation

The result is a simpler deployment path and a faster document-chat workflow.
