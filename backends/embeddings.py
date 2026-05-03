#!/usr/bin/env python3
"""Embedding backends for CrossExtend-KG."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Protocol

import numpy as np

try:
    from crossextend_kg.config import EmbeddingBackendConfig
    from crossextend_kg.exceptions import EmbeddingBackendError
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import EmbeddingBackendConfig
    from exceptions import EmbeddingBackendError

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


def normalize_api_base_url(base_url: str | None) -> str:
    value = (base_url or "").strip()
    if not value:
        raise ValueError("base_url is required")
    if not value.startswith("http://") and not value.startswith("https://"):
        value = f"http://{value}"
    if "0.0.0.0" in value:
        value = value.replace("0.0.0.0", "127.0.0.1")
    return value.rstrip("/")


def normalize_ollama_host(host: str | None) -> str:
    return normalize_api_base_url(host or "http://127.0.0.1:11434")


def build_api_endpoint(base_url: str, endpoint_path: str) -> str:
    normalized_base = normalize_api_base_url(base_url)
    normalized_endpoint = endpoint_path.lstrip("/")
    if normalized_base.endswith(f"/{normalized_endpoint}") or normalized_base.endswith(normalized_endpoint):
        return normalized_base
    return f"{normalized_base}/{normalized_endpoint}"


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    array_a = np.asarray(vec_a, dtype=np.float32)
    array_b = np.asarray(vec_b, dtype=np.float32)
    denom = np.linalg.norm(array_a) * np.linalg.norm(array_b)
    if denom == 0:
        return 0.0
    return float(np.dot(array_a, array_b) / denom)


class OpenAICompatibleEmbeddingBackend:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_sec: int = 120,
        dimensions: int | None = None,
    ) -> None:
        self.base_url = normalize_api_base_url(base_url)
        self.model = model
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.dimensions = dimensions

    def _post(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = build_api_endpoint(self.base_url, "embeddings")
        data = json.dumps(payload).encode("utf-8")
        last_error = None
        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace") if e.fp else ""
                last_error = EmbeddingBackendError(
                    f"embedding API returned HTTP {e.code}: {body[:500]}"
                )
                if e.code in {429, 500, 502, 503, 504} and attempt < 4:
                    delay_sec = min(10.0, 2.0 * attempt)
                    logger.warning(
                        "Retryable embedding API error on attempt %d/3: HTTP %d. Retrying in %.1fs",
                        attempt, e.code, delay_sec,
                    )
                    time.sleep(delay_sec)
                    continue
                raise last_error from e
            except (urllib.error.URLError, OSError, ConnectionError) as e:
                last_error = EmbeddingBackendError(f"embedding API connection failed: {e}")
                if attempt < 4:
                    delay_sec = min(10.0, 2.0 * attempt)
                    logger.warning(
                        "Retryable embedding connection error on attempt %d/3: %s. Retrying in %.1fs",
                        attempt, e, delay_sec,
                    )
                    time.sleep(delay_sec)
                    continue
                raise last_error from e
        raise last_error  # type: ignore[misc]

    _EMBED_BATCH_SIZE = 10

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if len(texts) <= self._EMBED_BATCH_SIZE:
            return self._embed_batch(texts)
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self._EMBED_BATCH_SIZE):
            batch = texts[offset : offset + self._EMBED_BATCH_SIZE]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, object] = {
            "model": self.model,
            "input": texts,
        }
        body = self._post(payload)
        items = body.get("data")
        if not isinstance(items, list) or len(items) != len(texts):
            raise RuntimeError("embedding endpoint returned an unexpected payload")
        vectors: list[list[float]] = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise RuntimeError("embedding endpoint returned an item without embedding")
            vectors.append(item["embedding"])
        return vectors


def build_embedding_backend(config: EmbeddingBackendConfig) -> EmbeddingBackend:
    return OpenAICompatibleEmbeddingBackend(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout_sec=config.timeout_sec,
        dimensions=config.dimensions,
    )
