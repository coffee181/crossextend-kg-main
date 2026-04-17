#!/usr/bin/env python3
"""Relation type validation for CrossExtend-KG.

This module validates whether edges conform to the semantic constraints
defined in relation_constraints.json. Invalid edges are filtered out
during graph assembly.

Semantic constraints ensure:
- propagation: Only Fault/Signal/State/Process/Component can cause Fault/Signal/State
- structural: Only Asset/Component can have hierarchical relationships
- task_dependency: Only Task/Process/Actor can execute and produce results
- communication: Only Component/Signal/Process can send/monitor signals
- lifecycle: Only Asset/Component/Fault/State can experience state changes
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_relation_constraints(config_path: str | Path) -> dict:
    """Load relation constraints from JSON config file.

    Args:
        config_path: Path to relation_constraints.json

    Returns:
        Dictionary with constraint definitions for each family
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Relation constraints config not found: {config_path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    # Filter out metadata keys (starting with _ or $, and 'description')
    constraints = {}
    for key, value in data.items():
        if not key.startswith("_") and not key.startswith("$") and key != "description":
            constraints[key] = value

    return constraints


def validate_edge(
    edge: dict,
    node_types: dict[str, str],
    constraints: dict
) -> tuple[bool, str | None]:
    """Validate a single edge against type constraints.

    Args:
        edge: Edge dict with family, head, tail fields
        node_types: Dict mapping node label -> parent_anchor (type)
        constraints: Constraint config from load_relation_constraints

    Returns:
        (is_valid, reason) - reason is None if valid, or explanation if invalid
    """
    family = edge.get("family")
    head_label = edge.get("head")
    tail_label = edge.get("tail")

    # Check if family is defined
    constraint = constraints.get(family)
    if not constraint:
        return False, f"family '{family}' not defined in constraints"

    # Get node types
    head_type = node_types.get(head_label, "Unknown")
    tail_type = node_types.get(tail_label, "Unknown")

    # Check head type
    allowed_head_types = constraint.get("allowed_head_types", [])
    if head_type not in allowed_head_types:
        return False, f"head type '{head_type}' not allowed for family '{family}' (allowed: {allowed_head_types})"

    # Check tail type
    allowed_tail_types = constraint.get("allowed_tail_types", [])
    if tail_type not in allowed_tail_types:
        return False, f"tail type '{tail_type}' not allowed for family '{family}' (allowed: {allowed_tail_types})"

    return True, None


def filter_invalid_edges(
    edges: list[dict],
    concepts: list[dict],
    constraints: dict
) -> tuple[list[dict], list[dict], dict[str, Any]]:
    """Filter edges that violate type constraints.

    Args:
        edges: List of edge dicts
        concepts: List of concept dicts (for type lookup)
        constraints: Constraint config

    Returns:
        (valid_edges, invalid_edges, stats)
    """
    # Build node type lookup
    node_types = {}
    for concept in concepts:
        label = concept.get("label")
        parent_anchor = concept.get("parent_anchor", "Unknown")
        if label:
            node_types[label] = parent_anchor

    valid_edges = []
    invalid_edges = []

    for edge in edges:
        is_valid, reason = validate_edge(edge, node_types, constraints)
        if is_valid:
            valid_edges.append(edge)
        else:
            # Attach reason to invalid edge for reporting
            invalid_edge_with_reason = {
                **edge,
                "validation_reason": reason
            }
            invalid_edges.append(invalid_edge_with_reason)

    # Compute stats
    total = len(edges)
    invalid_count = len(invalid_edges)
    invalid_rate = invalid_count / total if total > 0 else 0

    invalid_by_family = Counter()
    invalid_reasons = []
    for edge in invalid_edges:
        family = edge.get("family")
        invalid_by_family[family] += 1
        reason = edge.get("validation_reason")
        if reason:
            invalid_reasons.append({
                "edge_id": edge.get("edge_id"),
                "family": family,
                "head": edge.get("head"),
                "tail": edge.get("tail"),
                "reason": reason
            })

    stats = {
        "total_edges": total,
        "valid_edges": len(valid_edges),
        "invalid_edges": invalid_count,
        "invalid_rate": round(invalid_rate, 4),
        "invalid_by_family": dict(invalid_by_family),
        "invalid_examples": invalid_reasons[:10]  # Top 10 examples
    }

    return valid_edges, invalid_edges, stats


def get_default_constraints_path() -> str:
    """Return default path to relation_constraints.json."""
    return "config/persistent/relation_constraints.json"
