#!/usr/bin/env python3
"""Core strict metrics plus relaxed diagnostics for graph evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .diagnostics import build_relaxed_diagnostics
from .matching import concept_anchor_pairs


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
        provenance = set(node.get("provenance_evidence_ids", []) or [])
        if provenance and not (provenance & doc_ids):
            continue
        label = normalize_step_label(str(node.get("label", "")).strip(), doc_ids)
        if not label:
            continue
        parent_anchor = str(node.get("parent_anchor") or "").strip()
        node_type = str(node.get("node_type") or "").strip()
        if node_type == "backbone_concept":
            concepts[label] = label
        elif parent_anchor:
            concepts[label] = parent_anchor
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
        provenance = set(edge.get("provenance_evidence_ids", []) or [])
        if provenance and not (provenance & doc_ids):
            continue
        head = normalize_step_label(str(edge.get("head", "")).strip(), doc_ids)
        relation = str(edge.get("label", "")).strip()
        tail = normalize_step_label(str(edge.get("tail", "")).strip(), doc_ids)
        family = str(edge.get("family", "")).strip()
        if head and relation and tail and family:
            relations.add((head, relation, tail, family))
    return relations


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

    payload = {
        "gold_path": str(Path(gold_path).resolve()),
        "graph_path": str(Path(graph_path).resolve()),
        "documents": sorted(doc_ids),
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
