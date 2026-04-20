from __future__ import annotations

from crossextend_kg.models import ConceptMention, EvidenceRecord, RelationMention, StepConceptMention, StepRecord
from crossextend_kg.pipeline.evidence import aggregate_schema_candidates


def test_task_candidates_are_scoped_by_evidence_and_step() -> None:
    record = EvidenceRecord(
        evidence_id="BATOM_001",
        domain_id="battery",
        source_type="om_manual",
        timestamp="2026-04-19T00:00:00Z",
        raw_text="| T1 | Inspect coolant level. |",
        step_records=[
            StepRecord(
                step_id="T1",
                task=StepConceptMention(label="T1", surface_form="Inspect coolant level."),
                concept_mentions=[
                    ConceptMention(
                        label="coolant level",
                        description="measured coolant level",
                        surface_form="coolant level",
                        semantic_type_hint="Signal",
                    )
                ],
                relation_mentions=[
                    RelationMention(
                        label="observes",
                        family="task_dependency",
                        head="T1",
                        tail="coolant level",
                    ),
                    RelationMention(
                        label="triggers",
                        family="task_dependency",
                        head="T1",
                        tail="T2",
                    ),
                ],
            ),
            StepRecord(
                step_id="T2",
                task=StepConceptMention(label="T2", surface_form="Close inspection."),
            ),
        ],
    )

    candidates = aggregate_schema_candidates({"battery": [record]})["battery"]
    by_label = {candidate.label: candidate for candidate in candidates}

    assert "BATOM_001:T1" in by_label
    assert "BATOM_001:T2" in by_label
    assert by_label["BATOM_001:T1"].candidate_id == "battery::BATOM_001:T1"
    assert by_label["BATOM_001:T1"].routing_features["is_task_candidate"] is True
    assert by_label["BATOM_001:T1"].routing_features["task_step_id"] == "T1"
    assert by_label["BATOM_001:T1"].routing_features["task_evidence_id"] == "BATOM_001"
    assert by_label["coolant level"].routing_features["step_ids"] == ["T1"]
    assert by_label["coolant level"].routing_features["semantic_type_hint"] == "Signal"


def test_runtime_label_normalization_collapses_stable_and_handle_variants() -> None:
    record = EvidenceRecord(
        evidence_id="EVMAN_003",
        domain_id="nev",
        source_type="om_manual",
        timestamp="2026-04-19T00:00:00Z",
        raw_text="| T1 | Verify disconnect seating. |",
        step_records=[
            StepRecord(
                step_id="T1",
                task=StepConceptMention(label="T1", surface_form="Verify disconnect seating."),
                concept_mentions=[
                    ConceptMention(label="HVIL path stable", surface_form="HVIL path stable"),
                    ConceptMention(label="orange handle sits proud", surface_form="orange handle sits proud"),
                    ConceptMention(label="handle flush with cover plane", surface_form="handle flush with cover plane"),
                ],
                relation_mentions=[
                    RelationMention(
                        label="observes",
                        family="task_dependency",
                        head="T1",
                        tail="HVIL path stable",
                    )
                ],
            )
        ],
    )

    candidates = aggregate_schema_candidates({"nev": [record]})["nev"]
    labels = {candidate.label for candidate in candidates}

    assert "HVIL path" in labels
    assert "handle proud" in labels
    assert "handle flushness" in labels
    assert "HVIL path stable" not in labels
    assert "orange handle sits proud" not in labels
