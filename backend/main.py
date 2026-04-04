from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
import shutil
import os
import re
from typing import Optional, Tuple
from processing.embeddings import model
from processing.chunking import chunk_text
from processing.embeddings import embed_chunks
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
from processing.chroma_store import delete_chunks_by_filename, index_chunks, search_chunks, get_collection_size

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
        r"\bshow\b.*\bstudents?\b",
        r"\bstudents?\s+data\b",
    )
    is_broad_query = any(re.search(pattern, question_lower) for pattern in broad_patterns)

    if is_broad_query:
        return min(total_chunks, 20)
    return min(total_chunks, 8)


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
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

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

    delete_chunks_by_filename(safe_filename)

    if file_exists:
        os.remove(file_path)

    if doc:
        db.delete(doc)
        db.commit()

    return {"filename": safe_filename, "message": "Document removed from context."}

@app.post("/query/")
def query_system(question: str, filename: Optional[str] = None):
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if get_collection_size() == 0:
        raise HTTPException(
            status_code=400,
            detail="No indexed document found. Upload a PDF/Excel file first."
        )

    # Encode gives an ndarray, we need a 1D list for chromadb querying
    query_embedding = model.encode([question])
    query_embedding_list = np.array(query_embedding).tolist()[0]

    retrieval_k = choose_retrieval_k(question, get_collection_size())
    initial_results = search_chunks(query_embedding_list, k=min(retrieval_k * 2, 20), filename=filename)

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
