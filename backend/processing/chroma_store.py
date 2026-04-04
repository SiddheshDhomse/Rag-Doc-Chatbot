import chromadb
import os
import uuid
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chroma_data")

# Initialize ChromaDB client with persistent storage
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

# Get or create a collection
collection_name = "documents_collection"
collection = chroma_client.get_or_create_collection(name=collection_name)

def index_chunks(embeddings, chunks, metadata=None):
    if not chunks:
        return

    ids = [str(uuid.uuid4()) for _ in chunks]

    # Metadata is optional, but good for filtering later
    metadatas = [metadata or {} for _ in chunks]

    collection.add(
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )

def delete_chunks_by_filename(filename: str) -> None:
    if not filename:
        return

    results = collection.get(where={"filename": filename})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)

def search_chunks(query_embedding, k=3, filename: Optional[str] = None):
    if collection.count() == 0:
        raise ValueError("ChromaDB collection is empty. Upload and process a document first.")

    query_args = {
        "query_embeddings": [query_embedding],
        "n_results": k,
    }
    if filename:
        query_args["where"] = {"filename": filename}

    results = collection.query(**query_args)

    if "documents" in results and results["documents"]:
        return results["documents"][0]
    return []

def get_collection_size():
    return collection.count()
