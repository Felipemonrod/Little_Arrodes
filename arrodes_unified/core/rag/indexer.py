"""
Indexador offline para gerar indices FAISS e BM25.
Rode manualmente quando adicionar novos arquivos de lore.

Uso:
    python -m core.rag.indexer
"""

import glob
import json
import os
import pickle
import sys
import time

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from google import genai

from core.config import LORE_DIR, DATA_DIR, GEMINI_API_KEY
from core.rag.chunker import chunk_text

EMBEDDING_MODEL = "gemini-embedding-001"
BATCH_LOG_INTERVAL = 50


def build_index(api_key: str | None = None) -> bool:
    """
    Le todos os .txt de lore, gera chunks, embeddings e salva indices.

    Returns:
        True se indexacao foi bem sucedida.
    """
    _api_key = api_key or GEMINI_API_KEY
    if not _api_key:
        print("ERRO: GEMINI_API_KEY nao encontrada. Defina no .env.")
        return False

    client = genai.Client(api_key=_api_key)

    # Busca arquivos de lore
    txt_files = glob.glob(os.path.join(LORE_DIR, "*.txt"))
    if not txt_files:
        print(f"ERRO: Nenhum arquivo .txt encontrado em {LORE_DIR}")
        return False

    print(f"Encontrados {len(txt_files)} arquivos de lore.")

    # Gera chunks de todos os arquivos
    all_chunks: list[str] = []
    for file_path in txt_files:
        filename = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        chunks = chunk_text(content)
        all_chunks.extend(chunks)
        print(f"  {filename}: {len(chunks)} chunks")

    print(f"\nTotal: {len(all_chunks)} chunks gerados.")
    print("Gerando embeddings via Gemini API...")

    # Gera embeddings
    embeddings: list[list[float]] = []
    for i, chunk in enumerate(all_chunks):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=chunk,
            )
            embeddings.append(response.embeddings[0].values)
        except Exception as e:
            print(f"  Erro no chunk {i}: {e}. Usando zeros.")
            if embeddings:
                embeddings.append([0.0] * len(embeddings[0]))
            else:
                raise

        if (i + 1) % BATCH_LOG_INTERVAL == 0:
            print(f"  Processado: [{i + 1}/{len(all_chunks)}]")

        # Rate limiting basico
        if (i + 1) % 100 == 0:
            time.sleep(1)

    # Cria indice FAISS
    print("\nCriando indice FAISS...")
    embeddings_np = np.array(embeddings).astype("float32")
    dim = embeddings_np.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings_np)

    os.makedirs(DATA_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(DATA_DIR, "index.faiss"))

    # Cria indice BM25
    print("Criando indice BM25...")
    tokenized_chunks = [chunk.lower().split() for chunk in all_chunks]
    bm25 = BM25Okapi(tokenized_chunks)
    with open(os.path.join(DATA_DIR, "bm25_index.pkl"), "wb") as f:
        pickle.dump(bm25, f)

    # Salva chunks
    with open(os.path.join(DATA_DIR, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"\nSUCESSO! Indices salvos em {DATA_DIR}/")
    print(f"  - index.faiss ({dim}D, {len(all_chunks)} vetores)")
    print(f"  - bm25_index.pkl")
    print(f"  - chunks.json ({len(all_chunks)} chunks)")
    return True


if __name__ == "__main__":
    # Permite rodar como: python -m core.rag.indexer
    # Adiciona o diretorio pai ao path para imports relativos
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"), override=True)

    success = build_index(api_key=os.getenv("GEMINI_API_KEY", ""))
    sys.exit(0 if success else 1)
