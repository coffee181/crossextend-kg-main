#!/usr/bin/env python3
"""Configuration models and loading utilities for CrossExtend-KG."""

from __future__ import annotations

from copy import deepcopy
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

try:
    import yaml
except ImportError:  # pragma: no cover - dependency error is surfaced only when YAML is used
    yaml = None


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


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalize_whitespace: bool = True


class PromptConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_judge_template_path: str


class VariantConfig(BaseModel):
    variant_id: str
    description: str
    attachment_strategy: Literal["llm", "embedding_top1", "deterministic"] = "llm"
    use_embedding_routing: bool = True
    embedding_routing_mode: Literal["baseline", "contextual_rerank"] = "baseline"
    use_rule_filter: bool = True
    allow_free_form_growth: bool = False
    enable_snapshots: bool = True
    write_temporal_metadata: bool = True
    detect_lifecycle_events: bool = True
    export_artifacts: bool = True


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_root: str
    retrieval_top_k: int = Field(default=3, ge=1)
    min_relation_support_count: int = Field(default=1, ge=0)
    llm_attachment_batch_size: int = Field(default=8, ge=1)
    save_latest_summary: bool = True
    write_detailed_working_artifacts: bool = False
    write_jsonl_artifacts: bool = False
    write_graphml: bool = True
    write_graph_db_csv: bool = False
    write_property_graph_jsonl: bool = False
    enable_embedding_cache: bool = True
    embedding_cache_dir: str = ""
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
    exclude_domains: list[str] = Field(default_factory=list)

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
        if self.exclude_domains:
            excluded = set(self.exclude_domains)
            return [d for d in self.domains if d.domain_id not in excluded]
        return self.domains

    def variant_map(self) -> dict[str, VariantConfig]:
        return {variant.variant_id: variant for variant in self.variants}

    def config_for_domains(self, domain_ids: list[str]) -> "PipelineConfig":
        """Return a copy including only the specified domains."""
        selected = {d for d in domain_ids}
        filtered_domains = [d for d in self.domains if d.domain_id in selected]
        if not filtered_domains:
            raise ValueError(f"none of the requested domains exist in config: {domain_ids}")
        return self.model_copy(update={"domains": filtered_domains, "exclude_domains": []})


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


def _read_structured_file(path: Path) -> Any:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        return json.loads(text)
    if suffix in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError(
                "YAML config support requires PyYAML. Install it or use JSON configs."
            )
        payload = yaml.safe_load(text)
        return {} if payload is None else payload
    raise ValueError(f"unsupported config extension for {path}: expected .json, .yaml, or .yml")


def _merge_payloads(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = _merge_payloads(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    return deepcopy(override)


def _normalize_extends_field(value: Any, *, source_path: Path) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError(f"'extends' in {source_path} must be a string or list of strings")


def _load_raw_structured_payload(config_path: Path, seen_paths: set[Path] | None = None) -> dict[str, Any]:
    resolved_path = config_path.resolve()
    seen = set(seen_paths or set())
    if resolved_path in seen:
        cycle = " -> ".join(str(item) for item in [*seen, resolved_path])
        raise ValueError(f"cyclic config extends detected: {cycle}")

    payload = _read_structured_file(resolved_path)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise ValueError(f"config payload must be a mapping: {resolved_path}")

    merged: dict[str, Any] = {}
    for extends_item in _normalize_extends_field(payload.get("extends"), source_path=resolved_path):
        expanded_extends = _expand_env_in_string(extends_item)
        extends_path = Path(expanded_extends)
        if not extends_path.is_absolute():
            extends_path = (resolved_path.parent / extends_path).resolve()
        parent_payload = _load_raw_structured_payload(extends_path, seen | {resolved_path})
        merged = _merge_payloads(merged, parent_payload)

    current_payload = {key: value for key, value in payload.items() if key != "extends"}
    return _merge_payloads(merged, current_payload)


def _default_backend_catalog_path(base_dir: Path, filename_stem: str) -> Path | None:
    for extension in (".yaml", ".yml", ".json"):
        candidate = (base_dir / f"{filename_stem}{extension}").resolve()
        if candidate.exists():
            return candidate
    return None


def _load_backend_catalog(path: Path) -> dict[str, Any]:
    payload = _expand_env(_load_raw_structured_payload(path))
    if not isinstance(payload, dict):
        raise ValueError(f"backend catalog must be a mapping: {path}")
    backends = payload.get("backends")
    if not isinstance(backends, dict):
        raise ValueError(f"backend catalog missing 'backends' mapping: {path}")
    return payload


def _resolve_backend_reference(
    payload: dict[str, Any],
    *,
    base_dir: Path,
    section_key: str,
    backend_id_key: str,
    catalog_path_key: str,
    default_catalog_stem: str,
) -> None:
    backend_id = str(payload.get(backend_id_key, "")).strip()
    if not backend_id:
        return

    catalog_path_value = payload.get(catalog_path_key)
    if catalog_path_value:
        catalog_path = Path(str(catalog_path_value))
        if not catalog_path.is_absolute():
            catalog_path = (base_dir / catalog_path).resolve()
    else:
        catalog_path = _default_backend_catalog_path(base_dir, default_catalog_stem)
        if catalog_path is None:
            raise FileNotFoundError(
                f"could not resolve backend catalog for {backend_id_key} under {base_dir}"
            )

    catalog = _load_backend_catalog(catalog_path)
    backends = catalog["backends"]
    if backend_id not in backends:
        available = ", ".join(sorted(backends))
        raise KeyError(
            f"unknown backend id '{backend_id}' in {catalog_path}; available backends: {available}"
        )

    existing_section = payload.get(section_key, {})
    if existing_section is None:
        existing_section = {}
    if not isinstance(existing_section, dict):
        raise ValueError(f"'{section_key}' must be a mapping when {backend_id_key} is used")

    payload[section_key] = _merge_payloads(backends[backend_id], existing_section)


def load_structured_config_payload(config_path: str | Path) -> tuple[Path, dict[str, Any]]:
    path = Path(config_path).resolve()
    payload = _expand_env(_load_raw_structured_payload(path))
    _resolve_backend_reference(
        payload,
        base_dir=path.parent,
        section_key="llm",
        backend_id_key="llm_backend_id",
        catalog_path_key="llm_backend_catalog_path",
        default_catalog_stem="llm_backends",
    )
    _resolve_backend_reference(
        payload,
        base_dir=path.parent,
        section_key="embedding",
        backend_id_key="embedding_backend_id",
        catalog_path_key="embedding_backend_catalog_path",
        default_catalog_stem="embedding_backends",
    )
    for meta_key in (
        "llm_backend_id",
        "llm_backend_catalog_path",
        "embedding_backend_id",
        "embedding_backend_catalog_path",
    ):
        payload.pop(meta_key, None)
    return path, payload


def resolve_pipeline_payload_paths(payload: dict[str, Any], *, base_dir: Path) -> dict[str, Any]:
    resolved = deepcopy(payload)
    prompts = resolved.get("prompts")
    if isinstance(prompts, dict):
        prompts["attachment_judge_template_path"] = _resolve_path(
            base_dir,
            prompts.get("attachment_judge_template_path"),
        )

    runtime = resolved.get("runtime")
    if isinstance(runtime, dict):
        runtime["artifact_root"] = _resolve_path(base_dir, runtime.get("artifact_root"))
        runtime["embedding_cache_dir"] = _resolve_path(
            base_dir,
            runtime.get("embedding_cache_dir"),
        )
        runtime["relation_constraints_path"] = _resolve_path(
            base_dir,
            runtime.get("relation_constraints_path"),
        )

    for domain in resolved.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain["data_path"] = _resolve_path(base_dir, domain.get("data_path"))
        domain["ontology_seed_path"] = _resolve_path(base_dir, domain.get("ontology_seed_path"))
    return resolved


def resolve_preprocessing_payload_paths(payload: dict[str, Any], *, base_dir: Path) -> dict[str, Any]:
    resolved = deepcopy(payload)
    if "data_root" in resolved:
        resolved["data_root"] = _resolve_path(base_dir, resolved.get("data_root"))
    if "output_path" in resolved:
        resolved["output_path"] = _resolve_path(base_dir, resolved.get("output_path"))
    if "prompt_template_path" in resolved:
        resolved["prompt_template_path"] = _resolve_path(base_dir, resolved.get("prompt_template_path"))
    return resolved


def load_pipeline_config(config_path: str | Path) -> PipelineConfig:
    path, payload = load_structured_config_payload(config_path)
    payload = resolve_pipeline_payload_paths(payload, base_dir=path.parent)
    config = PipelineConfig.model_validate(payload)
    return config
