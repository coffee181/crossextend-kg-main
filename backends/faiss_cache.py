#!/usr/bin/env python3
"""FAISS-based embedding cache for CrossExtend-KG.

This module provides persistent caching for embedding vectors using FAISS indices.
Caching embeddings avoids redundant API calls and speeds up pipeline execution.

Architecture:
- FaissEmbeddingCache: Manages FAISS index and metadata for a single domain
- CachedEmbeddingBackend: Wrapper that provides caching for any embedding backend

Storage Structure:
    data/embeddings/{domain}/
        index.faiss           # FAISS index file
        metadata.jsonl        # text→id mapping and embeddings
        manifest.json         # metadata: dimension, count, model, created_at

Usage:
    cache = FaissEmbeddingCache(cache_dir, domain_id, dimension)
    cache.load()  # Load existing index if available
    backend = CachedEmbeddingBackend(base_backend, cache)

    vectors = backend.embed_texts(texts, domain_id)  # Cached embedding calls
    cache.save()  # Persist cache after run
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ..io import ensure_dir, read_json, read_jsonl, write_json, write_jsonl

logger = logging.getLogger(__name__)

# Default embedding dimension for most models
DEFAULT_EMBEDDING_DIMENSION = 1024


class EmbeddingBackend(Protocol):
    def embed_texts(self, texts: list[str], domain_id: str | None = None) -> list[list[float]]: ...


def _text_hash(text: str) -> str:
    """Generate a stable hash for text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _utc_now() -> str:
    """Get current UTC timestamp in ISO format."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class FaissEmbeddingCache:
    """FAISS-based embedding cache for a single domain.

    Manages:
    - FAISS index for fast similarity search
    - Metadata JSONL for text→embedding mapping
    - Manifest JSON for cache metadata

    Attributes:
        cache_dir: Root directory for all caches (e.g., data/embeddings)
        domain_id: Domain identifier (e.g., "battery")
        dimension: Embedding vector dimension
        model_name: Name of embedding model used
    """

    def __init__(
        self,
        cache_dir: Path,
        domain_id: str,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        model_name: str = "",
    ) -> None:
        self.cache_dir = cache_dir
        self.domain_id = domain_id
        self.dimension = dimension
        self.model_name = model_name
        self._index: Any = None
        self._metadata: dict[str, dict[str, Any]] = {}  # hash -> {text, vector, id}
        self._id_counter: int = 0
        self._loaded: bool = False

    @property
    def domain_cache_dir(self) -> Path:
        """Path to domain-specific cache directory."""
        return self.cache_dir / self.domain_id

    @property
    def index_path(self) -> Path:
        """Path to FAISS index file."""
        return self.domain_cache_dir / "index.faiss"

    @property
    def metadata_path(self) -> Path:
        """Path to metadata JSONL file."""
        return self.domain_cache_dir / "metadata.jsonl"

    @property
    def manifest_path(self) -> Path:
        """Path to manifest JSON file."""
        return self.domain_cache_dir / "manifest.json"

    def load(self) -> bool:
        """Load existing cache from disk.

        Returns:
            True if cache was loaded, False if no cache exists.
        """
        if self._loaded:
            return True

        if not self.index_path.exists():
            logger.debug("No existing FAISS cache for domain %s", self.domain_id)
            return False

        try:
            import faiss
        except ImportError:
            logger.warning("FAISS not installed, caching disabled")
            return False

        try:
            # Load FAISS index
            self._index = faiss.read_index(str(self.index_path))

            # Load metadata
            if self.metadata_path.exists():
                for item in read_jsonl(self.metadata_path):
                    text_hash = item.get("text_hash", "")
                    if text_hash:
                        self._metadata[text_hash] = item
                        self._id_counter = max(self._id_counter, item.get("id", 0) + 1)

            # Load manifest
            if self.manifest_path.exists():
                manifest = read_json(self.manifest_path)
                self.model_name = manifest.get("model", self.model_name)
                self.dimension = manifest.get("dimension", self.dimension)

            self._loaded = True
            logger.info(
                "Loaded FAISS cache for domain %s: %d vectors, dimension=%d",
                self.domain_id,
                len(self._metadata),
                self.dimension,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load FAISS cache for domain %s: %s", self.domain_id, exc)
            self._index = None
            self._metadata = {}
            return False

    def save(self) -> None:
        """Save cache to disk."""
        if not self._metadata:
            logger.debug("No embeddings to cache for domain %s", self.domain_id)
            return

        try:
            import faiss
        except ImportError:
            logger.warning("FAISS not installed, cannot save cache")
            return

        ensure_dir(self.domain_cache_dir)

        # Build FAISS index if not exists
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity

        # Write metadata
        write_jsonl(self.metadata_path, list(self._metadata.values()))

        # Write FAISS index
        faiss.write_index(self._index, str(self.index_path))

        # Write manifest
        manifest = {
            "domain_id": self.domain_id,
            "dimension": self.dimension,
            "count": len(self._metadata),
            "model": self.model_name,
            "created_at": _utc_now(),
        }
        write_json(self.manifest_path, manifest)

        logger.info(
            "Saved FAISS cache for domain %s: %d vectors to %s",
            self.domain_id,
            len(self._metadata),
            self.domain_cache_dir,
        )

    def get_embedding(self, text: str) -> list[float] | None:
        """Get embedding from cache if available.

        Args:
            text: Text to look up

        Returns:
            Embedding vector if cached, None otherwise
        """
        text_hash = _text_hash(text)
        entry = self._metadata.get(text_hash)
        if entry:
            return entry.get("vector", [])
        return None

    def add_embedding(self, text: str, vector: list[float]) -> None:
        """Add embedding to cache.

        Args:
            text: Text content
            vector: Embedding vector
        """
        try:
            import faiss
        except ImportError:
            return

        text_hash = _text_hash(text)
        if text_hash in self._metadata:
            return  # Already cached

        # Build index if not exists
        if self._index is None:
            self._index = faiss.IndexFlatIP(self.dimension)

        # Normalize vector for cosine similarity (inner product with normalized vectors)
        vec_array = np.asarray(vector, dtype=np.float32)
        vec_norm = np.linalg.norm(vec_array)
        if vec_norm > 0:
            vec_array = vec_array / vec_norm

        # Add to FAISS index
        vec_array = vec_array.reshape(1, -1)
        self._index.add(vec_array)

        # Store metadata
        entry = {
            "id": self._id_counter,
            "text_hash": text_hash,
            "text": text[:500],  # Truncate for storage
            "vector": vector,
            "added_at": _utc_now(),
        }
        self._metadata[text_hash] = entry
        self._id_counter += 1

    def search(self, query_vector: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Search for similar embeddings.

        Args:
            query_vector: Query embedding vector
            k: Number of results to return

        Returns:
            List of (id, score) tuples
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        # Normalize query vector
        query_array = np.asarray(query_vector, dtype=np.float32)
        query_norm = np.linalg.norm(query_array)
        if query_norm > 0:
            query_array = query_array / query_norm
        query_array = query_array.reshape(1, -1)

        scores, ids = self._index.search(query_array, k)
        results = []
        for i, score in zip(ids[0], scores[0]):
            if i >= 0:  # FAISS returns -1 for empty slots
                results.append((int(i), float(score)))
        return results

    def has_text(self, text: str) -> bool:
        """Check if text is already cached."""
        return _text_hash(text) in self._metadata

    @property
    def count(self) -> int:
        """Number of cached embeddings."""
        return len(self._metadata)


class CachedEmbeddingBackend:
    """Embedding backend wrapper with FAISS caching.

    Wraps any embedding backend and caches results per domain.
    On first call for a text, computes embedding and caches it.
    On subsequent calls, returns cached embedding.

    Attributes:
        backend: Underlying embedding backend
        caches: Dict mapping domain_id to FaissEmbeddingCache
        cache_dir: Root directory for caches
        dimension: Embedding dimension
        model_name: Model name for manifest
    """

    def __init__(
        self,
        backend: EmbeddingBackend,
        cache_dir: Path,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        model_name: str = "",
        enabled: bool = True,
    ) -> None:
        self.backend = backend
        self.cache_dir = cache_dir
        self.dimension = dimension
        self.model_name = model_name
        self.enabled = enabled
        self._caches: dict[str, FaissEmbeddingCache] = {}

    def _get_cache(self, domain_id: str) -> FaissEmbeddingCache:
        """Get or create cache for a domain."""
        if domain_id not in self._caches:
            cache = FaissEmbeddingCache(
                cache_dir=self.cache_dir,
                domain_id=domain_id,
                dimension=self.dimension,
                model_name=self.model_name,
            )
            if self.enabled:
                cache.load()
            self._caches[domain_id] = cache
        return self._caches[domain_id]

    def embed_texts(self, texts: list[str], domain_id: str | None = None) -> list[list[float]]:
        """Compute embeddings with caching.

        Args:
            texts: List of texts to embed
            domain_id: Domain for caching (required for caching)

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # If caching disabled or no domain, use backend directly
        if not self.enabled or not domain_id:
            return self.backend.embed_texts(texts)

        cache = self._get_cache(domain_id)

        # Check cache for each text
        vectors: list[list[float]] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for i, text in enumerate(texts):
            cached = cache.get_embedding(text)
            if cached:
                vectors.append(cached)
                logger.debug("Retrieved cached embedding for text %d", i)
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                vectors.append([])  # Placeholder

        # Compute uncached embeddings
        if uncached_texts:
            logger.info(
                "Computing %d new embeddings for domain %s (cached: %d)",
                len(uncached_texts),
                domain_id,
                len(texts) - len(uncached_texts),
            )
            new_vectors = self.backend.embed_texts(uncached_texts)

            # Add to cache and fill results
            for j, (text, vector) in enumerate(zip(uncached_texts, new_vectors)):
                cache.add_embedding(text, vector)
                vectors[uncached_indices[j]] = vector

        return vectors

    def save_all_caches(self) -> None:
        """Save all domain caches to disk."""
        if not self.enabled:
            return

        for domain_id, cache in self._caches.items():
            cache.save()

    def load_cache(self, domain_id: str) -> bool:
        """Explicitly load cache for a domain."""
        cache = self._get_cache(domain_id)
        return cache.load()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics per domain."""
        return {domain_id: cache.count for domain_id, cache in self._caches.items()}


def build_cached_embedding_backend(
    backend: EmbeddingBackend,
    cache_dir: str | Path | None,
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    model_name: str = "",
    enabled: bool = True,
) -> CachedEmbeddingBackend:
    """Build a cached embedding backend.

    Args:
        backend: Base embedding backend
        cache_dir: Directory for cache storage (default: data/embeddings)
        dimension: Embedding dimension
        model_name: Model name for manifest
        enabled: Whether caching is enabled

    Returns:
        CachedEmbeddingBackend instance
    """
    if cache_dir is None:
        cache_dir = Path("data/embeddings")
    else:
        cache_dir = Path(cache_dir)

    return CachedEmbeddingBackend(
        backend=backend,
        cache_dir=cache_dir,
        dimension=dimension,
        model_name=model_name,
        enabled=enabled,
    )