#!/usr/bin/env python3
"""LLM backends for synthetic data generation and attachment decisions."""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any, Protocol

from .embeddings import build_api_endpoint, normalize_api_base_url
from ..config import LLMBackendConfig


class LLMBackend(Protocol):
    def supports_generation(self) -> bool: ...
    def generate_json(self, prompt: str) -> dict[str, Any]: ...


def _extract_first_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError(f"Failed to extract JSON from LLM response: {text[:200]}...")
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError(f"Failed to extract JSON from LLM response: {text[:200]}...")


def _normalize_chat_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") in {"text", "output_text"}
        )
    return str(content or "")


def extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return json.loads(_extract_first_json_object(text))


def _build_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


class ChatCompletionsLLMBackend:
    def __init__(self, config: LLMBackendConfig) -> None:
        self.base_url = normalize_api_base_url(config.base_url)
        self.api_key = config.api_key
        self.model = config.model
        self.timeout_sec = config.timeout_sec
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature

    def supports_generation(self) -> bool:
        return True

    def generate_json(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        req = urllib.request.Request(
            build_api_endpoint(self.base_url, "chat/completions"),
            data=json.dumps(payload).encode("utf-8"),
            headers=_build_headers(self.api_key),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        message = body["choices"][0]["message"]
        return extract_json(_normalize_chat_content(message.get("content", "")))


def build_llm_backend(config: LLMBackendConfig) -> LLMBackend:
    return ChatCompletionsLLMBackend(config)
