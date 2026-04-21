#!/usr/bin/env python3
"""Attachment decision logic for CrossExtend-KG variants."""

from __future__ import annotations

import logging

try:
    from crossextend_kg.config import PipelineConfig, VariantConfig
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import PipelineConfig, VariantConfig
try:
    from crossextend_kg.models import AttachmentDecision, RejectReason, RetrievedAnchor, SchemaCandidate
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import AttachmentDecision, RejectReason, RetrievedAnchor, SchemaCandidate
from pipeline.utils import json_pretty, load_text, render_prompt_template

logger = logging.getLogger(__name__)

_PROPAGATION_FAMILIES: frozenset[str] = frozenset({"propagation", "communication"})
_SEMANTIC_TYPE_HINTS: frozenset[str] = frozenset({"Asset", "Component", "Signal", "State", "Fault"})
_FAMILY_COMPATIBLE_ANCHORS: dict[str, frozenset[str]] = {
    "task_dependency": frozenset({"Task", "Process", "Actor", "Signal", "State", "Fault", "Asset", "Component", "Document"}),
    "communication": frozenset({"Component", "Signal", "Process", "State", "Asset", "Actor", "Task", "Fault"}),
    "propagation": frozenset({"Fault", "Signal", "State", "Process", "Component"}),
    "structural": frozenset({"Asset", "Component"}),
    "lifecycle": frozenset({"Asset", "Component", "Fault", "State", "MaintenanceAction", "Incident", "Process"}),
}

ALLOWED_REJECT_REASONS: tuple[RejectReason, ...] = (
    "person_name",
    "document_title",
    "observation_like_not_grounded",
    "cannot_anchor_backbone",
    "weak_relation_support",
    "low_graph_value",
    "unsupported_semantic_type",
    "route_not_allowed",
    "invalid_backbone_parent",
    "llm_no_decision",
    "backbone_label_mismatch",
)


def _semantic_type_hint(candidate: SchemaCandidate) -> str | None:
    hint = candidate.routing_features.get("semantic_type_hint")
    if isinstance(hint, str) and hint in _SEMANTIC_TYPE_HINTS:
        return hint
    for item in candidate.routing_features.get("semantic_type_hint_candidates", []):
        if isinstance(item, str) and item in _SEMANTIC_TYPE_HINTS:
            return item
    return None


def _is_task_candidate(candidate: SchemaCandidate) -> bool:
    if candidate.routing_features.get("is_task_candidate"):
        return True
    task_step_id = candidate.routing_features.get("task_step_id")
    return isinstance(task_step_id, str) and task_step_id.startswith("T")


def _apply_semantic_type_hint(candidate: SchemaCandidate, proposed_anchor: str | None) -> str | None:
    hint = _semantic_type_hint(candidate)
    if hint is None:
        return proposed_anchor
    if proposed_anchor is None:
        return hint
    if proposed_anchor == "Task" and not _is_task_candidate(candidate):
        return hint
    return proposed_anchor


def _infer_anchor_from_relation_families(
    candidate: SchemaCandidate,
    proposed_anchor: str | None,
) -> str | None:
    families: list[str] = candidate.routing_features.get("relation_families", [])
    family_set = set(families)
    if not family_set:
        return proposed_anchor

    if _PROPAGATION_FAMILIES & family_set and "task_dependency" not in family_set:
        if proposed_anchor in (None, "Task"):
            return _semantic_type_hint(candidate)
        if all(
            proposed_anchor in _FAMILY_COMPATIBLE_ANCHORS.get(family, frozenset({proposed_anchor}))
            for family in family_set
        ):
            return proposed_anchor
        return _semantic_type_hint(candidate)

    if proposed_anchor == "Task" and "task_dependency" not in family_set and family_set:
        return _semantic_type_hint(candidate)

    if proposed_anchor is None:
        return None

    if all(
        proposed_anchor in _FAMILY_COMPATIBLE_ANCHORS.get(family, frozenset({proposed_anchor}))
        for family in family_set
    ):
        return proposed_anchor

    hint = _semantic_type_hint(candidate)
    if hint is None:
        return None
    if all(
        hint in _FAMILY_COMPATIBLE_ANCHORS.get(family, frozenset({hint}))
        for family in family_set
    ):
        return hint
    return None


def _seed_decision(candidate: SchemaCandidate, backbone_concepts: set[str]) -> AttachmentDecision | None:
    if _is_task_candidate(candidate) and "Task" in backbone_concepts:
        return AttachmentDecision(
            candidate_id=candidate.candidate_id,
            label=candidate.label,
            route="vertical_specialize",
            parent_anchor="Task",
            accept=True,
            admit_as_node=True,
            reject_reason=None,
            confidence=1.0,
            justification="preserved O&M step candidate as Task",
            evidence_ids=list(candidate.evidence_ids),
        )
    if candidate.label not in backbone_concepts:
        return None
    return AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="reuse_backbone",
        parent_anchor=None,
        accept=True,
        admit_as_node=True,
        reject_reason=None,
        confidence=1.0,
        justification="already in frozen backbone",
        evidence_ids=list(candidate.evidence_ids),
    )


def _top_anchor(candidate: SchemaCandidate, retrievals: dict[str, list[RetrievedAnchor]]) -> str | None:
    items = retrievals.get(candidate.candidate_id, [])
    if items:
        return items[0].anchor
    return None


def _top_retrieval(candidate: SchemaCandidate, retrievals: dict[str, list[RetrievedAnchor]]) -> RetrievedAnchor | None:
    items = retrievals.get(candidate.candidate_id, [])
    if items:
        return items[0]
    return None


def _build_prompt_priors(
    candidate: SchemaCandidate,
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_concepts: set[str],
) -> dict[str, object]:
    top_retrieval = _top_retrieval(candidate, retrievals)
    top_anchor = top_retrieval.anchor if top_retrieval else None
    semantic_hint = _semantic_type_hint(candidate)
    retrieved_anchor = _infer_anchor_from_relation_families(
        candidate,
        _apply_semantic_type_hint(candidate, top_anchor),
    )
    hint_anchor = _infer_anchor_from_relation_families(
        candidate,
        _apply_semantic_type_hint(candidate, None),
    )
    recommended_anchor = retrieved_anchor or hint_anchor
    prior_agreement = (
        retrieved_anchor is not None
        and hint_anchor is not None
        and retrieved_anchor == hint_anchor
    )
    if candidate.label in backbone_concepts:
        recommended_route = "reuse_backbone"
    elif recommended_anchor is not None:
        recommended_route = "vertical_specialize"
    else:
        recommended_route = "reject"
    if prior_agreement or (top_anchor and semantic_hint and top_anchor == semantic_hint):
        prior_strength = "high"
    elif recommended_anchor is not None:
        prior_strength = "medium"
    else:
        prior_strength = "low"
    return {
        "semantic_type_hint": semantic_hint,
        "top_retrieved_anchor": top_anchor,
        "top_retrieved_score": round(float(top_retrieval.score), 4) if top_retrieval else None,
        "retrieval_anchor_after_family_check": retrieved_anchor,
        "hint_anchor_after_family_check": hint_anchor,
        "recommended_parent_anchor": recommended_anchor,
        "recommended_route_if_admitted": recommended_route,
        "prior_agreement": prior_agreement,
        "prior_strength": prior_strength,
    }


def _normalize_attachment_decision(
    candidate: SchemaCandidate,
    decision: AttachmentDecision,
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_concepts: set[str],
) -> AttachmentDecision:
    if decision.route != "reuse_backbone" or candidate.label in backbone_concepts:
        return decision

    recovered_anchor = decision.parent_anchor if decision.parent_anchor in backbone_concepts else None
    recovered_anchor = _apply_semantic_type_hint(candidate, recovered_anchor)
    recovered_anchor = _infer_anchor_from_relation_families(candidate, recovered_anchor)
    if recovered_anchor is None:
        recovered_anchor = _infer_anchor_from_relation_families(
            candidate,
            _apply_semantic_type_hint(candidate, _top_anchor(candidate, retrievals)),
        )
    if recovered_anchor is None:
        recovered_anchor = _infer_anchor_from_relation_families(
            candidate,
            _apply_semantic_type_hint(candidate, None),
        )

    if recovered_anchor is None:
        return decision.model_copy(
            update={
                "route": "reject",
                "parent_anchor": None,
                "accept": False,
                "admit_as_node": False,
                "reject_reason": "cannot_anchor_backbone",
                "justification": "invalid backbone reuse without recoverable backbone anchor",
            }
        )

    return decision.model_copy(
        update={
            "route": "vertical_specialize",
            "parent_anchor": recovered_anchor,
            "accept": True,
            "admit_as_node": True,
            "reject_reason": None,
            "justification": "normalized non-backbone reuse request into anchored vertical specialization",
        }
    )


def build_embedding_top1_decisions(
    candidates: list[SchemaCandidate],
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_concepts: set[str],
    allow_free_form_growth: bool,
) -> list[AttachmentDecision]:
    decisions: list[AttachmentDecision] = []
    for candidate in candidates:
        seed = _seed_decision(candidate, backbone_concepts)
        if seed:
            decisions.append(seed)
            continue
        retrieved_anchor = _infer_anchor_from_relation_families(
            candidate,
            _apply_semantic_type_hint(candidate, _top_anchor(candidate, retrievals)),
        )
        hint_anchor = _infer_anchor_from_relation_families(
            candidate,
            _apply_semantic_type_hint(candidate, None),
        )
        parent_anchor = retrieved_anchor or hint_anchor
        accept = parent_anchor is not None or allow_free_form_growth
        if retrieved_anchor is not None:
            confidence = 0.55
            justification = "embedding top-1 anchor"
        elif hint_anchor is not None:
            confidence = 0.5
            justification = "preprocessing semantic type hint"
        else:
            confidence = 0.25
            justification = "no anchor available"
        decisions.append(
            AttachmentDecision(
                candidate_id=candidate.candidate_id,
                label=candidate.label,
                route="vertical_specialize" if accept else "reject",
                parent_anchor=parent_anchor,
                accept=accept,
                admit_as_node=accept,
                reject_reason=None if accept else "cannot_anchor_backbone",
                confidence=confidence,
                justification=justification,
                evidence_ids=list(candidate.evidence_ids),
            )
        )
    return decisions


def build_deterministic_decisions(
    candidates: list[SchemaCandidate],
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_concepts: set[str],
    allow_free_form_growth: bool,
) -> list[AttachmentDecision]:
    decisions = build_embedding_top1_decisions(
        candidates,
        retrievals,
        backbone_concepts,
        allow_free_form_growth,
    )
    for index, decision in enumerate(decisions):
        if decision.route == "vertical_specialize":
            decisions[index] = decision.model_copy(
                update={
                    "confidence": max(decision.confidence, 0.6),
                    "justification": "deterministic anchor routing",
                }
            )
    return decisions


def _parse_llm_decisions(payload: dict, candidates: list[SchemaCandidate]) -> list[AttachmentDecision]:
    candidate_map = {candidate.candidate_id: candidate for candidate in candidates}
    parsed_by_id: dict[str, AttachmentDecision] = {}
    for item in payload.get("decisions", []):
        decision = AttachmentDecision.model_validate(item)
        candidate = candidate_map.get(decision.candidate_id)
        if candidate is None:
            continue
        parsed_by_id[decision.candidate_id] = decision.model_copy(
            update={
                "label": candidate.label,
                "evidence_ids": decision.evidence_ids or list(candidate.evidence_ids),
            }
        )

    parsed = list(parsed_by_id.values())
    seen = set(parsed_by_id)
    for candidate in candidates:
        if candidate.candidate_id in seen:
            continue
        parsed.append(
            AttachmentDecision(
                candidate_id=candidate.candidate_id,
                label=candidate.label,
                route="reject",
                parent_anchor=None,
                accept=False,
                admit_as_node=False,
                reject_reason="llm_no_decision",
                confidence=0.0,
                justification="llm returned no decision for candidate",
                evidence_ids=list(candidate.evidence_ids),
            )
        )
    return parsed


def _build_llm_prompt(
    config: PipelineConfig,
    variant: VariantConfig,
    domain_id: str,
    candidates: list[SchemaCandidate],
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_descriptions: dict[str, str],
    backbone_concepts: set[str],
) -> str:
    template = load_text(config.prompts.attachment_judge_template_path)
    candidate_payload = []
    for candidate in candidates:
        payload = {
            "candidate_id": candidate.candidate_id,
            "label": candidate.label,
            "description": candidate.description,
            "evidence_ids": candidate.evidence_ids[:3],
            "evidence_examples": candidate.evidence_texts[:2],
            "routing_features": candidate.routing_features,
            "prompt_priors": _build_prompt_priors(candidate, retrievals, backbone_concepts),
            "retrieved_anchors": [item.model_dump(mode="json") for item in retrievals.get(candidate.candidate_id, [])],
        }
        candidate_payload.append(payload)
    return_schema = {
        "domain_id": domain_id,
        "allowed_reject_reasons": list(ALLOWED_REJECT_REASONS),
        "decisions": [
            {
                "candidate_id": "string",
                "label": "string",
                "route": " | ".join(config.relations.allowed_routes),
                "parent_anchor": "null or backbone concept",
                "accept": True,
                "admit_as_node": True,
                "reject_reason": f"null or one of {list(ALLOWED_REJECT_REASONS)}",
                "confidence": 0.0,
                "justification": "short explanation",
                "evidence_ids": ["optional evidence ids"],
            }
        ],
    }
    return render_prompt_template(
        template,
        {
            "__DOMAIN_ID__": domain_id,
            "__ALLOWED_ROUTES__": ", ".join(config.relations.allowed_routes),
            "__ALLOW_FREE_FORM_GROWTH__": str(variant.allow_free_form_growth),
            "__BACKBONE_DESCRIPTIONS_JSON__": json_pretty(backbone_descriptions),
            "__CANDIDATES_JSON__": json_pretty(candidate_payload),
            "__RETURN_SCHEMA_JSON__": json_pretty(return_schema),
        },
    )


def _chunked(items: list[SchemaCandidate], size: int) -> list[list[SchemaCandidate]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    return [items[index : index + size] for index in range(0, len(items), size)]


def decide_attachments_for_domain(
    config: PipelineConfig,
    variant: VariantConfig,
    llm_backend,
    domain_id: str,
    candidates: list[SchemaCandidate],
    retrievals: dict[str, list[RetrievedAnchor]],
    backbone_descriptions: dict[str, str],
    backbone_concepts: set[str],
) -> dict[str, AttachmentDecision]:
    if variant.attachment_strategy == "embedding_top1":
        decisions = build_embedding_top1_decisions(
            candidates,
            retrievals,
            backbone_concepts,
            variant.allow_free_form_growth,
        )
    elif variant.attachment_strategy == "deterministic":
        decisions = build_deterministic_decisions(
            candidates,
            retrievals,
            backbone_concepts,
            variant.allow_free_form_growth,
        )
    else:
        seed_decisions = [seed for candidate in candidates if (seed := _seed_decision(candidate, backbone_concepts))]
        seeded_ids = {decision.candidate_id for decision in seed_decisions}
        llm_candidates = [candidate for candidate in candidates if candidate.candidate_id not in seeded_ids]
        decisions = list(seed_decisions)
        total_batches = len(_chunked(llm_candidates, config.runtime.llm_attachment_batch_size))
        logger.info(
            "Domain %s: %d candidates (%d seed, %d LLM), processing %d batches",
            domain_id,
            len(candidates),
            len(seed_decisions),
            len(llm_candidates),
            total_batches,
        )
        batch_idx = 0
        for batch in _chunked(llm_candidates, config.runtime.llm_attachment_batch_size):
            batch_idx += 1
            logger.info("Domain %s: processing batch %d/%d (%d candidates)", domain_id, batch_idx, total_batches, len(batch))
            prompt = _build_llm_prompt(
                config,
                variant,
                domain_id,
                batch,
                retrievals,
                backbone_descriptions,
                backbone_concepts,
            )
            try:
                payload = llm_backend.generate_json(prompt)
                decisions.extend(_parse_llm_decisions(payload, batch))
                logger.info("Domain %s: batch %d/%d completed successfully", domain_id, batch_idx, total_batches)
            except Exception as exc:
                logger.error("Domain %s: batch %d/%d failed: %s", domain_id, batch_idx, total_batches, exc)
                raise RuntimeError(
                    f"LLM attachment failed for variant={variant.variant_id} domain={domain_id}: {exc}"
                ) from exc

    candidates_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    normalized_decisions: list[AttachmentDecision] = []
    for decision in decisions:
        candidate = candidates_by_id.get(decision.candidate_id)
        if candidate is None:
            logger.warning(
                "Dropping attachment decision for unknown candidate_id=%s in domain %s",
                decision.candidate_id,
                domain_id,
            )
            continue
        normalized_decisions.append(
            _normalize_attachment_decision(
                candidate=candidate,
                decision=decision,
                retrievals=retrievals,
                backbone_concepts=backbone_concepts,
            )
        )

    decisions_by_id: dict[str, AttachmentDecision] = {}
    for decision in normalized_decisions:
        decisions_by_id[decision.candidate_id] = decision

    for candidate in candidates:
        if candidate.candidate_id not in decisions_by_id:
            decisions_by_id[candidate.candidate_id] = AttachmentDecision(
                candidate_id=candidate.candidate_id,
                label=candidate.label,
                route="reject",
                parent_anchor=None,
                accept=False,
                admit_as_node=False,
                reject_reason="llm_no_decision",
                confidence=0.0,
                justification="no decision available",
                evidence_ids=list(candidate.evidence_ids),
            )
    return decisions_by_id
