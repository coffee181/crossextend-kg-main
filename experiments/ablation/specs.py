#!/usr/bin/env python3
"""Ablation variant specifications."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_ABLATION_SPECS: list[dict[str, Any]] = [
    {
        "variant_id": "full_llm",
        "description": "Main pipeline with LLM attachment, embedding routing, rule filtering, and memory bank",
        "component": "full_system",
        "mode": "baseline",
        "updates": {},
    },
    {
        "variant_id": "no_memory_bank",
        "description": "Ablation without temporal memory bank",
        "component": "memory_bank",
        "mode": "remove",
        "updates": {"enable_memory_bank": False},
    },
    {
        "variant_id": "no_rule_filter",
        "description": "Ablation without rule filtering",
        "component": "rule_filter",
        "mode": "remove",
        "updates": {"use_rule_filter": False},
    },
    {
        "variant_id": "no_embedding_routing",
        "description": "Ablation without embedding routing",
        "component": "embedding_routing",
        "mode": "remove",
        "updates": {"use_embedding_routing": False},
    },
    {
        "variant_id": "embedding_top1",
        "description": "Embedding top-1 routing without LLM attachment",
        "component": "attachment_strategy",
        "mode": "replace",
        "updates": {"attachment_strategy": "embedding_top1", "use_embedding_routing": True},
    },
    {
        "variant_id": "deterministic",
        "description": "Deterministic routing with embedding anchor proposal",
        "component": "attachment_strategy",
        "mode": "replace",
        "updates": {"attachment_strategy": "deterministic", "use_embedding_routing": True},
    },
]


def build_default_ablation_variants(base_variant: dict[str, Any]) -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = []
    for spec in DEFAULT_ABLATION_SPECS:
        item = deepcopy(base_variant)
        item["variant_id"] = spec["variant_id"]
        item["description"] = spec["description"]
        item.update(spec["updates"])
        variants.append(item)
    return variants
