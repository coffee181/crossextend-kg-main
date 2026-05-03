#!/usr/bin/env python3
"""Preprocessing data models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

try:
    from crossextend_kg.config import LLMBackendConfig, resolve_backend_config
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import LLMBackendConfig, resolve_backend_config


_PERSISTENT_CONFIG_DIR = (Path(__file__).resolve().parent.parent / "config" / "persistent").resolve()


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
    state_transitions: list[dict[str, Any]] = Field(default_factory=list)
    diagnostic_edges: list[dict[str, Any]] = Field(default_factory=list)
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
    llm: LLMBackendConfig
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
            "Signal",
            "State",
            "Fault",
            "Seal",
            "Connector",
            "Sensor",
            "Controller",
            "Coolant",
            "Actuator",
            "Power",
            "Housing",
            "Fastener",
            "Media",
        ]
    )

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_llm_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        if "llm" not in payload and any(key.startswith("llm_") for key in payload):
            payload["llm"] = {
                "provider": payload.pop("llm_provider", None),
                "host": payload.pop("llm_host", None),
                "base_url": payload.pop("llm_base_url", ""),
                "api_key": payload.pop("llm_api_key", ""),
                "model": payload.pop("llm_model", ""),
                "timeout_sec": payload.pop("llm_timeout_sec", 600),
                "max_tokens": payload.pop("llm_max_tokens", 4096),
                "temperature": payload.pop("llm_temperature", 0.1),
            }

        llm_payload = payload.get("llm")
        if llm_payload is not None and not isinstance(llm_payload, dict):
            return payload

        llm_mapping = dict(llm_payload or {})
        needs_backend_defaults = not llm_mapping.get("base_url") or not llm_mapping.get("model")
        if needs_backend_defaults or payload.get("llm_backend_id") or payload.get("llm_backend_catalog_path"):
            payload["llm"] = resolve_backend_config(
                llm_mapping,
                base_dir=_PERSISTENT_CONFIG_DIR,
                section_key="llm",
                backend_id_key="llm_backend_id",
                default_catalog_stem="llm_backends",
                backend_id=str(payload.get("llm_backend_id", "")).strip() or None,
                catalog_path_value=payload.get("llm_backend_catalog_path"),
                use_default_backend=needs_backend_defaults,
            )
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
