#!/usr/bin/env python3
"""Filtering and validation rules for attachment decisions."""

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
_DOCUMENT_LABEL_PATTERN = re.compile(r"\b(document|report|manual|ticket|work order|sop)\b", re.IGNORECASE)
_DOCUMENT_DESCRIPTION_PATTERN = re.compile(r"\b(case document|service report|inspection report|maintenance report|document)\b", re.IGNORECASE)
_TASK_STEP_PATTERN = re.compile(r"^T\d+\b", re.IGNORECASE)
_ASSET_PATTERN = re.compile(r"\b(pack|vehicle|machine|line|cabinet|station|platform|equipment|asset)\b", re.IGNORECASE)
_COMPONENT_PATTERN = re.compile(
    r"\b(bms|management system|controller|sensor|cell|anode|cathode|separator|vent|bearing|motor|valve|module|connector|board|pump|fan|hose|bracket|clip|seam)\b",
    re.IGNORECASE,
)
_SIGNAL_PATTERN = re.compile(
    r"\b(signal|curve|history|reading|telemetry|odor|count|alarm|warning|runtime reduction|result|response|level|wetness|wetting|seepage|height|depth|twist|load|path)\b",
    re.IGNORECASE,
)
_OBSERVATION_SIGNAL_PATTERN = re.compile(
    r"\b(pressure result|pressure test result|residue path|drip path|leak path|wet boundary|fresh wetting|insertion depth|latch height|clocking|preload|side load|coolant level|residue color|witness pattern)\b",
    re.IGNORECASE,
)
_STATE_PATTERN = re.compile(r"\b(state|status|condition|mode)\b", re.IGNORECASE)
_STATE_CONTEXT_PATTERN = re.compile(
    r"\b(as-found|as found|as-received|as received|under circulation|after shutdown|remains wet|stays dry|operating condition|safe state|opened state|closed state)\b",
    re.IGNORECASE,
)
_STATE_DESCRIPTION_PATTERN = re.compile(r"^(?:state|condition|status)\b.*\b(where|when)\b", re.IGNORECASE)
_FAULT_PATTERN = re.compile(
    r"\b(fault|failure|degradation|crack|cracking|plating|anomaly|defect|growth|leak|leakage|distortion|seepage)\b",
    re.IGNORECASE,
)
_TASK_PATTERN = re.compile(r"\b(task|test|inspection|analysis|diagnosis|dump|verification|correlation|repair|replacement)\b", re.IGNORECASE)
_SIGNAL_CONTEXT_PATTERN = re.compile(
    r"\b(reported|detected|telemetry|sensor reading|reading|warning|alarm|measured|observed|visible|photographed)\b",
    re.IGNORECASE,
)
_OBSERVATION_AS_SIGNAL_PATTERN = re.compile(
    r"\b(centered|seated|flush(?:ness)?|proud|movement|trace|witness|recovery|position|seating)\b",
    re.IGNORECASE,
)
_FAULTISH_OBSERVATION_PATTERN = re.compile(
    r"\b(side-loaded|off-axis|misalignment|short-stroke|warp(?:ed)?|pull-up|bow)\b",
    re.IGNORECASE,
)
_OBSERVATION_EVIDENCE_PATTERN = re.compile(
    r"\b(whitening|witness marks?|distortion|wear|burrs?|nicks?|corrosion|odor|wetting|wet boundary|residue|seepage|path)\b",
    re.IGNORECASE,
)
_LOW_VALUE_FRAGMENT_PATTERN = re.compile(
    r"\b(as-found angle|as-found leak path|connector-to-clip path|dynamic proof results?|static proof results?|clip position|connector centering|connector sweating|dry joint|damaged neck|bead condition|full engagement|insertion depth reference|retainer windows|shield preload)\b",
    re.IGNORECASE,
)
_VERIFICATION_OUTCOME_PATTERN = re.compile(
    r"\b(stable|no\s+(?:renewed|repeat|handle movement|latch relaxation)|seats\s+flush|flush\s+with|snaps\s+(?:fully|back)|stays\s+dry|remains\s+dry|holding\s+without|dry\s+after)\b",
    re.IGNORECASE,
)
_GENERIC_PLACEHOLDER_PATTERN = re.compile(
    r"^(failure|fault|problem|confirmed leak boundary|identified leak point|suspect joint)$",
    re.IGNORECASE,
)
_CONTEXTUAL_CONTAINER_PATTERN = re.compile(r"\b(branch|path|section|geometry|position)\b", re.IGNORECASE)
_GEOMETRY_MEASUREMENT_PATTERN = re.compile(r"\b(bend radius|upper-to-lower offset|clearance)\b", re.IGNORECASE)
_GENERIC_COMPONENT_CANDIDATE_PATTERN = re.compile(r"^(replacement connector|seal|retainer)$", re.IGNORECASE)
_GENERIC_COMPONENT_DESCRIPTION_PATTERN = re.compile(r"\b(new|replacement)\b", re.IGNORECASE)
_PERSON_KEYWORDS = {
    "engineer",
    "technician",
    "operator",
    "inspector",
    "analyst",
    "doctor",
    "specialist",
    "reviewer",
    "approver",
}
_SEMANTIC_TYPE_HINTS = {"Asset", "Component", "Signal", "State", "Fault"}


def _reject(decision: AttachmentDecision, justification: str, reject_reason: str) -> AttachmentDecision:
    return decision.model_copy(
        update={
            "route": "reject",
            "accept": False,
            "admit_as_node": False,
            "parent_anchor": None,
            "reject_reason": reject_reason,
            "justification": justification,
        }
    )


def _compact(text: str) -> str:
    return " ".join(text.lower().split())


def _is_om_step_candidate(candidate: SchemaCandidate) -> bool:
    if _TASK_STEP_PATTERN.match(candidate.label.strip()):
        return True
    if candidate.routing_features.get("is_task_candidate"):
        return True
    task_step_id = candidate.routing_features.get("task_step_id")
    return isinstance(task_step_id, str) and bool(_TASK_STEP_PATTERN.match(task_step_id))


def _looks_like_document(candidate: SchemaCandidate) -> bool:
    if _is_om_step_candidate(candidate):
        return False
    return bool(
        _DOCUMENT_LABEL_PATTERN.search(candidate.label)
        or _DOCUMENT_DESCRIPTION_PATTERN.search(candidate.description)
    )


def _looks_like_person(candidate: SchemaCandidate) -> bool:
    label = candidate.label.strip()
    label_compact = _compact(label)
    description = _compact(candidate.description)
    if _PERSON_TITLE_PATTERN.match(label):
        return True
    if _PERSON_ROLE_PATTERN.search(label_compact):
        return True
    if _PERSON_NAME_PATTERN.match(label) and any(keyword in description for keyword in _PERSON_KEYWORDS):
        return True
    return False


def _relation_support_count(candidate: SchemaCandidate) -> int:
    return int(candidate.routing_features.get("relation_participation_count", 0))


def _semantic_type_hint(candidate: SchemaCandidate) -> str | None:
    hint = candidate.routing_features.get("semantic_type_hint")
    if isinstance(hint, str) and hint in _SEMANTIC_TYPE_HINTS:
        return hint
    for item in candidate.routing_features.get("semantic_type_hint_candidates", []):
        if isinstance(item, str) and item in _SEMANTIC_TYPE_HINTS:
            return item
    return None


def _preferred_parent_anchor(candidate: SchemaCandidate) -> str | None:
    label = candidate.label
    description = candidate.description
    text = f"{label} {description}"
    if _is_om_step_candidate(candidate):
        return "Task"
    if _FAULTISH_OBSERVATION_PATTERN.search(label):
        return "Fault"
    if _OBSERVATION_AS_SIGNAL_PATTERN.search(label):
        return "Signal"
    if _OBSERVATION_EVIDENCE_PATTERN.search(label) and not _FAULT_PATTERN.search(label):
        return "Signal"
    if label.strip().lower() == "operating state":
        return "Signal"
    hint = _semantic_type_hint(candidate)
    if hint is not None:
        if hint == "Fault" and _OBSERVATION_EVIDENCE_PATTERN.search(text) and not _FAULT_PATTERN.search(label):
            return "Signal"
        return hint
    if _OBSERVATION_SIGNAL_PATTERN.search(label):
        return "Signal"
    if _SIGNAL_PATTERN.search(label):
        return "Signal"
    if _STATE_CONTEXT_PATTERN.search(label):
        return "State"
    if _STATE_PATTERN.search(label):
        return "State"
    if _FAULT_PATTERN.search(label):
        return "Fault"
    if _TASK_PATTERN.search(label):
        return "Task"
    if _OBSERVATION_SIGNAL_PATTERN.search(text):
        return "Signal"
    if _SIGNAL_CONTEXT_PATTERN.search(description):
        return "Signal"
    if _SIGNAL_PATTERN.search(text):
        return "Signal"
    if _STATE_DESCRIPTION_PATTERN.search(description):
        return "State"
    if _STATE_CONTEXT_PATTERN.search(text):
        return "State"
    if _STATE_PATTERN.search(text):
        return "State"
    if _FAULT_PATTERN.search(text):
        return "Fault"
    if _COMPONENT_PATTERN.search(text):
        return "Component"
    if _ASSET_PATTERN.search(text):
        return "Asset"
    if _TASK_PATTERN.search(text):
        return "Task"
    return None


def preferred_parent_anchor(candidate: SchemaCandidate) -> str | None:
    """Public helper for anchor inference based on current filtering semantics."""
    return _preferred_parent_anchor(candidate)


def _should_override_parent_anchor(
    candidate: SchemaCandidate,
    current_anchor: str,
    preferred_anchor: str,
) -> bool:
    if preferred_anchor == current_anchor:
        return False

    if preferred_anchor == "Task" and _is_om_step_candidate(candidate):
        return True

    hint = _semantic_type_hint(candidate)
    if hint == preferred_anchor:
        return True

    if current_anchor == "Task" and not _is_om_step_candidate(candidate):
        return True

    label = candidate.label
    if preferred_anchor == "Signal" and (
        _OBSERVATION_AS_SIGNAL_PATTERN.search(label)
        or _OBSERVATION_SIGNAL_PATTERN.search(label)
        or _GEOMETRY_MEASUREMENT_PATTERN.search(label)
    ):
        return True

    if preferred_anchor == "Fault" and _FAULTISH_OBSERVATION_PATTERN.search(label):
        return True

    return False


def _has_high_value_semantics(candidate: SchemaCandidate) -> bool:
    preferred_anchor = _preferred_parent_anchor(candidate)
    if preferred_anchor in {"Asset", "Component"}:
        return True
    text = f"{candidate.label} {candidate.description}"
    if _ASSET_PATTERN.search(text) or _COMPONENT_PATTERN.search(text):
        return True
    return False


def _is_contextual_container(candidate: SchemaCandidate) -> bool:
    preferred_anchor = _preferred_parent_anchor(candidate)
    if preferred_anchor not in {"Asset", "Component"}:
        return False
    return bool(_CONTEXTUAL_CONTAINER_PATTERN.search(candidate.label))


def _rescue_rejected_candidate(
    candidate: SchemaCandidate,
    decision: AttachmentDecision,
    backbone_concepts: set[str],
    min_relation_support_count: int,
) -> AttachmentDecision | None:
    support_count = _relation_support_count(candidate)
    preferred_anchor = _preferred_parent_anchor(candidate)
    if _is_om_step_candidate(candidate) and "Task" in backbone_concepts:
        return decision.model_copy(
            update={
                "route": "vertical_specialize",
                "parent_anchor": "Task",
                "accept": True,
                "admit_as_node": True,
                "reject_reason": None,
                "justification": "rescued O&M step candidate as Task despite reject route",
            }
        )

    if (
        preferred_anchor in {"Asset", "Component"}
        and preferred_anchor in backbone_concepts
        and _has_high_value_semantics(candidate)
        and not _is_contextual_container(candidate)
        and decision.reject_reason in {"weak_relation_support", "cannot_anchor_backbone", "llm_no_decision"}
    ):
        return decision.model_copy(
            update={
                "route": "vertical_specialize",
                "parent_anchor": preferred_anchor,
                "accept": True,
                "admit_as_node": True,
                "reject_reason": None,
                "justification": f"rescued high-value {preferred_anchor} despite sparse relation support",
            }
        )

    if (
        decision.reject_reason == "observation_like_not_grounded"
        and preferred_anchor in {"Signal", "State"}
        and preferred_anchor in backbone_concepts
        and (
            support_count >= max(2, min_relation_support_count)
            or any(
                family in {"communication", "propagation", "lifecycle"}
                for family in candidate.routing_features.get("relation_families", [])
            )
        )
    ):
        return decision.model_copy(
            update={
                "route": "vertical_specialize",
                "parent_anchor": preferred_anchor,
                "accept": True,
                "admit_as_node": True,
                "reject_reason": None,
                "justification": f"rescued grounded O&M observation as {preferred_anchor}",
            }
        )

    if (
        preferred_anchor == "Signal"
        and preferred_anchor in backbone_concepts
        and decision.reject_reason in {"low_graph_value", "observation_like_not_grounded"}
        and _GEOMETRY_MEASUREMENT_PATTERN.search(candidate.label)
    ):
        return decision.model_copy(
            update={
                "route": "vertical_specialize",
                "parent_anchor": "Signal",
                "accept": True,
                "admit_as_node": True,
                "reject_reason": None,
                "justification": "rescued reusable geometry measurement as Signal",
            }
        )

    if support_count < min_relation_support_count:
        return None

    return None


def filter_attachment_decision(
    candidate: SchemaCandidate,
    decision: AttachmentDecision,
    backbone_concepts: set[str],
    allowed_routes: set[str],
    allow_free_form_growth: bool,
    min_relation_support_count: int = 1,
) -> AttachmentDecision:
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
            justification=decision.justification or "seed or promoted backbone concept",
            evidence_ids=list(candidate.evidence_ids),
        )

    if decision.route not in allowed_routes:
        return _reject(decision, "route is not allowed by config", "route_not_allowed")

    if decision.route == "vertical_specialize":
        if _looks_like_person(candidate):
            return _reject(decision, "person names are not eligible as graph nodes", "person_name")
        if _looks_like_document(candidate):
            return _reject(decision, "document titles are kept in provenance instead of graph nodes", "document_title")
        if _GENERIC_PLACEHOLDER_PATTERN.match(candidate.label.strip()):
            return _reject(
                decision,
                "generic placeholder wording is not kept as a stable graph node when a more specific concept should carry the semantics",
                "low_graph_value",
            )
        if _is_contextual_container(candidate):
            return _reject(
                decision,
                "contextual container component is kept in explainability context, not as a stable graph node",
                "low_graph_value",
            )
        if (
            _preferred_parent_anchor(candidate) == "Component"
            and _relation_support_count(candidate) == 0
            and (
                _GENERIC_COMPONENT_CANDIDATE_PATTERN.match(candidate.label)
                or _GENERIC_COMPONENT_DESCRIPTION_PATTERN.search(candidate.description)
            )
        ):
            return _reject(
                decision,
                "generic replacement-part wording is not kept as a stable graph node when a more specific component should carry the semantics",
                "low_graph_value",
            )
        if _VERIFICATION_OUTCOME_PATTERN.search(candidate.label):
            return _reject(
                decision,
                "post-repair verification outcome wording is kept in explainability context instead of the stable graph",
                "low_graph_value",
            )
        if _LOW_VALUE_FRAGMENT_PATTERN.search(candidate.label):
            return _reject(decision, "low-value step-local fragment is not kept as a graph node", "low_graph_value")
        if decision.parent_anchor and decision.parent_anchor in backbone_concepts:
            preferred_anchor = _preferred_parent_anchor(candidate)
            if (
                preferred_anchor
                and preferred_anchor in backbone_concepts
                and _should_override_parent_anchor(candidate, decision.parent_anchor, preferred_anchor)
            ):
                decision = decision.model_copy(
                    update={
                        "parent_anchor": preferred_anchor,
                        "justification": f"{decision.justification}; normalized parent anchor to {preferred_anchor}",
                    }
                )
            if (
                _relation_support_count(candidate) < min_relation_support_count
                and not _has_high_value_semantics(candidate)
            ):
                return _reject(
                    decision,
                    f"candidate relation support is below the minimum threshold ({min_relation_support_count})",
                    "weak_relation_support",
                )
            return decision.model_copy(update={"accept": True, "admit_as_node": True, "reject_reason": None})
        if allow_free_form_growth:
            return decision.model_copy(update={"accept": True, "admit_as_node": True, "reject_reason": None})
        return _reject(
            decision,
            "vertical specialization requires a backbone parent when free-form growth is disabled",
            "invalid_backbone_parent",
        )

    if decision.route == "reuse_backbone":
        if candidate.label in backbone_concepts:
            return decision.model_copy(update={"accept": True, "admit_as_node": True, "reject_reason": None})
        return _reject(
            decision,
            "candidate label does not exactly match a backbone concept",
            "backbone_label_mismatch",
        )

    if decision.route == "reject":
        if _looks_like_person(candidate):
            return _reject(decision, "person names are not eligible as graph nodes", "person_name")
        rescued_decision = _rescue_rejected_candidate(
            candidate,
            decision,
            backbone_concepts,
            min_relation_support_count,
        )
        if rescued_decision is not None:
            return rescued_decision
        reject_reason = decision.reject_reason or "low_graph_value"
        return decision.model_copy(update={"accept": False, "admit_as_node": False, "reject_reason": reject_reason})

    return _reject(decision, "unsupported route", "route_not_allowed")
