#!/usr/bin/env python3
"""Ablation variant specifications and metadata."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_SPEC_METADATA_KEYS: tuple[str, ...] = (
    "variant_id",
    "description",
    "component",
    "mode",
    "paper_table",
    "implemented",
    "preprocessing_source",
    "attachment_source",
    "uses_llm_preprocessing",
    "uses_llm_attachment",
    "notes",
    "alias_for",
)


DEFAULT_ABLATION_SPECS: list[dict[str, Any]] = [
    {
        "variant_id": "full_llm",
        "description": "Main pipeline with LLM preprocessing, LLM attachment, and rule filtering",
        "component": "full_system",
        "mode": "baseline",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Main paper-facing pipeline.",
        "updates": {},
    },
    {
        "variant_id": "no_preprocessing_llm",
        "description": "Rule-based preprocessing with LLM attachment, keeping downstream routing and filtering active",
        "component": "preprocessing_source",
        "mode": "replace",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "rule",
        "attachment_source": "llm",
        "uses_llm_preprocessing": False,
        "uses_llm_attachment": True,
        "notes": "Primary control for preprocessing-stage LLM contribution while preserving downstream attachment semantics.",
        "updates": {},
    },
    {
        "variant_id": "no_rule_filter",
        "description": "LLM preprocessing and LLM attachment without downstream rule filtering",
        "component": "rule_filter",
        "mode": "remove",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Measures quality-control contribution from the explicit filtering layer.",
        "updates": {"use_rule_filter": False},
    },
    {
        "variant_id": "no_embedding_routing",
        "description": "LLM preprocessing and LLM attachment without embedding retrieval",
        "component": "embedding_routing",
        "mode": "remove",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Attachment remains LLM-based; only retrieval proposals are removed.",
        "updates": {"use_embedding_routing": False},
    },
    {
        "variant_id": "no_attachment_llm",
        "description": "LLM preprocessing with deterministic attachment instead of LLM attachment",
        "component": "attachment_strategy",
        "mode": "replace",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "deterministic",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": False,
        "notes": "Primary control for attachment-stage LLM contribution.",
        "updates": {"attachment_strategy": "deterministic", "use_embedding_routing": True},
    },
    {
        "variant_id": "embedding_top1",
        "description": "LLM preprocessing with embedding top-1 routing instead of LLM attachment",
        "component": "attachment_strategy",
        "mode": "replace",
        "paper_table": True,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "embedding_top1",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": False,
        "notes": "Keeps embedding anchor proposals but removes attachment-stage LLM reasoning.",
        "updates": {"attachment_strategy": "embedding_top1", "use_embedding_routing": True},
    },
    # ---- Temporal ablations ----
    {
        "variant_id": "no_snapshots",
        "description": "Pipeline with snapshot creation disabled",
        "component": "temporal",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only temporal ablation; not part of the current paper table.",
        "updates": {
            "enable_snapshots": False,
            "write_temporal_metadata": False,
            "detect_lifecycle_events": False,
        },
    },
    {
        "variant_id": "no_temporal_metadata",
        "description": "Graph constructed without valid_from/valid_to temporal metadata on nodes and edges",
        "component": "temporal",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only temporal ablation; not part of the current paper table.",
        "updates": {"write_temporal_metadata": False},
    },
    {
        "variant_id": "no_lifecycle_events",
        "description": "Pipeline with lifecycle event detection disabled",
        "component": "temporal",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only temporal ablation; not part of the current paper table.",
        "updates": {"detect_lifecycle_events": False},
    },
    # ---- Dependency/propagation ablations ----
    {
        "variant_id": "no_relation_constraints",
        "description": "Disable relation type constraints during graph assembly",
        "component": "dependency",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only dependency ablation; not part of the current paper table.",
        "updates": {},
        "payload_updates": {"runtime": {"enable_relation_validation": False}},
    },
    {
        "variant_id": "no_propagation_family",
        "description": "Remove propagation relation family from accepted families",
        "component": "dependency",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only dependency ablation; not part of the current paper table.",
        "updates": {},
        "payload_updates": {
            "relations": {
                "relation_families": [
                    "task_dependency",
                    "communication",
                    "lifecycle",
                    "structural",
                ]
            }
        },
    },
    {
        "variant_id": "no_communication_family",
        "description": "Remove communication relation family from accepted families",
        "component": "dependency",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only dependency ablation; not part of the current paper table.",
        "updates": {},
        "payload_updates": {
            "relations": {
                "relation_families": [
                    "task_dependency",
                    "propagation",
                    "lifecycle",
                    "structural",
                ]
            }
        },
    },
    {
        "variant_id": "no_structural_family",
        "description": "Remove structural relation family from accepted families",
        "component": "dependency",
        "mode": "remove",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "llm",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": True,
        "notes": "Diagnostic-only dependency ablation; not part of the current paper table.",
        "updates": {},
        "payload_updates": {
            "relations": {
                "relation_families": [
                    "task_dependency",
                    "communication",
                    "propagation",
                    "lifecycle",
                ]
            }
        },
    },
]


DEBUG_ABLATION_ALIAS_SPECS: list[dict[str, Any]] = [
    {
        "variant_id": "deterministic",
        "description": "Debug alias for no_attachment_llm",
        "component": "attachment_strategy",
        "mode": "alias",
        "paper_table": False,
        "implemented": True,
        "preprocessing_source": "llm",
        "attachment_source": "deterministic",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": False,
        "notes": "Kept only for backward-compatible debugging; do not use in the paper main table.",
        "alias_for": "no_attachment_llm",
        "updates": {"attachment_strategy": "deterministic", "use_embedding_routing": True},
    }
]


def list_ablation_specs(
    *,
    include_debug_aliases: bool = False,
    paper_facing_only: bool = False,
    include_unimplemented: bool = True,
) -> list[dict[str, Any]]:
    specs = [deepcopy(spec) for spec in DEFAULT_ABLATION_SPECS]
    if include_debug_aliases:
        specs.extend(deepcopy(spec) for spec in DEBUG_ABLATION_ALIAS_SPECS)
    if paper_facing_only:
        specs = [spec for spec in specs if spec.get("paper_table", True)]
    if not include_unimplemented:
        specs = [spec for spec in specs if spec.get("implemented", True)]
    return specs


def ablation_spec_index(
    *,
    include_debug_aliases: bool = False,
    paper_facing_only: bool = False,
    include_unimplemented: bool = True,
) -> dict[str, dict[str, Any]]:
    return {
        spec["variant_id"]: spec
        for spec in list_ablation_specs(
            include_debug_aliases=include_debug_aliases,
            paper_facing_only=paper_facing_only,
            include_unimplemented=include_unimplemented,
        )
    }


def ablation_variant_metadata(spec: dict[str, Any]) -> dict[str, Any]:
    return {key: spec[key] for key in _SPEC_METADATA_KEYS if key in spec}


def build_default_ablation_variants(
    base_variant: dict[str, Any],
    *,
    include_debug_aliases: bool = False,
    paper_facing_only: bool = True,
    include_unimplemented: bool = False,
) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for spec in list_ablation_specs(
        include_debug_aliases=include_debug_aliases,
        paper_facing_only=paper_facing_only,
        include_unimplemented=include_unimplemented,
    ):
        item = deepcopy(base_variant)
        item["variant_id"] = spec["variant_id"]
        item["description"] = spec["description"]
        item.update(spec["updates"])
        variants.append(item)
    return variants
