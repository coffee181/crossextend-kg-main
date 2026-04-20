from __future__ import annotations

from crossextend_kg.models import RetrievedAnchor, SchemaCandidate
from crossextend_kg.pipeline.attachment import build_embedding_top1_decisions


def test_task_candidates_are_seeded_as_task() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::BATOM_001:T1",
        domain_id="battery",
        label="BATOM_001:T1",
        description="",
        evidence_ids=["BATOM_001"],
        routing_features={
            "is_task_candidate": True,
            "task_step_id": "T1",
            "task_evidence_id": "BATOM_001",
        },
    )

    decisions = build_embedding_top1_decisions(
        candidates=[candidate],
        retrievals={candidate.candidate_id: []},
        historical_context={candidate.candidate_id: []},
        backbone_concepts={"Task", "Signal", "State", "Fault", "Component", "Asset"},
        allow_free_form_growth=False,
    )

    assert len(decisions) == 1
    assert decisions[0].route == "vertical_specialize"
    assert decisions[0].parent_anchor == "Task"
    assert decisions[0].accept is True


def test_semantic_hint_overrides_wrong_task_anchor_for_signal_like_candidate() -> None:
    candidate = SchemaCandidate(
        candidate_id="battery::coolant level",
        domain_id="battery",
        label="coolant level",
        description="measured coolant level",
        evidence_ids=["BATOM_001"],
        routing_features={
            "relation_families": ["communication"],
            "semantic_type_hint": "Signal",
        },
    )

    decisions = build_embedding_top1_decisions(
        candidates=[candidate],
        retrievals={
            candidate.candidate_id: [RetrievedAnchor(anchor="Task", score=0.95, rank=1)]
        },
        historical_context={candidate.candidate_id: []},
        backbone_concepts={"Task", "Signal", "State", "Fault", "Component", "Asset"},
        allow_free_form_growth=False,
    )

    assert len(decisions) == 1
    assert decisions[0].parent_anchor == "Signal"
    assert decisions[0].accept is True
