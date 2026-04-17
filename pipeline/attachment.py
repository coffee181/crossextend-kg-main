#!/usr/bin/env python3
"""Attachment decision logic for CrossExtend-KG variants."""

from __future__ import annotations

import logging

from ..config import PipelineConfig, VariantConfig
from ..models import AttachmentDecision, HistoricalContextHit, RejectReason, RetrievedAnchor, SchemaCandidate
from .memory import top_historical_parent_anchor
from .utils import json_pretty, load_text, render_prompt_template

logger = logging.getLogger(__name__)

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


def _seed_decision(candidate: SchemaCandidate, backbone_concepts: set[str]) -> AttachmentDecision | None:
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


def _normalize_attachment_decision(
    candidate: SchemaCandidate,
    decision: AttachmentDecision,
    retrievals: dict[str, list[RetrievedAnchor]],
    historical_context: dict[str, list[HistoricalContextHit]],
    backbone_concepts: set[str],
) -> AttachmentDecision:
    if decision.route != "reuse_backbone" or candidate.label in backbone_concepts:
        return decision

    recovered_anchor = decision.parent_anchor if decision.parent_anchor in backbone_concepts else None
    if recovered_anchor is None:
        recovered_anchor = _top_anchor(candidate, retrievals)
    if recovered_anchor is None:
        recovered_anchor = top_historical_parent_anchor(historical_context.get(candidate.candidate_id), backbone_concepts)

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
    historical_context: dict[str, list[HistoricalContextHit]],
    backbone_concepts: set[str],
    allow_free_form_growth: bool,
) -> list[AttachmentDecision]:
    decisions: list[AttachmentDecision] = []
    for candidate in candidates:
        seed = _seed_decision(candidate, backbone_concepts)
        if seed:
            decisions.append(seed)
            continue
        retrieved_anchor = _top_anchor(candidate, retrievals)
        historical_anchor = top_historical_parent_anchor(historical_context.get(candidate.candidate_id), backbone_concepts)
        parent_anchor = retrieved_anchor or historical_anchor
        accept = parent_anchor is not None or allow_free_form_growth
        if retrieved_anchor and historical_anchor and retrieved_anchor == historical_anchor:
            confidence = 0.7
            justification = "embedding anchor reinforced by temporal memory"
        elif historical_anchor is not None:
            confidence = 0.65
            justification = "temporal memory anchor"
        elif retrieved_anchor is not None:
            confidence = 0.55
            justification = "embedding top-1 anchor"
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
    historical_context: dict[str, list[HistoricalContextHit]],
    backbone_concepts: set[str],
    allow_free_form_growth: bool,
) -> list[AttachmentDecision]:
    decisions = build_embedding_top1_decisions(candidates, retrievals, historical_context, backbone_concepts, allow_free_form_growth)
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
    historical_context: dict[str, list[HistoricalContextHit]],
    backbone_descriptions: dict[str, str],
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
            "retrieved_anchors": [item.model_dump(mode="json") for item in retrievals.get(candidate.candidate_id, [])],
            "historical_context": [item.model_dump(mode="json") for item in historical_context.get(candidate.candidate_id, [])],
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
    historical_context: dict[str, list[HistoricalContextHit]],
    backbone_descriptions: dict[str, str],
    backbone_concepts: set[str],
) -> dict[str, AttachmentDecision]:
    if variant.attachment_strategy == "embedding_top1":
        decisions = build_embedding_top1_decisions(candidates, retrievals, historical_context, backbone_concepts, variant.allow_free_form_growth)
    elif variant.attachment_strategy == "deterministic":
        decisions = build_deterministic_decisions(candidates, retrievals, historical_context, backbone_concepts, variant.allow_free_form_growth)
    else:
        seed_decisions = [seed for candidate in candidates if (seed := _seed_decision(candidate, backbone_concepts))]
        llm_candidates = [candidate for candidate in candidates if candidate.label not in backbone_concepts]
        decisions = list(seed_decisions)
        total_batches = len(_chunked(llm_candidates, config.runtime.llm_attachment_batch_size))
        logger.info("Domain %s: %d candidates (%d seed, %d LLM), processing %d batches", domain_id, len(candidates), len(seed_decisions), len(llm_candidates), total_batches)
        batch_idx = 0
        for batch in _chunked(llm_candidates, config.runtime.llm_attachment_batch_size):
            batch_idx += 1
            logger.info("Domain %s: processing batch %d/%d (%d candidates)", domain_id, batch_idx, total_batches, len(batch))
            prompt = _build_llm_prompt(config, variant, domain_id, batch, retrievals, historical_context, backbone_descriptions)
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
    normalized_decisions = [
        _normalize_attachment_decision(
            candidate=candidates_by_id[decision.candidate_id],
            decision=decision,
            retrievals=retrievals,
            historical_context=historical_context,
            backbone_concepts=backbone_concepts,
        )
        for decision in decisions
    ]

    decisions_by_id: dict[str, AttachmentDecision] = {}
    for decision in normalized_decisions:
        decisions_by_id[decision.candidate_id] = decision

    # Ensure stable output for every candidate.
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
