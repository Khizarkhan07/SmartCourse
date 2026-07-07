import hashlib
import json

import redis
from fastembed import TextEmbedding

from config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    """Turns text into vectors, with a Redis cache in front.

    This is the ONE place embeddings are produced — for both ingestion and
    query — so the same model is always used on both sides (the invariant from
    §6.2). The model lives behind this class, so swapping providers later is a
    change here and nowhere else.
    """

    def __init__(self) -> None:
        # fastembed runs the model via ONNX (no PyTorch). cache_dir points at
        # the model files baked into the image at build time, so there is no
        # download at runtime.
        self._model = TextEmbedding(
            model_name=settings.EMBEDDING_MODEL,
            cache_dir=settings.EMBEDDING_CACHE_DIR,
        )
        self._redis = redis.Redis.from_url(settings.REDIS_URL)
        # Counts real model inferences (cache misses). Lets tests prove the
        # cache actually prevents recomputation.
        self._model_calls = 0

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        # Key includes the model name: switch models and old cached vectors
        # (from a different model, different dimensions) are never reused.
        return f"emb:{settings.EMBEDDING_MODEL}:{digest}"

    def embed(self, text: str) -> list[float]:
        key = self._cache_key(text)
        cached = self._redis.get(key)
        if cached is not None:
            return json.loads(cached)

        vector = self._embed_uncached(text)
        self._redis.set(key, json.dumps(vector))
        return vector

    def _embed_uncached(self, text: str) -> list[float]:
        self._model_calls += 1
        # fastembed returns a generator of numpy arrays, one per input text.
        vector = next(iter(self._model.embed([text])))
        return vector.tolist()
