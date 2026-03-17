import os
import json
import faiss
import pickle
import numpy as np
from google import genai
import config

index = None
bm25 = None
chunks = []
client = genai.Client(api_key=config.GEMINI_API_KEY)

def load_local_index():
    global index, bm25, chunks
    # Path to klein_ai's generated index files
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'klein_ai'))
    
    faiss_path = os.path.join(base_dir, 'index.faiss')
    bm25_path = os.path.join(base_dir, 'bm25_index.pkl')
    chunks_path = os.path.join(base_dir, 'chunks.json')
    
    if os.path.exists(faiss_path):
        index = faiss.read_index(faiss_path)
        with open(bm25_path, 'rb') as f:
            bm25 = pickle.load(f)
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        return True
    return False

def check_confidence_and_search(query):
    if index is None:
        load_local_index()
    if index is None:
        return "", 0.0

    try:
        response = client.models.embed_content(
            model='text-embedding-004',
            contents=query
        )
        q_emb = np.array([response.embeddings[0].values]).astype('float32')
        
        distances, ids = index.search(q_emb, 3)
        confidence = 1.0 / (1.0 + distances[0][0]) if len(distances[0]) > 0 else 0.0
        
        # We only really care if the confidence is high enough (e.g. > 0.6)
        if confidence > 0.6:
            vector_results = [chunks[i] for i in ids[0] if i < len(chunks)]
            return "\n".join(vector_results), confidence
        else:
            return "", confidence
    except Exception as e:
        print(f"Erro no Fast-RAG: {e}")
        return "", 0.0