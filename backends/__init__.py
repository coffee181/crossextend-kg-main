"""Backend factories for CrossExtend-KG."""

from .embeddings import build_embedding_backend
from .llm import build_llm_backend

__all__ = ["build_embedding_backend", "build_llm_backend"]
