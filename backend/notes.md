# Enterprise RAG Chatbot: Technical Deep Dive

This document provides a detailed technical explanation of the Enterprise RAG Chatbot project. It covers the architecture, technology stack, data flow, and individual component responsibilities.

## 1. Project Overview

This project is a local-first, Retrieval-Augmented Generation (RAG) system designed to answer questions about user-uploaded documents (PDFs and Excel files). It combines a document processing backend with a web-based chat interface.

The core user flow is:
1.  Upload a document.
2.  Wait for it to be processed and indexed.
3.  Ask questions about the document's content.

The architecture is split into two main parts: a **FastAPI backend** for all heavy lifting and a **Streamlit UI** for user interaction.

## 2. System Architecture

The system consists of several interconnected components:

-   **Streamlit UI**: The user-facing application for file management and chat. It communicates directly with the FastAPI backend via HTTP requests.
-   **FastAPI Backend**: The central nervous system. It exposes a REST API to handle file uploads, document processing, metadata storage, and the entire RAG query pipeline.
-   **Ollama**: An external, locally-running service that provides Large Language Model (LLM) inference (e.g., using `llama3`). The backend communicates with it to generate answers.
-   **Storage Layers**:
    -   **File Storage (`backend/uploads/`)**: Stores the original uploaded documents.
    -   **Vector Store (`backend/chroma_data/`)**: A persistent ChromaDB database that stores text chunks and their corresponding vector embeddings for semantic search.
    -   **Metadata Store (`backend/metadata.db`)**: A SQLite database that tracks document information like filename, processing status, and chunk count.

The legacy Next.js frontend (`frontend/my-app`) is no longer part of the primary workflow.

## 3. Technology Stack & Key Libraries

### Backend (Python)
-   **Web Framework**: `FastAPI` - For building the high-performance REST API.
-   **Web Server**: `Uvicorn` - ASGI server to run the FastAPI application.
-   **Document Parsing**:
    -   PDF: `PyMuPDF` (`fitz`) - Efficiently extracts text from PDF files.
    -   Excel: `pandas` & `openpyxl` - Parses `.xlsx` and `.xls` files, converting sheet data into a text-based format.
-   **Database / ORM**:
    -   `SQLAlchemy` - For interacting with the metadata database.
    -   `SQLite` - The file-based database engine for metadata.
-   **Vector Embeddings**: `sentence-transformers` - Used to generate dense vector representations of text. The `all-MiniLM-L6-v2` model is used for this.
-   **Vector Database**: `chromadb` - For storing and searching vector embeddings.
-   **Reranking**: `sentence-transformers` (Cross-Encoder) - The `ms-marco-MiniLM-L-6-v2` model is used to improve the relevance of retrieved search results.
-   **LLM Communication**: `requests` - To make HTTP calls to the Ollama API.

### Frontend (Python)
-   **UI Framework**: `Streamlit` - For creating the interactive web-based user interface.
-   **HTTP Client**: `requests` - To communicate with the FastAPI backend.

### LLM Runtime
-   **Inference**: `Ollama` - Manages and serves local LLMs like Llama 3.

## 4. End-to-End Data Pipelines

### Pipeline 1: Document Ingestion and Indexing

This process runs in the background after a file is uploaded to avoid blocking the user.

1.  **Upload**: The user selects a file in the Streamlit UI. Streamlit sends a `POST` request to the `/upload/` endpoint on the FastAPI backend.
2.  **Persist & Schedule**: The backend saves the raw file to `backend/uploads/` and creates a new entry in the SQLite `documents` table with a `status` of `"processing"`. It then schedules a background task (`index_file_task`) to handle the rest.
3.  **Parse Text**: Based on the file extension, the appropriate parser (`pdf_parser` or `excel_parser`) is used to extract all text content.
4.  **Chunk Text**: The extracted text is passed to the `chunk_text` function. This function splits the text into smaller, overlapping chunks. The chunking is structure-aware, attempting to split along sentence or paragraph boundaries.
5.  **Clean Vector Store**: Any existing chunks associated with the same filename are deleted from ChromaDB to ensure a clean re-index.
6.  **Generate Embeddings**: The `embed_chunks` function uses the `sentence-transformers` library to convert the list of text chunks into a list of numerical vector embeddings. This is done in batches for efficiency.
7.  **Index in ChromaDB**: The `index_chunks` function adds the embeddings, the original text chunks, and associated metadata (e.g., `{"filename": "..."}`) to the ChromaDB collection.
8.  **Update Metadata**: The background task updates the document's record in the SQLite database, setting the `status` to `"processed"` and recording the total `chunks_count`. If an error occurs, the status is set to `"error"`.

### Pipeline 2: Query, Retrieval, and Generation (RAG)

This pipeline is executed when a user asks a question in the chat.

1.  **Send Query**: The Streamlit UI sends a `POST` request to the `/query/` endpoint with the user's `question` and an optional `filename` to scope the search.
2.  **Validate Scope**: The backend checks if there are any indexed documents available for the given scope. If a specific file is targeted, it verifies that its status is `"processed"`.
3.  **Embed Query**: The user's question is converted into a vector embedding using `embed_query`.
4.  **Semantic Search (Retrieval)**:
    -   The backend determines how many chunks to retrieve (`k`). It uses a larger `k` for "broad" questions (e.g., "list all...") and a smaller `k` for specific ones.
    -   A query is sent to ChromaDB (`search_chunks`) to find the `k` most semantically similar text chunks from the vector store. The search is filtered by `filename` if one was provided.
5.  **Rerank Results**:
    -   The initial chunks retrieved from ChromaDB are passed to the `rerank_chunks` function.
    -   A more powerful Cross-Encoder model re-evaluates the relevance of each chunk against the original question and re-orders them. This significantly improves the quality of the context provided to the LLM.
6.  **Construct Context**: The top-ranked, refined chunks are joined together into a single block of text. This is the "context" the LLM will use to answer the question.
7.  **Generate Answer**:
    -   The `generate_response_stream` function constructs a detailed prompt containing the retrieved context and the user's question.
    -   This prompt is sent to the Ollama `/api/generate` endpoint.
8.  **Stream Response**: The backend receives the response from Ollama as a stream of tokens and forwards it directly to the Streamlit UI via a `StreamingResponse`. The UI then renders the answer as it arrives, creating a "typing" effect.

## 5. Component Responsibilities

### `streamlit_app.py`
-   **UI Rendering**: Manages all visual components, including the document manager, chat history, and input fields.
-   **State Management**: Uses `st.session_state` to maintain chat history and the selected document scope.
-   **API Client**: Acts as a client to the FastAPI backend, handling uploads, deletions, status checks, and queries.
-   **Real-time Updates**: Consumes the streaming response from the `/query/` endpoint to display the assistant's answer live.

### `backend/main.py`
-   **API Orchestration**: Defines all API endpoints and orchestrates the calls between different modules (parsing, chunking, embedding, storage, RAG).
-   **Input Validation**: Ensures that inputs like filenames and questions are valid and that files are of a supported type.
-   **Error Handling**: Provides meaningful HTTP error responses for various failure scenarios (e.g., file not found, document still processing).
-   **Background Processing**: Leverages `BackgroundTasks` to offload the time-consuming indexing process from the main request-response cycle.

### Storage (`chroma_store.py` & `db/models.py`)
-   **`chroma_store.py`**: Provides a clean abstraction layer for interacting with ChromaDB. It handles adding, deleting, and searching for chunks.
-   **`db/`**: Defines the SQLAlchemy model for the `documents` table and provides the session management (`get_db`) for the SQLite metadata store. This separation of metadata from the vector store is a robust design choice.

### RAG (`rag/generator.py` & `rag/reranker.py`)
-   **`reranker.py`**: Implements the crucial reranking step, which acts as a refinement filter after the initial fast vector search.
-   **`generator.py`**: Is responsible for communicating with the Ollama LLM. It formats the final prompt and handles the streaming API interaction.