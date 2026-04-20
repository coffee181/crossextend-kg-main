from __future__ import annotations

from crossextend_kg.models import AttachmentDecision, SchemaCandidate
from crossextend_kg.rules.filtering import filter_attachment_decision


BACKBONE_CONCEPTS = {
    "Asset",
    "Component",
    "Process",
    "Task",
    "Signal",
    "State",
    "Fault",
    "MaintenanceAction",
    "Incident",
    "Actor",
    "Document",
}
ALLOWED_ROUTES = {"reuse_backbone", "vertical_specialize", "reject"}


def test_om_step_candidate_is_preserved_as_task() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::T1 Report Coolant Condition",
        domain_id="battery",
        label="T1 Report Coolant Condition",
        description="Initial O&M inspection step",
        evidence_ids=["BATOM_001"],
        evidence_texts=["..."],
        support_count=1,
        routing_features={"relation_participation_count": 1},
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Document",
        accept=False,
        admit_as_node=False,
        confidence=0.8,
        justification="llm proposed document-like anchor",
        evidence_ids=["BATOM_001"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.admit_as_node is True
    assert filtered.parent_anchor == "Task"
    assert filtered.route == "vertical_specialize"
    assert filtered.reject_reason is None


def test_document_title_is_rejected() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::Battery Service Report",
        domain_id="battery",
        label="Battery Service Report",
        description="inspection report for service team",
        evidence_ids=["BATOM_001"],
        evidence_texts=["..."],
        support_count=1,
        routing_features={"relation_participation_count": 2},
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Document",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed document anchor",
        evidence_ids=["BATOM_001"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is False
    assert filtered.admit_as_node is False
    assert filtered.parent_anchor is None
    assert filtered.reject_reason == "document_title"


def test_high_value_component_is_not_rejected_only_for_zero_relation_support() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::chiller-inlet connector",
        domain_id="battery",
        label="chiller-inlet connector",
        description="primary cooling connector component",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 0,
            "semantic_type_hint": "Component",
            "step_ids": ["T1"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Component",
        accept=True,
        admit_as_node=True,
        confidence=0.8,
        justification="component candidate",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "Component"


def test_rejected_high_value_component_is_rescued_even_without_relation_support() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::aluminum tube bead",
        domain_id="battery",
        label="aluminum tube bead",
        description="aluminum tube bead component",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 0,
            "semantic_type_hint": "Component",
            "step_ids": ["T4"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="reject",
        parent_anchor=None,
        accept=False,
        admit_as_node=False,
        reject_reason="weak_relation_support",
        confidence=0.2,
        justification="component candidate has no relation participation",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.admit_as_node is True
    assert filtered.parent_anchor == "Component"
    assert filtered.reject_reason is None


def test_fault_hint_is_not_demoted_to_signal_for_recurring_seepage() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::recurring seepage",
        domain_id="battery",
        label="recurring seepage",
        description="persistent seepage fault at inlet bead",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 2,
            "semantic_type_hint": "Fault",
            "step_ids": ["T1", "T7"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Signal",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed signal anchor",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "Fault"


def test_contextual_container_component_is_rejected() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::cooling branch",
        domain_id="battery",
        label="cooling branch",
        description="branch section around connector",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 2,
            "semantic_type_hint": "Component",
            "step_ids": ["T2"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Component",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed component anchor",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is False
    assert filtered.admit_as_node is False
    assert filtered.reject_reason == "low_graph_value"


def test_geometry_measurement_signal_is_rescued_from_low_graph_value() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::upper-to-lower offset",
        domain_id="battery",
        label="upper-to-lower offset",
        description="intended offset",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 1,
            "semantic_type_hint": "Signal",
            "relation_families": ["task_dependency"],
            "step_ids": ["T6"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="reject",
        parent_anchor=None,
        accept=False,
        admit_as_node=False,
        reject_reason="low_graph_value",
        confidence=0.2,
        justification="llm judged it too local",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "Signal"
    assert filtered.reject_reason is None


def test_generic_replacement_component_is_rejected() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::replacement connector",
        domain_id="battery",
        label="replacement connector",
        description="new connector",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 0,
            "semantic_type_hint": "Component",
            "step_ids": ["T5"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="Component",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed component anchor",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is False
    assert filtered.reject_reason == "low_graph_value"


def test_verification_outcome_fragment_is_rejected() -> None:
    candidate = SchemaCandidate(
        candidate_id="nev::service-disconnect status stable",
        domain_id="nev",
        label="service-disconnect status stable",
        description="post-repair verification outcome",
        evidence_ids=["EVMAN_003"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 2,
            "semantic_type_hint": "State",
            "relation_families": ["communication", "task_dependency"],
            "step_ids": ["T7"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="State",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed state anchor",
        evidence_ids=["EVMAN_003"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is False
    assert filtered.reject_reason == "low_graph_value"


def test_centered_clamp_band_is_normalized_to_signal() -> None:
    candidate = SchemaCandidate(
        candidate_id="cnc::clamp band centered",
        domain_id="cnc",
        label="clamp band centered",
        description="observed centered clamp band position",
        evidence_ids=["CNCOM_003"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 2,
            "semantic_type_hint": "State",
            "relation_families": ["lifecycle", "task_dependency"],
            "step_ids": ["T6"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="State",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed state anchor",
        evidence_ids=["CNCOM_003"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "Signal"


def test_side_loaded_branch_is_normalized_to_fault() -> None:
    candidate = SchemaCandidate(
        candidate_id="cnc::side-loaded branch",
        domain_id="cnc",
        label="side-loaded branch",
        description="branch forced off axis by retained twist",
        evidence_ids=["CNCOM_003"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 2,
            "semantic_type_hint": "State",
            "relation_families": ["lifecycle"],
            "step_ids": ["T7"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="State",
        accept=True,
        admit_as_node=True,
        confidence=0.7,
        justification="llm proposed state anchor",
        evidence_ids=["CNCOM_003"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "Fault"


def test_regex_only_preference_does_not_override_valid_llm_anchor() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::sweet odor",
        domain_id="battery",
        label="sweet odor",
        description="observed coolant-like odor near connector outlet",
        evidence_ids=["BATOM_002"],
        evidence_texts=["..."],
        routing_features={
            "relation_participation_count": 3,
            "relation_families": ["communication", "task_dependency"],
            "step_ids": ["T2"],
        },
    )
    decision = AttachmentDecision(
        candidate_id=candidate.candidate_id,
        label=candidate.label,
        route="vertical_specialize",
        parent_anchor="State",
        accept=True,
        admit_as_node=True,
        confidence=0.72,
        justification="llm anchored observation as stateful operating condition",
        evidence_ids=["BATOM_002"],
    )

    filtered = filter_attachment_decision(
        candidate=candidate,
        decision=decision,
        backbone_concepts=BACKBONE_CONCEPTS,
        allowed_routes=ALLOWED_ROUTES,
        allow_free_form_growth=False,
    )

    assert filtered.accept is True
    assert filtered.parent_anchor == "State"
