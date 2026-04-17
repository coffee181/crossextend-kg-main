#!/usr/bin/env python3
"""Configuration models and loading utilities for CrossExtend-KG."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _normalize_api_base_url(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    if not normalized.startswith("http://") and not normalized.startswith("https://"):
        normalized = f"http://{normalized}"
    if "0.0.0.0" in normalized:
        normalized = normalized.replace("0.0.0.0", "127.0.0.1")
    return normalized.rstrip("/")


class LLMBackendConfig(BaseModel):
    provider: str | None = None
    base_url: str = ""
    host: str | None = None
    api_key: str = ""
    model: str = ""
    timeout_sec: int = Field(default=120, ge=1)
    max_tokens: int = Field(default=1200, ge=1)
    temperature: float = Field(default=0.1, ge=0.0)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            payload = dict(data)
            if not payload.get("base_url") and payload.get("host"):
                payload["base_url"] = payload["host"]
            return payload
        return data

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "LLMBackendConfig":
        self.base_url = _normalize_api_base_url(self.base_url)
        if not self.base_url:
            raise ValueError("llm.base_url is required")
        if not self.model:
            raise ValueError("llm.model is required")
        return self


class EmbeddingBackendConfig(BaseModel):
    provider: str | None = None
    base_url: str = ""
    host: str | None = None
    api_key: str = ""
    model: str = ""
    timeout_sec: int = Field(default=120, ge=1)
    dimensions: int = Field(default=1024, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _upgrade_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            payload = dict(data)
            if not payload.get("base_url") and payload.get("host"):
                payload["base_url"] = payload["host"]
            return payload
        return data

    @model_validator(mode="after")
    def _validate_required_fields(self) -> "EmbeddingBackendConfig":
        self.base_url = _normalize_api_base_url(self.base_url)
        if not self.base_url:
            raise ValueError("embedding.base_url is required")
        if not self.model:
            raise ValueError("embedding.model is required")
        return self


class DomainConfig(BaseModel):
    domain_id: str
    domain_name: str
    role: Literal["target"] = "target"
    data_path: str
    source_types: list[str] = Field(default_factory=lambda: ["text"])
    domain_keywords: list[str] = Field(default_factory=list)
    ontology_seed_path: str | None = None


class BackbonePolicyConfig(BaseModel):
    seed_concepts: list[str]
    seed_descriptions: dict[str, str]


class RelationConfig(BaseModel):
    relation_families: list[str]
    family_descriptions: dict[str, str] = Field(default_factory=dict)
    allowed_routes: list[str] = Field(
        default_factory=lambda: [
            "reuse_backbone",
            "vertical_specialize",
            "reject",
        ]
    )

    @model_validator(mode="after")
    def _validate_allowed_routes(self) -> "RelationConfig":
        allowed = ["reuse_backbone", "vertical_specialize", "reject"]
        invalid = [route for route in self.allowed_routes if route not in allowed]
        if invalid:
            raise ValueError(
                "relations.allowed_routes may only contain reuse_backbone, vertical_specialize, reject; "
                f"found: {invalid}"
            )
        if len(self.allowed_routes) != len(set(self.allowed_routes)):
            raise ValueError("duplicate route detected in relations.allowed_routes")
        return self


class SyntheticGenerationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    output_path: str
    num_samples: int = Field(default=10, ge=1)
    domain_sample_counts: dict[str, int] = Field(default_factory=dict)


class DataConfig(BaseModel):
    synthetic_generation: SyntheticGenerationConfig
    normalize_whitespace: bool = True


class PromptConfig(BaseModel):
    attachment_judge_template_path: str
    synthetic_generator_template_path: str


class VariantConfig(BaseModel):
    variant_id: str
    description: str
    attachment_strategy: Literal["llm", "embedding_top1", "deterministic"] = "llm"
    use_embedding_routing: bool = True
    use_rule_filter: bool = True
    allow_free_form_growth: bool = False
    enable_snapshots: bool = True
    enable_memory_bank: bool = True
    export_artifacts: bool = True


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_root: str
    retrieval_top_k: int = Field(default=3, ge=1)
    llm_attachment_batch_size: int = Field(default=8, ge=1)
    enable_temporal_memory_bank: bool = True
    temporal_memory_top_k: int = Field(default=3, ge=1)
    temporal_memory_max_entries: int = Field(default=4000, ge=1)
    temporal_memory_path: str | None = None
    save_latest_summary: bool = True
    write_jsonl_artifacts: bool = True
    write_graph_db_csv: bool = True
    write_property_graph_jsonl: bool = True
    run_prefix: str = "run"
    relation_constraints_path: str | None = None
    enable_relation_validation: bool = True


class PipelineConfig(BaseModel):
    project_name: str
    benchmark_name: str
    prompts: PromptConfig
    llm: LLMBackendConfig
    embedding: EmbeddingBackendConfig
    backbone: BackbonePolicyConfig
    relations: RelationConfig
    data: DataConfig
    runtime: RuntimeConfig
    variants: list[VariantConfig]
    domains: list[DomainConfig]

    @model_validator(mode="after")
    def validate_roles(self) -> "PipelineConfig":
        if len(self.domains) < 1:
            raise ValueError("CrossExtend-KG requires at least one domain in config")
        if not self.variants:
            raise ValueError("At least one pipeline variant must be configured")
        domain_ids = [domain.domain_id for domain in self.domains]
        if len(domain_ids) != len(set(domain_ids)):
            raise ValueError("duplicate domain_id detected in config")
        variant_ids = [variant.variant_id for variant in self.variants]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("duplicate variant_id detected in config")
        missing_seed_descriptions = sorted(set(self.backbone.seed_concepts) - set(self.backbone.seed_descriptions))
        if missing_seed_descriptions:
            raise ValueError("missing backbone seed descriptions for: " + ", ".join(missing_seed_descriptions))
        return self

    def all_domains(self) -> list[DomainConfig]:
        return self.domains

    def variant_map(self) -> dict[str, VariantConfig]:
        return {variant.variant_id: variant for variant in self.variants}


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def _expand_env_in_string(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        default = match.group(2)
        if env_name in os.environ:
            return os.environ[env_name]
        return default or ""

    return _ENV_PATTERN.sub(replace, value)


def _expand_env(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _expand_env(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_expand_env(item) for item in payload]
    if isinstance(payload, str):
        return _expand_env_in_string(payload)
    return payload


def _resolve_path(base_dir: Path, value: str | None) -> str | None:
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((base_dir / path).resolve())


def load_pipeline_config(config_path: str | Path) -> PipelineConfig:
    path = Path(config_path).resolve()
    payload = _expand_env(json.loads(path.read_text(encoding="utf-8")))
    config = PipelineConfig.model_validate(payload)
    base_dir = path.parent

    config.prompts.attachment_judge_template_path = _resolve_path(base_dir, config.prompts.attachment_judge_template_path) or ""
    config.prompts.synthetic_generator_template_path = _resolve_path(base_dir, config.prompts.synthetic_generator_template_path) or ""
    config.runtime.artifact_root = _resolve_path(base_dir, config.runtime.artifact_root) or ""
    config.runtime.temporal_memory_path = _resolve_path(base_dir, config.runtime.temporal_memory_path)
    config.runtime.relation_constraints_path = _resolve_path(base_dir, config.runtime.relation_constraints_path)
    config.data.synthetic_generation.output_path = _resolve_path(base_dir, config.data.synthetic_generation.output_path) or ""

    for domain in config.domains:
        domain.data_path = _resolve_path(base_dir, domain.data_path) or ""
        domain.ontology_seed_path = _resolve_path(base_dir, domain.ontology_seed_path)
    return config
