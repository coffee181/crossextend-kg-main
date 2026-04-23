"""Active backend factories for the workflow-first CrossExtend-KG mainline."""

from backends.embeddings import build_embedding_backend
from backends.llm import build_llm_backend

__all__ = ["build_embedding_backend", "build_llm_backend"]
