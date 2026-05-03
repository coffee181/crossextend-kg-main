#!/usr/bin/env python3
"""Relation-level filtering rules for final-graph promotion."""

from __future__ import annotations

import re


_STRUCTURAL_CONTEXTUAL_HEAD_PATTERN = re.compile(
    r"\b(branch|path|condition|state|section|geometry|position|circuit|loop|face|surface|interface|cavity|pocket|edge)\b",
    re.IGNORECASE,
)
_LOW_VALUE_STRUCTURAL_TAIL_PATTERN = re.compile(
    r"\b(access panels?|shield|path|angle|offset|clearance|face|surface|interface|cavity|pocket|edge)\b",
    re.IGNORECASE,
)
_GENERIC_COMMUNICATION_TARGET_PATTERN = re.compile(
    r"^(root cause|underlying issue|generic fault)$",
    re.IGNORECASE,
)
_VERIFICATION_RESULT_HEAD_PATTERN = re.compile(
    r"\b(static|dynamic|pressure|proof|test|verification)\s+(?:hold\s+)?results?\b",
    re.IGNORECASE,
)
_SIDE_LOAD_TARGET_PATTERN = re.compile(r"^bracket side load$", re.IGNORECASE)
_SIDE_LOAD_OBSERVATION_PATTERN = re.compile(
    r"\b(witness marks?|witness pattern|side load|off-axis|preload|routing)\b",
    re.IGNORECASE,
)
_LOW_VALUE_LIFECYCLE_ENDPOINTS = {
    "dry",
    "fully latched",
    "naturally supported",
    "stable",
}
_STRUCTURAL_ANCHORS = frozenset({
    "Asset",
    "Component",
    "Seal",
    "Connector",
    "Sensor",
    "Controller",
    "Coolant",
    "Actuator",
    "Power",
    "Housing",
    "Fastener",
    "Media",
})


def _anchor_for(label: str, node_anchor_map: dict[str, str | None] | None) -> str | None:
    if not node_anchor_map:
        return None
    value = node_anchor_map.get(label)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def should_filter_structural_relation(
    head: str,
    tail: str,
    *,
    head_in_graph: bool,
    tail_in_graph: bool,
    node_anchor_map: dict[str, str | None] | None = None,
) -> tuple[bool, str]:
    if not head_in_graph or not tail_in_graph:
        return (False, "endpoint_not_in_graph")

    if _STRUCTURAL_CONTEXTUAL_HEAD_PATTERN.search(head):
        return (True, "structural_contextual_head")

    head_anchor = _anchor_for(head, node_anchor_map)
    tail_anchor = _anchor_for(tail, node_anchor_map)
    if head_anchor not in _STRUCTURAL_ANCHORS or tail_anchor not in _STRUCTURAL_ANCHORS:
        return (True, "structural_requires_stable_components")

    if _LOW_VALUE_STRUCTURAL_TAIL_PATTERN.search(tail):
        return (True, "structural_low_value_tail")

    return (False, "")


def should_filter_communication_relation(
    head: str,
    tail: str,
    *,
    relation_label: str,
    head_in_graph: bool,
    tail_in_graph: bool,
) -> tuple[bool, str]:
    if not head_in_graph or not tail_in_graph:
        return (False, "endpoint_not_in_graph")

    if relation_label.lower() != "indicates":
        return (False, "")

    if _GENERIC_COMMUNICATION_TARGET_PATTERN.match(tail.strip()):
        return (True, "communication_generic_target")

    if _VERIFICATION_RESULT_HEAD_PATTERN.search(head) and tail.strip().lower() in _LOW_VALUE_LIFECYCLE_ENDPOINTS:
        return (True, "communication_verification_bundle")

    if _SIDE_LOAD_TARGET_PATTERN.match(tail.strip()) and not _SIDE_LOAD_OBSERVATION_PATTERN.search(head):
        return (True, "communication_generic_side_load_target")

    return (False, "")


def should_filter_lifecycle_relation(
    head: str,
    tail: str,
    *,
    relation_label: str,
    head_in_graph: bool,
    tail_in_graph: bool,
) -> tuple[bool, str]:
    if not head_in_graph or not tail_in_graph:
        return (False, "endpoint_not_in_graph")

    if relation_label != "transitionsTo":
        return (False, "")

    head_label = head.strip().lower()
    tail_label = tail.strip().lower()
    if head_label in _LOW_VALUE_LIFECYCLE_ENDPOINTS or tail_label in _LOW_VALUE_LIFECYCLE_ENDPOINTS:
        return (True, "lifecycle_verification_only")

    return (False, "")


def filter_relation_mention(
    *,
    family: str,
    head: str,
    tail: str,
    relation_label: str,
    head_in_graph: bool,
    tail_in_graph: bool,
    node_anchor_map: dict[str, str | None] | None = None,
) -> tuple[bool, str]:
    """Return whether a relation should be promoted into the final graph."""

    if family == "structural":
        should_filter, reason = should_filter_structural_relation(
            head,
            tail,
            head_in_graph=head_in_graph,
            tail_in_graph=tail_in_graph,
            node_anchor_map=node_anchor_map,
        )
        return (not should_filter, reason)

    if family == "communication":
        should_filter, reason = should_filter_communication_relation(
            head,
            tail,
            relation_label=relation_label,
            head_in_graph=head_in_graph,
            tail_in_graph=tail_in_graph,
        )
        return (not should_filter, reason)

    if family == "lifecycle":
        should_filter, reason = should_filter_lifecycle_relation(
            head,
            tail,
            relation_label=relation_label,
            head_in_graph=head_in_graph,
            tail_in_graph=tail_in_graph,
        )
        return (not should_filter, reason)

    return (True, "")
