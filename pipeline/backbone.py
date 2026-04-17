#!/usr/bin/env python3
"""Backbone construction logic for CrossExtend-KG."""

from __future__ import annotations

from ..config import PipelineConfig
from ..io import read_json


def _load_curated_backbone_concepts(path: str | None) -> dict[str, str]:
    if not path:
        return {}
    payload = read_json(path)
    items = payload.get("concepts", payload) if isinstance(payload, dict) else payload
    concept_map: dict[str, str] = {}
    if isinstance(items, dict):
        for label, description in items.items():
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"invalid curated backbone label in {path}")
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"invalid curated backbone description for {label} in {path}")
            concept_map[label.strip()] = description.strip()
        return concept_map
    if not isinstance(items, list):
        raise ValueError(f"unsupported ontology_seed_path payload in {path}: expected list or mapping")
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            label = item.strip()
            description = label
        elif isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            description = str(item.get("description", "")).strip() or label
        else:
            raise ValueError(f"invalid curated backbone entry #{index} in {path}")
        if not label:
            raise ValueError(f"missing curated backbone label in {path} entry #{index}")
        concept_map[label] = description
    return concept_map


def build_backbone(
    config: PipelineConfig,
) -> tuple[list[str], dict[str, str], list[str]]:
    """Build the predefined backbone plus any explicit curated supplements."""

    backbone_concepts = list(config.backbone.seed_concepts)
    backbone_descriptions = dict(config.backbone.seed_descriptions)
    curated_backbone_concepts: list[str] = []

    for domain in config.all_domains():
        curated_concepts = _load_curated_backbone_concepts(domain.ontology_seed_path)
        for label, description in curated_concepts.items():
            if label in backbone_descriptions:
                continue
            backbone_concepts.append(label)
            backbone_descriptions[label] = description
            curated_backbone_concepts.append(label)

    return (
        backbone_concepts,
        backbone_descriptions,
        curated_backbone_concepts,
    )
