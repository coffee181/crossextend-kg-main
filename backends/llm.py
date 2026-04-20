#!/usr/bin/env python3
"""LLM backends for synthetic data generation and attachment decisions."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

import openai

from .embeddings import normalize_api_base_url
from ..config import LLMBackendConfig


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
    def __init__(self, config: LLMBackendConfig) -> None:
        self.base_url = normalize_api_base_url(config.base_url)
        self.api_key = config.api_key
        self.model = config.model
        self.timeout_sec = config.timeout_sec
        self.max_tokens = config.max_tokens
        self.temperature = config.temperature
        self.max_retries = 3
        self.request_max_attempts = 2
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_sec,
            max_retries=self.max_retries,
        )


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
                    response_format={"type": "json_object"},
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
                return extract_json(_normalize_chat_content(content))
            except retryable_errors as exc:
                if attempt >= self.request_max_attempts:
                    logger.error("OpenAI API error after %d attempts: %s", attempt, exc)
                    raise
                delay_sec = min(10.0, 2.0 * attempt)
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


def build_llm_backend(config: LLMBackendConfig) -> LLMBackend:
    return ChatCompletionsLLMBackend(config)
