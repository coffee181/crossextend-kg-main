"""Draft-only direct LLM baseline helper.

Sends the full document to an LLM with a single prompt requesting direct
KG extraction (entities + relations), bypassing the multi-stage pipeline.
This module is not wired into the current paper-facing baseline suite.
"""

from __future__ import annotations

from typing import Any

try:
    from crossextend_kg.models import (
        GraphEdge,
        GraphNode,
    )
except ImportError:
    from models import (
        GraphEdge,
        GraphNode,
    )


BASELINE_SPEC: dict[str, Any] = {
    "variant_id": "chatgpt_direct",
    "description": "Single-prompt LLM direct KG extraction without multi-stage pipeline",
    "component": "baseline",
    "mode": "reference",
    "preprocessing_source": "llm_direct",
    "attachment_source": "none",
    "uses_llm_preprocessing": True,
    "uses_llm_attachment": False,
    "paper_table": False,
}

DIRECT_EXTRACTION_PROMPT = """You are an expert in industrial O&M knowledge graph construction.

Given the following O&M document, extract ALL entities (components, assets, signals, states, faults, tasks/steps) and ALL relations between them.

For each entity, provide:
- label: the entity name
- type: one of Asset, Component, Signal, State, Fault, Task, Process

For each relation, provide:
- head: source entity label
- relation: relation name
- tail: target entity label
- family: one of structural, lifecycle, task_dependency, communication, propagation

Document:
{document_text}

Respond in JSON format with two arrays: "entities" and "relations".
"""


def build_direct_extraction_prompt(document_text: str) -> str:
    """Build the single-prompt extraction request."""
    return DIRECT_EXTRACTION_PROMPT.format(document_text=document_text)


def parse_direct_extraction_response(
    response_text: str,
    domain_id: str,
    doc_id: str,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Parse LLM response into graph nodes and edges.

    Falls back gracefully if the response is malformed.
    """
    import json
    import re

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # Try to extract JSON from the response
    json_match = re.search(r"\{[\s\S]*\}", response_text)
    if not json_match:
        return nodes, edges

    try:
        payload = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return nodes, edges

    entity_type_to_anchor = {
        "Asset": "Asset",
        "Component": "Component",
        "Signal": "Signal",
        "State": "State",
        "Fault": "Fault",
        "Task": "Task",
        "Process": "Process",
    }

    seen_labels: set[str] = set()
    for i, entity in enumerate(payload.get("entities", []), start=1):
        label = str(entity.get("label", "")).strip()
        etype = str(entity.get("type", "Component")).strip()
        if not label or label in seen_labels:
            continue
        seen_labels.add(label)
        nodes.append(
            GraphNode(
                node_id=f"{domain_id}::direct::node::{i:04d}",
                label=label,
                domain_id=domain_id,
                node_type="adapter_concept",
                parent_anchor=entity_type_to_anchor.get(etype, "Component"),
                surface_form=label,
                provenance_evidence_ids=[doc_id],
            )
        )

    for i, rel in enumerate(payload.get("relations", []), start=1):
        head = str(rel.get("head", "")).strip()
        relation = str(rel.get("relation", "")).strip()
        tail = str(rel.get("tail", "")).strip()
        family = str(rel.get("family", "lifecycle")).strip()
        if head and relation and tail and head in seen_labels and tail in seen_labels:
            edges.append(
                GraphEdge(
                    edge_id=f"{domain_id}::direct::edge::{i:04d}",
                    domain_id=domain_id,
                    label=relation,
                    family=family,
                    head=head,
                    tail=tail,
                    provenance_evidence_ids=[doc_id],
                )
            )

    return nodes, edges
