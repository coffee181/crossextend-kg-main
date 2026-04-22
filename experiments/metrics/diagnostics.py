#!/usr/bin/env python3
"""Relaxed diagnostics that complement strict paper-facing metrics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from experiments.metrics.matching import (
    family_agnostic_relation_key,
    normalize_diagnostic_label,
    normalize_label_set,
    normalized_relation_key,
    token_overlap_score,
)


def _trim_examples(items: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    return items[:limit]


def concept_alias_hits(
    predicted_concept_map: dict[str, str],
    gold_concept_map: dict[str, str],
) -> list[dict[str, Any]]:
    predicted_by_norm: dict[str, list[str]] = defaultdict(list)
    gold_by_norm: dict[str, list[str]] = defaultdict(list)
    for label in predicted_concept_map:
        predicted_by_norm[normalize_diagnostic_label(label)].append(label)
    for label in gold_concept_map:
        gold_by_norm[normalize_diagnostic_label(label)].append(label)

    hits: list[dict[str, Any]] = []
    for normalized in sorted(set(predicted_by_norm) & set(gold_by_norm)):
        for predicted_label in sorted(predicted_by_norm[normalized]):
            for gold_label in sorted(gold_by_norm[normalized]):
                if predicted_label == gold_label:
                    continue
                hits.append(
                    {
                        "predicted_label": predicted_label,
                        "gold_label": gold_label,
                        "normalized_label": normalized,
                        "predicted_anchor": predicted_concept_map[predicted_label],
                        "gold_anchor": gold_concept_map[gold_label],
                        "anchor_match": predicted_concept_map[predicted_label] == gold_concept_map[gold_label],
                    }
                )
    return _trim_examples(hits)


def concept_near_misses(
    predicted_concept_map: dict[str, str],
    gold_concept_map: dict[str, str],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    exact_shared = set(predicted_concept_map) & set(gold_concept_map)
    for predicted_label, predicted_anchor in predicted_concept_map.items():
        if predicted_label in exact_shared:
            continue
        best_match: dict[str, Any] | None = None
        best_score = 0.0
        for gold_label, gold_anchor in gold_concept_map.items():
            if gold_label in exact_shared:
                continue
            score = token_overlap_score(predicted_label, gold_label)
            if score < 0.5:
                continue
            adjusted_score = score + (0.2 if predicted_anchor == gold_anchor else 0.0)
            if adjusted_score <= best_score:
                continue
            best_score = adjusted_score
            best_match = {
                "predicted_label": predicted_label,
                "gold_label": gold_label,
                "predicted_anchor": predicted_anchor,
                "gold_anchor": gold_anchor,
                "token_overlap": round(score, 4),
                "anchor_match": predicted_anchor == gold_anchor,
            }
        if best_match is not None:
            hits.append(best_match)
    hits.sort(key=lambda item: (item["token_overlap"], item["anchor_match"]), reverse=True)
    return _trim_examples(hits)


def relation_alias_hits(
    predicted_relation_set: set[tuple[str, str, str, str]],
    gold_relation_set: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    predicted_by_norm: dict[tuple[str, str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    gold_by_norm: dict[tuple[str, str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    for relation in predicted_relation_set:
        predicted_by_norm[normalized_relation_key(relation)].append(relation)
    for relation in gold_relation_set:
        gold_by_norm[normalized_relation_key(relation)].append(relation)

    hits: list[dict[str, Any]] = []
    for normalized in sorted(set(predicted_by_norm) & set(gold_by_norm)):
        for predicted_relation in sorted(predicted_by_norm[normalized]):
            for gold_relation in sorted(gold_by_norm[normalized]):
                if predicted_relation == gold_relation:
                    continue
                hits.append(
                    {
                        "predicted": {
                            "head": predicted_relation[0],
                            "relation": predicted_relation[1],
                            "tail": predicted_relation[2],
                            "family": predicted_relation[3],
                        },
                        "gold": {
                            "head": gold_relation[0],
                            "relation": gold_relation[1],
                            "tail": gold_relation[2],
                            "family": gold_relation[3],
                        },
                        "normalized_key": normalized,
                    }
                )
    return _trim_examples(hits)


def relation_family_confusions(
    predicted_relation_set: set[tuple[str, str, str, str]],
    gold_relation_set: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    predicted_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    gold_by_key: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for relation in predicted_relation_set:
        predicted_by_key[family_agnostic_relation_key(relation)].add(relation[3])
    for relation in gold_relation_set:
        gold_by_key[family_agnostic_relation_key(relation)].add(relation[3])

    confusions: list[dict[str, Any]] = []
    for key in sorted(set(predicted_by_key) & set(gold_by_key)):
        predicted_families = sorted(predicted_by_key[key])
        gold_families = sorted(gold_by_key[key])
        if predicted_families == gold_families:
            continue
        confusions.append(
            {
                "head": key[0],
                "relation": key[1],
                "tail": key[2],
                "predicted_families": predicted_families,
                "gold_families": gold_families,
            }
        )
    return _trim_examples(confusions)


def relation_target_near_misses(
    predicted_relation_set: set[tuple[str, str, str, str]],
    gold_relation_set: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    for predicted_head, predicted_relation, predicted_tail, predicted_family in sorted(predicted_relation_set):
        best_match: dict[str, Any] | None = None
        best_score = 0.0
        for gold_head, gold_relation, gold_tail, gold_family in gold_relation_set:
            if predicted_relation != gold_relation or predicted_family != gold_family:
                continue
            if normalize_diagnostic_label(predicted_head) != normalize_diagnostic_label(gold_head):
                continue
            score = token_overlap_score(predicted_tail, gold_tail)
            if score < 0.5 or score <= best_score:
                continue
            best_score = score
            best_match = {
                "predicted": {
                    "head": predicted_head,
                    "relation": predicted_relation,
                    "tail": predicted_tail,
                    "family": predicted_family,
                },
                "gold": {
                    "head": gold_head,
                    "relation": gold_relation,
                    "tail": gold_tail,
                    "family": gold_family,
                },
                "tail_token_overlap": round(score, 4),
            }
        if best_match is not None and best_match["predicted"] != best_match["gold"]:
            misses.append(best_match)
    misses.sort(key=lambda item: item["tail_token_overlap"], reverse=True)
    return _trim_examples(misses)


def build_relaxed_diagnostics(
    predicted_concept_map: dict[str, str],
    gold_concept_map: dict[str, str],
    predicted_relation_set: set[tuple[str, str, str, str]],
    gold_relation_set: set[tuple[str, str, str, str]],
    set_metrics_fn,
) -> dict[str, Any]:
    relaxed_concept_label_metrics = set_metrics_fn(
        normalize_label_set(predicted_concept_map),
        normalize_label_set(gold_concept_map),
    )
    relaxed_relation_metrics = set_metrics_fn(
        {normalized_relation_key(relation) for relation in predicted_relation_set},
        {normalized_relation_key(relation) for relation in gold_relation_set},
    )
    family_agnostic_relation_metrics = set_metrics_fn(
        {family_agnostic_relation_key(relation) for relation in predicted_relation_set},
        {family_agnostic_relation_key(relation) for relation in gold_relation_set},
    )

    return {
        "diagnostic_metrics": {
            "concept_relaxed_label_metrics": relaxed_concept_label_metrics,
            "relation_relaxed_metrics": relaxed_relation_metrics,
            "relation_family_agnostic_metrics": family_agnostic_relation_metrics,
        },
        "diagnostic_examples": {
            "concept_alias_hits": concept_alias_hits(predicted_concept_map, gold_concept_map),
            "concept_near_misses": concept_near_misses(predicted_concept_map, gold_concept_map),
            "relation_alias_hits": relation_alias_hits(predicted_relation_set, gold_relation_set),
            "relation_family_confusions": relation_family_confusions(predicted_relation_set, gold_relation_set),
            "relation_target_near_misses": relation_target_near_misses(predicted_relation_set, gold_relation_set),
        },
    }
