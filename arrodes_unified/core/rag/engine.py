"""
Motor de busca RAG hibrido (FAISS + BM25).
Combina busca semantica vetorial com busca por palavras-chave
usando score ponderado configuravel.
"""

import json
import os
import pickle
from dataclasses import dataclass

import faiss
import numpy as np
from google import genai
from rank_bm25 import BM25Okapi

from core.config import DATA_DIR, GEMINI_API_KEY, RAG_ALPHA, RAG_CONFIDENCE_THRESHOLD
from core.logger import get_logger

log = get_logger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"


@dataclass
class SearchResult:
    """Resultado de uma busca RAG."""
    chunks: list[str]
    confidence: float
    faiss_scores: list[float]
    bm25_scores: list[float]


class RAGEngine:
    """Motor de busca hibrido FAISS + BM25."""

    def __init__(self, api_key: str | None = None) -> None:
        self._index: faiss.IndexFlatL2 | None = None
        self._bm25: BM25Okapi | None = None
        self._chunks: list[str] = []
        self._client: genai.Client | None = None
        self._api_key = api_key or GEMINI_API_KEY
        self._loaded = False

    def load(self) -> bool:
        """Carrega indices do disco. Retorna True se sucesso."""
        if self._loaded:
            return True

        faiss_path = os.path.join(DATA_DIR, "index.faiss")
        bm25_path = os.path.join(DATA_DIR, "bm25_index.pkl")
        chunks_path = os.path.join(DATA_DIR, "chunks.json")

        if not all(os.path.exists(p) for p in [faiss_path, bm25_path, chunks_path]):
            log.warning("Indices RAG nao encontrados em %s. Rode 'python -m core.rag.indexer'.", DATA_DIR)
            return False

        try:
            self._index = faiss.read_index(faiss_path)
            with open(bm25_path, "rb") as f:
                self._bm25 = pickle.load(f)
            with open(chunks_path, "r", encoding="utf-8") as f:
                self._chunks = json.load(f)

            if not self._api_key:
                log.warning("GEMINI_API_KEY nao definida - embeddings de query nao funcionarao.")
            else:
                self._client = genai.Client(api_key=self._api_key)

            self._loaded = True
            log.info("RAG carregado: %d chunks, indice FAISS + BM25.", len(self._chunks))
            return True
        except Exception as e:
            log.error("Erro ao carregar indices RAG: %s", e, exc_info=True)
            return False

    def _embed_query(self, query: str) -> np.ndarray | None:
        """Gera embedding para a query usando Gemini."""
        if not self._client:
            return None
        try:
            response = self._client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query,
            )
            return np.array([response.embeddings[0].values]).astype("float32")
        except Exception as e:
            log.error("Erro ao gerar embedding: %s", e)
            return None

    def _normalize_faiss_scores(self, distances: np.ndarray) -> list[float]:
        """Converte distancias L2 em scores normalizados [0, 1]."""
        return [1.0 / (1.0 + d) for d in distances]

    def _normalize_bm25_scores(self, scores: np.ndarray) -> list[float]:
        """Normaliza scores BM25 para [0, 1]."""
        max_score = max(scores) if len(scores) > 0 and max(scores) > 0 else 1.0
        return [s / max_score for s in scores]

    def search(self, query: str, top_k: int = 5, alpha: float | None = None) -> SearchResult:
        """
        Busca hibrida: combina FAISS (semantica) + BM25 (keywords).

        Args:
            query: Pergunta do usuario.
            top_k: Numero de resultados a retornar.
            alpha: Peso do FAISS (0-1). Default usa config RAG_ALPHA.

        Returns:
            SearchResult com chunks, confianca e scores.
        """
        if not self._loaded:
            self.load()

        if not self._loaded or self._index is None or self._bm25 is None:
            return SearchResult(chunks=[], confidence=0.0, faiss_scores=[], bm25_scores=[])

        _alpha = alpha if alpha is not None else RAG_ALPHA

        # Busca FAISS (semantica)
        q_emb = self._embed_query(query)
        faiss_results: dict[int, float] = {}
        if q_emb is not None:
            distances, ids = self._index.search(q_emb, top_k)
            faiss_scores = self._normalize_faiss_scores(distances[0])
            for idx, score in zip(ids[0], faiss_scores):
                if 0 <= idx < len(self._chunks):
                    faiss_results[int(idx)] = score

        # Busca BM25 (keywords)
        tokenized_query = query.lower().split()
        bm25_raw_scores = self._bm25.get_scores(tokenized_query)
        bm25_top_indices = np.argsort(bm25_raw_scores)[::-1][:top_k]
        bm25_norm = self._normalize_bm25_scores(bm25_raw_scores)
        bm25_results: dict[int, float] = {}
        for idx in bm25_top_indices:
            if bm25_raw_scores[idx] > 0:
                bm25_results[int(idx)] = bm25_norm[idx]

        # Combina scores (hybrid)
        all_indices = set(faiss_results.keys()) | set(bm25_results.keys())
        hybrid_scores: list[tuple[int, float, float, float]] = []
        for idx in all_indices:
            f_score = faiss_results.get(idx, 0.0)
            b_score = bm25_results.get(idx, 0.0)
            combined = _alpha * f_score + (1 - _alpha) * b_score
            hybrid_scores.append((idx, combined, f_score, b_score))

        # Ordena por score combinado
        hybrid_scores.sort(key=lambda x: x[1], reverse=True)
        top_results = hybrid_scores[:top_k]

        if not top_results:
            return SearchResult(chunks=[], confidence=0.0, faiss_scores=[], bm25_scores=[])

        chunks = [self._chunks[idx] for idx, _, _, _ in top_results]
        confidence = top_results[0][1]  # Score do melhor resultado
        f_scores = [fs for _, _, fs, _ in top_results]
        b_scores = [bs for _, _, _, bs in top_results]

        return SearchResult(
            chunks=chunks,
            confidence=confidence,
            faiss_scores=f_scores,
            bm25_scores=b_scores,
        )

    def check_and_search(self, query: str, threshold: float | None = None) -> tuple[str, float]:
        """
        Busca e retorna contexto se confianca for suficiente.
        Compativel com a interface antiga.

        Returns:
            (contexto_str, confianca)
        """
        _threshold = threshold if threshold is not None else RAG_CONFIDENCE_THRESHOLD
        result = self.search(query)

        if result.confidence >= _threshold and result.chunks:
            return "\n\n".join(result.chunks), result.confidence
        return "", result.confidence
