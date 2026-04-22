#!/usr/bin/env python3
"""Core strict metrics plus relaxed diagnostics for graph evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from experiments.metrics.diagnostics import build_relaxed_diagnostics
from experiments.metrics.matching import canonical_concept_anchor_pairs, concept_anchor_pairs, normalize_label_set


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def normalize_step_label(label: str, doc_ids: set[str]) -> str:
    compact = str(label).strip()
    for doc_id in doc_ids:
        prefix = f"{doc_id}:"
        if compact.startswith(prefix):
            tail = compact[len(prefix) :]
            if tail.startswith("T"):
                return tail
    return compact


def _is_step_label(label: str) -> bool:
    compact = str(label).strip()
    return len(compact) >= 2 and compact.startswith("T") and compact[1:].isdigit()


def _node_in_scope(node: dict[str, Any], doc_ids: set[str]) -> bool:
    provenance = set(node.get("provenance_evidence_ids", []) or [])
    return not provenance or bool(provenance & doc_ids)


def _edge_in_scope(edge: dict[str, Any], doc_ids: set[str]) -> bool:
    provenance = set(edge.get("provenance_evidence_ids", []) or [])
    return not provenance or bool(provenance & doc_ids)


def _is_workflow_step_node(node: dict[str, Any], doc_ids: set[str]) -> bool:
    node_type = str(node.get("node_type") or "").strip()
    node_layer = str(node.get("node_layer") or "").strip()
    step_id = str(node.get("step_id") or "").strip()
    label = normalize_step_label(str(node.get("label", "")).strip(), doc_ids)
    parent_anchor = str(node.get("parent_anchor") or "").strip()
    if node_type == "workflow_step" or node_layer == "workflow" or _is_step_label(step_id):
        return True
    return parent_anchor == "Task" and _is_step_label(label)


def _legacy_projected_anchor(node: dict[str, Any], label: str, doc_ids: set[str]) -> str | None:
    if _is_workflow_step_node(node, doc_ids):
        return "Task"
    node_type = str(node.get("node_type") or "").strip()
    parent_anchor = str(node.get("parent_anchor") or "").strip()
    if node_type == "backbone_concept":
        return label
    if parent_anchor:
        return parent_anchor
    return None


def set_metrics(predicted: set[Any], gold: set[Any]) -> dict[str, Any]:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1_score(precision, recall), 4),
    }


def classification_metrics(
    predicted_by_label: dict[str, str],
    gold_by_label: dict[str, str],
) -> dict[str, Any]:
    shared_labels = sorted(set(predicted_by_label) & set(gold_by_label))
    if not shared_labels:
        return {
            "support": 0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "predicted_labels": len(predicted_by_label),
            "gold_labels": len(gold_by_label),
        }

    correct = sum(1 for label in shared_labels if predicted_by_label[label] == gold_by_label[label])
    classes = sorted({gold_by_label[label] for label in shared_labels} | {predicted_by_label[label] for label in shared_labels})
    class_f1_scores: list[float] = []
    for cls in classes:
        tp = sum(1 for label in shared_labels if predicted_by_label[label] == cls and gold_by_label[label] == cls)
        fp = sum(1 for label in shared_labels if predicted_by_label[label] == cls and gold_by_label[label] != cls)
        fn = sum(1 for label in shared_labels if predicted_by_label[label] != cls and gold_by_label[label] == cls)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        class_f1_scores.append(f1_score(precision, recall))

    return {
        "support": len(shared_labels),
        "accuracy": round(safe_div(correct, len(shared_labels)), 4),
        "macro_f1": round(safe_div(sum(class_f1_scores), len(class_f1_scores)), 4),
        "predicted_labels": len(predicted_by_label),
        "gold_labels": len(gold_by_label),
    }


def resolve_gold_file(
    domain_id: str,
    evidence_id: str | None = None,
    ground_truth_dir: str | Path | None = None,
) -> Path:
    root = Path(ground_truth_dir) if ground_truth_dir else Path(__file__).resolve().parents[2] / "data" / "ground_truth"
    if evidence_id:
        candidate = root / f"{domain_id}_{evidence_id}.json"
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"gold file not found for {domain_id}/{evidence_id}: {candidate}")

    matches = sorted(root.glob(f"{domain_id}_*.json"))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"no gold files found for domain {domain_id} under {root}")
    raise ValueError(
        f"multiple gold files found for domain {domain_id} under {root}; "
        "specify evidence_id explicitly"
    )


def list_gold_files(
    ground_truth_dir: str | Path | None = None,
    domain_id: str | None = None,
) -> list[Path]:
    root = Path(ground_truth_dir) if ground_truth_dir else Path(__file__).resolve().parents[2] / "data" / "ground_truth"
    pattern = f"{domain_id}_*.json" if domain_id else "*.json"
    return sorted(root.glob(pattern))


def gold_concepts(gold_payload: dict[str, Any], doc_ids: set[str]) -> dict[str, str]:
    concepts: dict[str, str] = {}
    for item in gold_payload.get("concept_ground_truth", []):
        if not item.get("should_be_in_graph", False):
            continue
        if str(item.get("evidence_id", "")).strip() not in doc_ids:
            continue
        label = normalize_step_label(str(item.get("label", "")).strip(), doc_ids)
        anchor = str(item.get("expected_anchor", "")).strip()
        if label and anchor:
            concepts[label] = anchor
    return concepts


def predicted_concepts(graph_payload: dict[str, Any], doc_ids: set[str]) -> dict[str, str]:
    concepts: dict[str, str] = {}
    for node in graph_payload.get("nodes", []):
        if not _node_in_scope(node, doc_ids):
            continue
        label = normalize_step_label(str(node.get("label", "")).strip(), doc_ids)
        if not label:
            continue
        anchor = _legacy_projected_anchor(node, label, doc_ids)
        if anchor:
            concepts[label] = anchor
    return concepts


def gold_relations(gold_payload: dict[str, Any], doc_ids: set[str]) -> set[tuple[str, str, str, str]]:
    relations: set[tuple[str, str, str, str]] = set()
    for item in gold_payload.get("relation_ground_truth", []):
        if not item.get("valid", False):
            continue
        if str(item.get("evidence_id", "")).strip() not in doc_ids:
            continue
        head = normalize_step_label(str(item.get("head", "")).strip(), doc_ids)
        relation = str(item.get("relation", "")).strip()
        tail = normalize_step_label(str(item.get("tail", "")).strip(), doc_ids)
        family = str(item.get("family", "")).strip()
        if head and relation and tail and family:
            relations.add((head, relation, tail, family))
    return relations


def predicted_relations(graph_payload: dict[str, Any], doc_ids: set[str]) -> set[tuple[str, str, str, str]]:
    relations: set[tuple[str, str, str, str]] = set()
    for edge in graph_payload.get("edges", []):
        if not _edge_in_scope(edge, doc_ids):
            continue
        edge_layer = str(edge.get("edge_layer") or "").strip()
        workflow_kind = str(edge.get("workflow_kind") or "").strip()
        if edge_layer == "workflow" and workflow_kind != "sequence":
            continue
        head = normalize_step_label(str(edge.get("head", "")).strip(), doc_ids)
        relation = str(edge.get("label", "")).strip()
        tail = normalize_step_label(str(edge.get("tail", "")).strip(), doc_ids)
        family = str(edge.get("family", "")).strip()
        if head and relation and tail and family:
            relations.add((head, relation, tail, family))
    return relations


def gold_workflow_steps(gold_payload: dict[str, Any], doc_ids: set[str]) -> set[str]:
    return {
        normalize_step_label(str(item.get("label", "")).strip(), doc_ids)
        for item in gold_payload.get("concept_ground_truth", [])
        if item.get("should_be_in_graph", False)
        and str(item.get("evidence_id", "")).strip() in doc_ids
        and str(item.get("expected_anchor", "")).strip() == "Task"
    }


def predicted_workflow_steps(graph_payload: dict[str, Any], doc_ids: set[str]) -> set[str]:
    steps: set[str] = set()
    for node in graph_payload.get("nodes", []):
        if not _node_in_scope(node, doc_ids):
            continue
        if not _is_workflow_step_node(node, doc_ids):
            continue
        label = normalize_step_label(str(node.get("label", "")).strip(), doc_ids)
        if label:
            steps.add(label)
    return steps


def gold_workflow_sequences(gold_payload: dict[str, Any], doc_ids: set[str]) -> set[tuple[str, str, str, str]]:
    return {
        relation
        for relation in gold_relations(gold_payload, doc_ids)
        if relation[3] == "task_dependency" and _is_step_label(relation[0]) and _is_step_label(relation[2])
    }


def gold_workflow_groundings(
    gold_payload: dict[str, Any],
    doc_ids: set[str],
) -> set[tuple[str, str, str, str]] | None:
    items = gold_payload.get("workflow_relation_ground_truth")
    if not isinstance(items, list):
        return None
    relations: set[tuple[str, str, str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if not item.get("valid", False):
            continue
        if str(item.get("evidence_id", "")).strip() not in doc_ids:
            continue
        head = normalize_step_label(str(item.get("head", "")).strip(), doc_ids)
        relation = str(item.get("relation", "")).strip()
        tail = normalize_step_label(str(item.get("tail", "")).strip(), doc_ids)
        family = str(item.get("family", "")).strip()
        if head and relation and tail and family:
            relations.add((head, relation, tail, family))
    return relations


def predicted_workflow_sequences(graph_payload: dict[str, Any], doc_ids: set[str]) -> set[tuple[str, str, str, str]]:
    sequences: set[tuple[str, str, str, str]] = set()
    for edge in graph_payload.get("edges", []):
        if not _edge_in_scope(edge, doc_ids):
            continue
        edge_layer = str(edge.get("edge_layer") or "").strip()
        workflow_kind = str(edge.get("workflow_kind") or "").strip()
        head = normalize_step_label(str(edge.get("head", "")).strip(), doc_ids)
        relation = str(edge.get("label", "")).strip()
        tail = normalize_step_label(str(edge.get("tail", "")).strip(), doc_ids)
        family = str(edge.get("family", "")).strip()
        if not (head and relation and tail and family):
            continue
        is_sequence = workflow_kind == "sequence" or (
            not edge_layer and family == "task_dependency" and _is_step_label(head) and _is_step_label(tail)
        )
        if is_sequence:
            sequences.add((head, relation, tail, family))
    return sequences


def workflow_grounding_edges(graph_payload: dict[str, Any], doc_ids: set[str]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for edge in graph_payload.get("edges", []):
        if not _edge_in_scope(edge, doc_ids):
            continue
        if str(edge.get("edge_layer") or "").strip() != "workflow":
            continue
        if str(edge.get("workflow_kind") or "").strip() != "action_object":
            continue
        edges.append(
            {
                "head": normalize_step_label(str(edge.get("head", "")).strip(), doc_ids),
                "relation": str(edge.get("label", "")).strip(),
                "tail": normalize_step_label(str(edge.get("tail", "")).strip(), doc_ids),
                "family": str(edge.get("family", "")).strip(),
                "workflow_kind": "action_object",
            }
        )
    return edges


def predicted_workflow_groundings(
    graph_payload: dict[str, Any],
    doc_ids: set[str],
) -> set[tuple[str, str, str, str]]:
    return {
        (
            item["head"],
            item["relation"],
            item["tail"],
            item["family"],
        )
        for item in workflow_grounding_edges(graph_payload, doc_ids)
        if item["head"] and item["relation"] and item["tail"] and item["family"]
    }


def isolated_node_delta(graph_payload: dict[str, Any], doc_ids: set[str]) -> dict[str, Any]:
    relevant_nodes = [node for node in graph_payload.get("nodes", []) if _node_in_scope(node, doc_ids)]
    relevant_edges = [edge for edge in graph_payload.get("edges", []) if _edge_in_scope(edge, doc_ids)]
    labels = [str(node.get("label", "")).strip() for node in relevant_nodes if str(node.get("label", "")).strip()]
    all_incident = {str(edge.get("head", "")).strip() for edge in relevant_edges} | {
        str(edge.get("tail", "")).strip() for edge in relevant_edges
    }
    semantic_incident = {
        str(edge.get("head", "")).strip()
        for edge in relevant_edges
        if str(edge.get("edge_layer") or "").strip() == "semantic"
    } | {
        str(edge.get("tail", "")).strip()
        for edge in relevant_edges
        if str(edge.get("edge_layer") or "").strip() == "semantic"
    }
    total_isolated = sorted(label for label in labels if label not in all_incident)
    semantic_only_isolated = sorted(label for label in labels if label not in semantic_incident)
    workflow_connected_only = sorted(label for label in labels if label in all_incident and label not in semantic_incident)
    return {
        "full_graph_isolated_count": len(total_isolated),
        "semantic_only_isolated_count": len(semantic_only_isolated),
        "workflow_reduction_count": max(len(semantic_only_isolated) - len(total_isolated), 0),
        "workflow_connected_only_examples": [
            normalize_step_label(label, doc_ids)
            for label in workflow_connected_only[:15]
        ],
    }


def workflow_diagnostics_payload(
    gold_payload: dict[str, Any],
    graph_payload: dict[str, Any],
    doc_ids: set[str],
) -> dict[str, Any]:
    gold_steps = gold_workflow_steps(gold_payload, doc_ids)
    predicted_steps = predicted_workflow_steps(graph_payload, doc_ids)
    gold_sequences = gold_workflow_sequences(gold_payload, doc_ids)
    predicted_sequences = predicted_workflow_sequences(graph_payload, doc_ids)
    gold_groundings = gold_workflow_groundings(gold_payload, doc_ids)
    predicted_groundings = predicted_workflow_groundings(graph_payload, doc_ids)
    grounding_edges = workflow_grounding_edges(graph_payload, doc_ids)
    grounded_steps = sorted({item["head"] for item in grounding_edges if item["head"]})
    if gold_groundings is None:
        grounding_metrics = {
            "available": False,
            "tp": 0,
            "fp": 0,
            "fn": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "gold_count": 0,
            "predicted_count": len(predicted_groundings),
        }
        grounding_error_examples = {
            "missing_workflow_groundings": [],
            "extra_workflow_groundings": [],
        }
    else:
        grounding_metrics = {
            "available": True,
            **set_metrics(predicted_groundings, gold_groundings),
            "gold_count": len(gold_groundings),
            "predicted_count": len(predicted_groundings),
        }
        grounding_error_examples = {
            "missing_workflow_groundings": [
                {"head": head, "relation": relation, "tail": tail, "family": family}
                for head, relation, tail, family in sorted(gold_groundings - predicted_groundings)[:15]
            ],
            "extra_workflow_groundings": [
                {"head": head, "relation": relation, "tail": tail, "family": family}
                for head, relation, tail, family in sorted(predicted_groundings - gold_groundings)[:15]
            ],
        }

    return {
        "workflow_step_metrics": set_metrics(predicted_steps, gold_steps),
        "workflow_sequence_metrics": set_metrics(predicted_sequences, gold_sequences),
        "workflow_grounding_metrics": grounding_metrics,
        "workflow_grounding_stats": {
            "action_object_edge_count": len(grounding_edges),
            "grounded_step_count": len(grounded_steps),
            "ungrounded_step_count": max(len(predicted_steps) - len(grounded_steps), 0),
            "avg_action_object_edges_per_grounded_step": round(
                safe_div(len(grounding_edges), len(grounded_steps)),
                4,
            ),
        },
        "isolated_node_delta": isolated_node_delta(graph_payload, doc_ids),
        "workflow_edge_examples": grounding_edges[:15],
        "workflow_error_examples": grounding_error_examples,
    }


def compute_metrics(gold_path: str | Path, graph_path: str | Path) -> dict[str, Any]:
    gold_payload = read_json(gold_path)
    graph_payload = read_json(graph_path)

    doc_ids = {
        str(item.get("doc_id", "")).strip()
        for item in gold_payload.get("documents", [])
        if str(item.get("doc_id", "")).strip()
    }
    if not doc_ids:
        raise ValueError("gold file contains no document ids")

    gold_concept_map = gold_concepts(gold_payload, doc_ids)
    predicted_concept_map = predicted_concepts(graph_payload, doc_ids)
    gold_relation_set = gold_relations(gold_payload, doc_ids)
    predicted_relation_set = predicted_relations(graph_payload, doc_ids)
    gold_concept_pairs = concept_anchor_pairs(gold_concept_map)
    predicted_concept_pairs = concept_anchor_pairs(predicted_concept_map)
    gold_canonical_concept_pairs = canonical_concept_anchor_pairs(gold_concept_map)
    predicted_canonical_concept_pairs = canonical_concept_anchor_pairs(predicted_concept_map)
    gold_relaxed_labels = normalize_label_set(gold_concept_map)
    predicted_relaxed_labels = normalize_label_set(predicted_concept_map)

    payload = {
        "gold_path": str(Path(gold_path).resolve()),
        "graph_path": str(Path(graph_path).resolve()),
        "documents": sorted(doc_ids),
        "node_coverage_metrics": set_metrics(predicted_relaxed_labels, gold_relaxed_labels),
        "anchored_node_canonical_metrics": set_metrics(
            predicted_canonical_concept_pairs,
            gold_canonical_concept_pairs,
        ),
        "concept_metrics": set_metrics(predicted_concept_pairs, gold_concept_pairs),
        "concept_label_metrics": set_metrics(set(predicted_concept_map), set(gold_concept_map)),
        "anchor_metrics": classification_metrics(predicted_concept_map, gold_concept_map),
        "relation_metrics": set_metrics(predicted_relation_set, gold_relation_set),
        "predicted_counts": {
            "concepts": len(predicted_concept_map),
            "relations": len(predicted_relation_set),
        },
        "gold_counts": {
            "concepts": len(gold_concept_map),
            "relations": len(gold_relation_set),
        },
        "error_examples": {
            "missing_concepts": sorted(set(gold_concept_map) - set(predicted_concept_map))[:15],
            "extra_concepts": sorted(set(predicted_concept_map) - set(gold_concept_map))[:15],
            "missing_relations": [
                {"head": head, "relation": relation, "tail": tail, "family": family}
                for head, relation, tail, family in sorted(gold_relation_set - predicted_relation_set)[:15]
            ],
            "extra_relations": [
                {"head": head, "relation": relation, "tail": tail, "family": family}
                for head, relation, tail, family in sorted(predicted_relation_set - gold_relation_set)[:15]
            ],
            "anchor_confusions": [
                {
                    "label": label,
                    "predicted_anchor": predicted_concept_map[label],
                    "gold_anchor": gold_concept_map[label],
                }
                for label in sorted(set(predicted_concept_map) & set(gold_concept_map))
                if predicted_concept_map[label] != gold_concept_map[label]
            ][:15],
        },
    }
    payload.update(workflow_diagnostics_payload(gold_payload, graph_payload, doc_ids))
    payload.update(
        build_relaxed_diagnostics(
            predicted_concept_map=predicted_concept_map,
            gold_concept_map=gold_concept_map,
            predicted_relation_set=predicted_relation_set,
            gold_relation_set=gold_relation_set,
            set_metrics_fn=set_metrics,
        )
    )
    return payload
