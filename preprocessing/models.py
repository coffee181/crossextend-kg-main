#!/usr/bin/env python3
"""Preprocessing data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

try:
    from crossextend_kg.config import LLMBackendConfig
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import LLMBackendConfig


class DocumentInput(BaseModel):
    doc_id: str
    doc_type: str  # active corpus: om_manual
    domain_id: str
    role: Literal["target"] = "target"
    title: str = ""
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = ""


class ExtractionResult(BaseModel):
    doc_id: str
    concepts: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    extraction_quality: str = "unknown"
    llm_model: str = ""
    processing_time_ms: int = 0


class PreprocessingConfig(BaseModel):
    data_root: str
    domain_ids: list[str] = Field(default_factory=lambda: ["battery", "cnc", "nev"])
    output_path: str
    role: Literal["target"] = "target"
    prompt_template_path: str = Field(
        default_factory=lambda: str(
            (
                Path(__file__).resolve().parent.parent
                / "config"
                / "prompts"
                / "preprocessing_extraction_om.txt"
            ).resolve()
        )
    )
    llm: LLMBackendConfig = Field(
        default_factory=lambda: LLMBackendConfig(
            base_url="https://api.deepseek.com",
            api_key="",
            model="deepseek-chat",
            timeout_sec=600,
            max_tokens=4096,
            temperature=0.1,
        )
    )
    batch_size: int = 5
    relation_families: list[str] = Field(
        default_factory=lambda: [
            "task_dependency",
            "communication",
            "propagation",
            "lifecycle",
            "structural",
        ]
    )
    backbone_concepts: list[str] = Field(
        default_factory=lambda: [
            "Asset",
            "Component",
            "Task",
            "Signal",
            "State",
            "Fault",
        ]
    )

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_llm_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "llm" in data:
            return data
        if not any(key.startswith("llm_") for key in data):
            return data

        payload = dict(data)
        payload["llm"] = {
            "provider": payload.pop("llm_provider", None),
            "host": payload.pop("llm_host", None),
            "base_url": payload.pop("llm_base_url", ""),
            "api_key": payload.pop("llm_api_key", ""),
            "model": payload.pop("llm_model", "deepseek-chat"),
            "timeout_sec": payload.pop("llm_timeout_sec", 600),
            "max_tokens": payload.pop("llm_max_tokens", 4096),
            "temperature": payload.pop("llm_temperature", 0.1),
        }
        return payload


class PreprocessingResult(BaseModel):
    config_path: str
    data_root: str
    output_path: str
    domain_output_paths: dict[str, str] = Field(default_factory=dict)
    domain_ids: list[str]
    total_docs: int
    successful_docs: int
    failed_docs: int
    evidence_records_path: str
    processing_time_sec: float
    domain_stats: dict[str, dict[str, int]] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
