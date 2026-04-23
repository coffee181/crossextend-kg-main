#!/usr/bin/env python3
"""Lean safety-rail filtering for attachment decisions."""

from __future__ import annotations

import re

try:
    from crossextend_kg.models import AttachmentDecision, SchemaCandidate
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import AttachmentDecision, SchemaCandidate


_PERSON_TITLE_PATTERN = re.compile(r"^(dr|mr|mrs|ms|prof)\.?\s+", re.IGNORECASE)
_PERSON_NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}$")
_PERSON_ROLE_PATTERN = re.compile(
    r"\b(engineer|technician|operator|inspector|analyst|doctor|specialist|reviewer|approver)\b",
    re.IGNORECASE,
)
_DOCUMENT_PATTERN = re.compile(
    r"\b(document|report|manual|ticket|work order|sop|procedure|case document|service report)\b",
    re.IGNORECASE,
)
_TASK_STEP_PATTERN = re.compile(r"(^|:)T\d+\b", re.IGNORECASE)
_ASSET_PATTERN = re.compile(
    r"\b(asset|vehicle|machine|line|cabinet|platform|station|equipment|system|pack|module pack)\b",
    re.IGNORECASE,
)
_COMPONENT_PATTERN = re.compile(
    r"\b(component|module|connector|hose|clip|bracket|manifold|fitting|sensor|seal|o-ring|terminal|stud|lug|nut|washer|tube|bead|window|rail|cover|shell|boot|cable|contact|valve|pump|fan|board|controller|seat|land|ear|hook|pin)\b",
    re.IGNORECASE,
)
_SIGNAL_PATTERN = re.compile(
    r"\b(signal|reading|telemetry|warning|alarm|result|level|color|path|boundary|wetting|wetness|seepage|residue|height|depth|angle|offset|load|witness|mark|wear|whitening|temperature|pressure|vibration|odor|measurement)\b",
    re.IGNORECASE,
)
_STATE_PATTERN = re.compile(
    r"\b(state|status|condition|mode|open|opened|closed|latched|seated|flush|dry|wet|supported|under circulation|after shutdown)\b",
    re.IGNORECASE,
)
_FAULT_PATTERN = re.compile(
    r"\b(fault|failure|defect|damage|crack|cracked|distortion|corrosion|misalignment|deformation|break|broken|fracture|short-stroke|side-load root cause)\b",
    re.IGNORECASE,
)
_TASK_PATTERN = re.compile(
    r"\b(task|test|inspection|analysis|diagnosis|verification|repair|replacement|adjustment|calibration)\b",
    re.IGNORECASE,
)
_GENERIC_PLACEHOLDER_PATTERN = re.compile(
    r"^(failure|fault|problem|issue|identified leak point|suspect joint|known-good reference)$",
    re.IGNORECASE,
)
_SEMANTIC_TYPE_HINTS = {"Asset", "Component", "Signal", "State", "Fault"}


def _reject(decision: AttachmentDecision, justification: str, reject_reason: str) -> AttachmentDecision:
    return decision.model_copy(
        update={
            "route": "reject",
            "parent_anchor": None,
            "accept": False,
            "admit_as_node": False,
            "reject_reason": reject_reason,
            "justification": justification,
        }
    )


def _compact(text: str) -> str:
    return " ".join(text.lower().split())


def _is_om_step_candidate(candidate: SchemaCandidate) -> bool:
    if candidate.routing_features.get("is_task_candidate"):
        return True
    task_step_id = candidate.routing_features.get("task_step_id")
    if isinstance(task_step_id, str) and task_step_id.strip().upper().startswith("T"):
        return True
    return bool(_TASK_STEP_PATTERN.search(candidate.label.strip()))


def _looks_like_document(candidate: SchemaCandidate) -> bool:
    if _is_om_step_candidate(candidate):
        return False
    text = f"{candidate.label} {candidate.description}"
    return bool(_DOCUMENT_PATTERN.search(text))


def _looks_like_person(candidate: SchemaCandidate) -> bool:
    label = candidate.label.strip()
    compact_label = _compact(label)
    description = _compact(candidate.description)
    if _PERSON_TITLE_PATTERN.match(label):
        return True
    if _PERSON_ROLE_PATTERN.search(compact_label):
        return True
    if _PERSON_NAME_PATTERN.match(label) and any(
        keyword in description
        for keyword in ("engineer", "technician", "operator", "inspector", "analyst", "doctor", "specialist")
    ):
        return True
    return False


def _semantic_type_hint(candidate: SchemaCandidate) -> str | None:
    hint = candidate.routing_features.get("semantic_type_hint")
    if isinstance(hint, str) and hint in _SEMANTIC_TYPE_HINTS:
        return hint
    for item in candidate.routing_features.get("semantic_type_hint_candidates", []):
        if isinstance(item, str) and item in _SEMANTIC_TYPE_HINTS:
            return item
    return None


def preferred_parent_anchor(candidate: SchemaCandidate) -> str | None:
    """Infer a lightweight default anchor for deterministic attachment paths."""
    hint = _semantic_type_hint(candidate)
    if hint is not None:
        return hint

    text = f"{candidate.label} {candidate.description}"
    if _FAULT_PATTERN.search(text):
        return "Fault"
    if _SIGNAL_PATTERN.search(text):
        return "Signal"
    if _STATE_PATTERN.search(text):
        return "State"
    if _COMPONENT_PATTERN.search(text):
        return "Component"
    if _ASSET_PATTERN.search(text):
        return "Asset"
    return None


def filter_attachment_decision(
    candidate: SchemaCandidate,
    decision: AttachmentDecision,
    backbone_concepts: set[str],
    allowed_routes: set[str],
    allow_free_form_growth: bool,
    min_relation_support_count: int = 1,
) -> AttachmentDecision:
    del min_relation_support_count

    if candidate.label in backbone_concepts:
        return AttachmentDecision(
            candidate_id=candidate.candidate_id,
            label=candidate.label,
            route="reuse_backbone",
            parent_anchor=None,
            accept=True,
            admit_as_node=True,
            reject_reason=None,
            confidence=1.0,
            justification=decision.justification or "promoted exact backbone label",
            evidence_ids=list(candidate.evidence_ids),
        )

    if decision.route not in allowed_routes:
        return _reject(decision, "route is not allowed by config", "route_not_allowed")

    if _looks_like_person(candidate):
        return _reject(decision, "person names are provenance metadata, not graph nodes", "person_name")
    if _looks_like_document(candidate):
        return _reject(decision, "document titles belong in provenance, not in the graph schema", "document_title")
    if _GENERIC_PLACEHOLDER_PATTERN.match(candidate.label.strip()):
        return _reject(decision, "generic placeholder wording is not a stable reusable node", "low_graph_value")

    if decision.route == "reuse_backbone":
        if candidate.label in backbone_concepts:
            return decision.model_copy(update={"accept": True, "admit_as_node": True, "reject_reason": None})
        return _reject(
            decision,
            "reuse_backbone requires an exact backbone label match",
            "backbone_label_mismatch",
        )

    if decision.route == "vertical_specialize":
        parent_anchor = str(decision.parent_anchor or "").strip()
        if not parent_anchor:
            if allow_free_form_growth:
                return decision.model_copy(update={"accept": True, "admit_as_node": True, "reject_reason": None})
            return _reject(
                decision,
                "vertical specialization requires a valid backbone parent when free-form growth is disabled",
                "invalid_backbone_parent",
            )
        if parent_anchor not in backbone_concepts:
            return _reject(
                decision,
                "vertical specialization parent is not part of the frozen backbone",
                "invalid_backbone_parent",
            )
        if parent_anchor == "Task":
            return _reject(
                decision,
                "Task is reserved for legacy workflow projection, not semantic attachment",
                "invalid_backbone_parent",
            )
        return decision.model_copy(
            update={
                "parent_anchor": parent_anchor,
                "accept": True,
                "admit_as_node": True,
                "reject_reason": None,
            }
        )

    if decision.route == "reject":
        reject_reason = decision.reject_reason or "low_graph_value"
        return decision.model_copy(
            update={
                "parent_anchor": None,
                "accept": False,
                "admit_as_node": False,
                "reject_reason": reject_reason,
            }
        )

    return _reject(decision, "unsupported route", "route_not_allowed")
