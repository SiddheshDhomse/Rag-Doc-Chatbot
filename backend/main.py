from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
import shutil
import os
import re
import time
from typing import Optional, Tuple
from processing.chunking import chunk_text
from processing.embeddings import embed_chunks, embed_query
from ingestion.pdf_parser import extract_text_from_pdf
from ingestion.excel_parser import extract_text_from_excel
import numpy as np
from rag.generator import generate_response_stream
from rag.reranker import rerank_chunks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# New imports for DB and Chroma
from db.database import engine, Base, get_db
from db.models import Document
from processing.chroma_store import (
    delete_chunks_by_filename,
    get_collection_size,
    get_filename_chunk_count,
    index_chunks,
    search_chunks,
)

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def choose_retrieval_k(question: str, total_chunks: int) -> int:
    question_lower = question.lower()
    broad_patterns = (
        r"\ball\b",
        r"\bevery\b",
        r"\bcomplete\b",
        r"\bentire\b",
        r"\blist\b",
        r"\btable\b",
        r"\brows?\b",
        r"\bshow\b.*\bstudents?\b",
        r"\bstudents?\s+data\b",
    )
    is_broad_query = any(re.search(pattern, question_lower) for pattern in broad_patterns)

    if is_broad_query:
        return max(1, min(total_chunks, 16))
    return max(1, min(total_chunks, 6))


def extract_text_and_chunking(file_path: str, extension: str) -> Tuple[str, int, int]:
    if extension == ".pdf":
        return extract_text_from_pdf(file_path), 500, 100
    if extension in {".xlsx", ".xls"}:
        return extract_text_from_excel(file_path), 1400, 250
    raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or Excel.")


from db.database import SessionLocal

def index_file_task(file_path: str, filename: str):
    db = SessionLocal()
    db_doc = db.query(Document).filter(Document.filename == filename).first()
    if not db_doc:
        db_doc = Document(filename=filename, status="processing")
        db.add(db_doc)
    else:
        db_doc.status = "processing"
    db.commit()
    db.refresh(db_doc)
    
    try:
        started_at = time.perf_counter()
        extension = os.path.splitext(file_path)[1].lower()
        text, chunk_size, overlap = extract_text_and_chunking(file_path, extension)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        delete_chunks_by_filename(filename)

        if not chunks:
            raise ValueError("No text could be extracted from the uploaded file.")

        embeddings = embed_chunks(chunks)
        embeddings_list = np.array(embeddings).tolist()

        index_chunks(embeddings_list, chunks, metadata={"filename": filename})

        db_doc.chunks_count = len(chunks)
        db_doc.status = "processed"
        db.commit()
        elapsed = time.perf_counter() - started_at
        print(f"Indexed {filename} into {len(chunks)} chunks in {elapsed:.2f}s")
    except Exception as e:
        delete_chunks_by_filename(filename)
        db_doc.chunks_count = 0
        db_doc.status = "error"
        db.commit()
        print(f"Error indexing {filename}: {e}")
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Offline RAG System Running (Persistent)"}

@app.post("/upload/")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    safe_filename = os.path.basename(file.filename or "").strip()
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    extension = os.path.splitext(safe_filename)[1].lower()
    if extension not in {".pdf", ".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or Excel.")

    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

    background_tasks.add_task(index_file_task, file_path, safe_filename)
    return {"filename": safe_filename, "message": "Document upload accepted and is processing in background."}

@app.get("/status/{filename}")
def get_status(filename: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.filename == filename).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"filename": doc.filename, "status": doc.status, "chunks": doc.chunks_count}

@app.get("/documents/")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.upload_date.desc()).all()
    return [{"filename": d.filename, "status": d.status, "chunks": d.chunks_count, "upload_date": d.upload_date} for d in docs]

@app.delete("/documents/{filename}")
def delete_document(filename: str, db: Session = Depends(get_db)):
    safe_filename = os.path.basename(filename).strip()
    if not safe_filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    doc = db.query(Document).filter(Document.filename == safe_filename).first()
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    file_exists = os.path.exists(file_path)

    if not doc and not file_exists:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc and doc.status == "processing":
        raise HTTPException(
            status_code=409,
            detail="Document is still processing. Try deleting it again after indexing finishes."
        )

    delete_chunks_by_filename(safe_filename)

    if file_exists:
        try:
            os.remove(file_path)
        except PermissionError as exc:
            raise HTTPException(
                status_code=409,
                detail="Document file is still in use. Please wait a moment and try again."
            ) from exc

    if doc:
        db.delete(doc)
        db.commit()

    return {"filename": safe_filename, "message": "Document removed from context."}

@app.post("/query/")
def query_system(question: str, filename: Optional[str] = None, db: Session = Depends(get_db)):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    safe_filename = os.path.basename(filename).strip() if filename else None
    total_chunks = get_filename_chunk_count(safe_filename) if safe_filename else get_collection_size()

    if total_chunks == 0:
        raise HTTPException(
            status_code=400,
            detail="No indexed document found for that scope. Upload a PDF/Excel file first."
        )

    if safe_filename:
        doc = db.query(Document).filter(Document.filename == safe_filename).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Selected document was not found.")
        if doc.status != "processed":
            raise HTTPException(status_code=400, detail="Selected document is not ready yet.")

    query_embedding_list = np.array(embed_query(question)).tolist()
    retrieval_k = choose_retrieval_k(question, total_chunks)
    initial_results = search_chunks(
        query_embedding_list,
        k=min(max(retrieval_k * 2, retrieval_k), 24),
        filename=safe_filename,
    )

    refined_results = rerank_chunks(question, initial_results, top_k=retrieval_k)
    if not refined_results:
        raise HTTPException(
            status_code=404,
            detail="No relevant context found for that query."
        )

    context = "\n".join(refined_results)
    
    return StreamingResponse(
        generate_response_stream(context, question), 
        media_type="text/plain"
    )
