#!/usr/bin/env python3
"""Conservative matching helpers for strict metrics and relaxed diagnostics."""

from __future__ import annotations

import re
from typing import Iterable


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_LEADING_DIAGNOSTIC_TOKENS: frozenset[str] = frozenset({"plastic", "metal", "local", "nearby", "adjacent"})


def tokenize_label(label: str) -> list[str]:
    tokens = [token.lower() for token in _TOKEN_PATTERN.findall(str(label))]
    collapsed: list[str] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        if current == "o" and index + 1 < len(tokens) and tokens[index + 1] == "ring":
            collapsed.append("oring")
            index += 2
            continue
        collapsed.append(current)
        index += 1
    return collapsed


def normalize_diagnostic_label(label: str) -> str:
    tokens = tokenize_label(label)
    while len(tokens) > 1 and tokens[0] in _LEADING_DIAGNOSTIC_TOKENS:
        tokens = tokens[1:]
    return " ".join(tokens)


def token_overlap_score(left: str, right: str) -> float:
    left_tokens = set(tokenize_label(left))
    right_tokens = set(tokenize_label(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def concept_anchor_pairs(concept_map: dict[str, str]) -> set[tuple[str, str]]:
    return {(label, anchor) for label, anchor in concept_map.items()}


def normalized_relation_key(
    relation: tuple[str, str, str, str],
) -> tuple[str, str, str, str]:
    head, label, tail, family = relation
    return (
        normalize_diagnostic_label(head),
        str(label).strip(),
        normalize_diagnostic_label(tail),
        str(family).strip(),
    )


def family_agnostic_relation_key(
    relation: tuple[str, str, str, str],
) -> tuple[str, str, str]:
    head, label, tail, _family = relation
    return (
        normalize_diagnostic_label(head),
        str(label).strip(),
        normalize_diagnostic_label(tail),
    )


def normalize_label_set(labels: Iterable[str]) -> set[str]:
    return {normalize_diagnostic_label(label) for label in labels if normalize_diagnostic_label(label)}
