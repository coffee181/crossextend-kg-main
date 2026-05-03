#!/usr/bin/env python3
"""LLM backends for synthetic data generation and attachment decisions."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol

import openai

from backends.embeddings import normalize_api_base_url
try:
    from crossextend_kg.config import LLMBackendConfig
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import LLMBackendConfig


logger = logging.getLogger(__name__)


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
    except json.JSONDecodeError:
        try:
            return json.loads(_extract_first_json_object(text))
        except (ValueError, json.JSONDecodeError) as nested_exc:
            raise ValueError(
                "Failed to parse JSON from LLM response. "
                f"Preview: {text[:240]}..."
            ) from nested_exc


class ChatCompletionsLLMBackend:
    def __init__(self, config: LLMBackendConfig, *, debug_dir: str | None = None) -> None:
        self.base_url = normalize_api_base_url(config.base_url)
        self.api_key = config.api_key
        self.model = config.model
        self.timeout_sec = config.timeout_sec
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.max_retries = 3
        self.request_max_attempts = 2
        self.debug_dir = debug_dir
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_sec,
            max_retries=self.max_retries,
        )


    def _save_raw_response(self, prompt: str, content: str) -> None:
        if not self.debug_dir:
            return
        try:
            debug_path = Path(self.debug_dir)
            debug_path.mkdir(parents=True, exist_ok=True)
            prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"llm_response_{timestamp}_{prompt_hash}.json"
            payload = {
                "timestamp": timestamp,
                "model": self.model,
                "prompt": prompt,
                "content": content,
            }
            (debug_path / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Failed to save debug LLM response: %s", exc)

    def supports_generation(self) -> bool:
        return True

    def generate_json(self, prompt: str) -> dict[str, Any]:
        retryable_errors = (
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.RateLimitError,
            openai.InternalServerError,
        )
        for attempt in range(1, self.request_max_attempts + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )
                choice = response.choices[0]
                finish_reason = getattr(choice, "finish_reason", None)
                if finish_reason not in {None, "stop"}:
                    raise RuntimeError(
                        "LLM response did not finish cleanly "
                        f"(finish_reason={finish_reason}). "
                        "Reduce prompt/output size or increase max_tokens."
                    )
                content = choice.message.content or ""
                if self.debug_dir:
                    self._save_raw_response(prompt, content)
                return extract_json(_normalize_chat_content(content))
            except ValueError as exc:
                if attempt >= self.request_max_attempts:
                    logger.error(
                        "Failed to parse JSON from LLM response after %d attempts: %s",
                        attempt,
                        exc,
                    )
                    raise
                delay_sec = min(20.0, 4.0 * attempt)
                logger.warning(
                    "LLM returned invalid JSON on attempt %d/%d: %s. Retrying in %.1fs",
                    attempt,
                    self.request_max_attempts,
                    exc,
                    delay_sec,
                )
                time.sleep(delay_sec)
            except retryable_errors as exc:
                if attempt >= self.request_max_attempts:
                    logger.error("OpenAI API error after %d attempts: %s", attempt, exc)
                    raise
                delay_sec = min(20.0, 4.0 * attempt)
                logger.warning(
                    "Retryable OpenAI API error on attempt %d/%d: %s. Retrying in %.1fs",
                    attempt,
                    self.request_max_attempts,
                    exc,
                    delay_sec,
                )
                time.sleep(delay_sec)
            except openai.APIError as exc:
                logger.error("OpenAI API error: %s", exc)
                raise
        raise RuntimeError("LLM request exhausted without a JSON response")


def build_llm_backend(config: LLMBackendConfig, *, debug_dir: str | None = None) -> LLMBackend:
    return ChatCompletionsLLMBackend(config, debug_dir=debug_dir)
