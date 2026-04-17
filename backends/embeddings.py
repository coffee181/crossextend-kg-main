#!/usr/bin/env python3
"""Embedding backends for CrossExtend-KG."""

from __future__ import annotations

import json
import urllib.request
from typing import Protocol

import numpy as np

from ..config import EmbeddingBackendConfig


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
        req = urllib.request.Request(
            build_api_endpoint(self.base_url, "embeddings"),
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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
