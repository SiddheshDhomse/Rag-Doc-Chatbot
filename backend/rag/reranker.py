from sentence_transformers import CrossEncoder

# Load a fast, lightweight re-ranker model natively capable of offline execution
reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_chunks(query: str, chunks: list, top_k: int = 5) -> list:
    if not chunks:
        return []
        
    # Prepare pairs of (query, chunk)
    pairs = [[query, chunk] for chunk in chunks]
    
    # Predict scores
    scores = reranker_model.predict(pairs)
    
    # Sort chunks based on their score descending
    scored_chunks = list(zip(scores, chunks))
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # Return strictly the top_k most relevant chunks
    return [chunk for score, chunk in scored_chunks[:top_k]]
