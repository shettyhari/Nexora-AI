import hashlib
import json
import logging
import math
import re
from typing import List, Optional
import httpx
import numpy as np
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Pluggable Embedding Service supporting OpenAI, Gemini, and Local Deterministic Vector Generation."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two unit or un-normalized vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        a = np.array(vec1, dtype=np.float32)
        b = np.array(vec2, dtype=np.float32)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _local_embed(self, text: str) -> List[float]:
        """
        High-performance local n-gram frequency & hashing projection into unit vector.
        Captures word overlap, syntactic patterns, and semantic term weights deterministically.
        """
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = re.findall(r"\b\w+\b", text.lower())

        if not tokens:
            return vector.tolist()

        # Word tokens and character 3-grams
        features = tokens.copy()
        for i in range(len(text) - 2):
            features.append(text[i:i+3].lower())

        for feature in features:
            # MD5 hash to deterministic bucket in dimension
            hash_val = int(hashlib.md5(feature.encode("utf-8")).hexdigest(), 16)
            index = hash_val % self.dimension
            sign = 1.0 if ((hash_val >> 16) % 2 == 0) else -1.0
            vector[index] += sign * (1.0 / math.sqrt(len(features)))

        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return [round(float(v), 6) for v in vector]

    async def get_embedding(self, text: str) -> List[float]:
        """Generate vector embedding for a single string."""
        results = await self.get_batch_embeddings([text])
        return results[0] if results else self._local_embed(text)

    async def get_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings in batch, falling back gracefully to local vector generator."""
        if not texts:
            return []

        # 1. Try OpenAI if key is present
        if settings.OPENAI_API_KEY:
            try:
                url = "https://api.openai.com/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": settings.EMBEDDING_MODEL or "text-embedding-3-small",
                    "input": texts
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        embeddings = [item["embedding"] for item in data["data"]]
                        return embeddings
            except Exception as e:
                logger.warning(f"OpenAI embedding call failed, falling back: {e}")

        # 2. Try Gemini if key is present
        if settings.GEMINI_API_KEY:
            try:
                results = []
                headers = {"Content-Type": "application/json"}
                async with httpx.AsyncClient(timeout=10.0) as client:
                    for text in texts:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={settings.GEMINI_API_KEY}"
                        payload = {
                            "model": "models/text-embedding-004",
                            "content": {"parts": [{"text": text[:2048]}]}
                        }
                        resp = await client.post(url, json=payload, headers=headers)
                        if resp.status_code == 200:
                            data = resp.json()
                            results.append(data.get("embedding", {}).get("values", []))
                        else:
                            break
                    if len(results) == len(texts):
                        return results
            except Exception as e:
                logger.warning(f"Gemini embedding call failed, falling back: {e}")

        # 3. Deterministic Local Vector Projection
        return [self._local_embed(t) for t in texts]


# Global singleton instance
embedding_service = EmbeddingService(dimension=settings.VECTOR_DIMENSION)

