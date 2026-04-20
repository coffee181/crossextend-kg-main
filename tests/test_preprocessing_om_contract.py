from __future__ import annotations

from pathlib import Path

import pytest

from crossextend_kg.preprocessing.parser import (
    classify_doc_type,
    infer_doc_type_from_filename,
    parse_markdown_file,
    parse_multi_domain_directory,
)
from crossextend_kg.preprocessing.models import DocumentInput, ExtractionResult
from crossextend_kg.preprocessing.processor import extraction_to_evidence_record


def test_infer_doc_type_from_filename_for_active_om_files() -> None:
    assert infer_doc_type_from_filename(Path("BATOM_001.md")) == "om_manual"
    assert infer_doc_type_from_filename(Path("CNCOM_001.md")) == "om_manual"
    assert infer_doc_type_from_filename(Path("EVMAN_001.md")) == "om_manual"


def test_parse_markdown_file_strips_utf8_bom(tmp_path: Path) -> None:
    file_path = tmp_path / "BATOM_001.md"
    file_path.write_text(
        "\ufeff| Time step | O&M sample text |\n|---|---|\n| T1 | Inspect coolant level. |\n",
        encoding="utf-8",
    )

    document = parse_markdown_file(
        file_path=file_path,
        domain_id="battery",
        role="target",
        doc_type="om_manual",
    )

    assert not document.content.startswith("\ufeff")


def test_classify_doc_type_rejects_non_om_content() -> None:
    with pytest.raises(ValueError, match="active om_manual content contract"):
        classify_doc_type("# Product Specification\n\nRated voltage and brochure details.")


def test_parse_multi_domain_directory_rejects_unrecognized_markdown(tmp_path: Path) -> None:
    battery_dir = tmp_path / "battery"
    battery_dir.mkdir()
    (battery_dir / "misc_notes.md").write_text("This file has no time-step O&M structure.", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported markdown input"):
        parse_multi_domain_directory(tmp_path, ["battery"], "target")


def test_extraction_to_evidence_record_preserves_step_ids_and_surface_form() -> None:
    doc = DocumentInput(
        doc_id="BATOM_001",
        doc_type="om_manual",
        domain_id="battery",
        content="| Time step | O&M sample text |\n|---|---|\n| T1 | Record coolant level. |\n| T2 | Close inspection. |\n",
    )
    extraction = ExtractionResult(
        doc_id="BATOM_001",
        concepts=[
            {"label": "T1 Record Coolant Condition", "description": "task title", "node_worthy": True},
            {
                "label": "coolant level",
                "description": "measured coolant level",
                "node_worthy": True,
                "parent_gold": "Signal",
            },
        ],
        relations=[
            {"label": "observes", "family": "task_dependency", "head": "T1 Record Coolant Condition", "tail": "coolant level"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)

    assert [step.step_id for step in record.step_records] == ["T1", "T2"]
    assert record.step_records[0].task.label == "T1"
    assert record.step_records[0].task.surface_form == "Record coolant level."
    assert record.step_records[0].concept_mentions[0].semantic_type_hint == "Signal"
    assert record.step_records[0].relation_mentions[0].head == "T1"


def test_extraction_to_evidence_record_canonicalizes_unique_document_aliases() -> None:
    doc = DocumentInput(
        doc_id="BATOM_002",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Inspect green O-ring and internal retainer seating. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_002",
        concepts=[
            {"label": "green O-ring", "description": "seal ring", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "O-ring", "description": "generic alias", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "internal retainer", "description": "retaining feature", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "retainer", "description": "generic alias", "node_worthy": True, "semantic_type_hint": "Component"},
        ],
        relations=[
            {"label": "observes", "family": "task_dependency", "head": "T1", "tail": "O-ring"},
            {"label": "requires", "family": "task_dependency", "head": "T1", "tail": "retainer"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    concept_labels = [concept.label for concept in record.step_records[0].concept_mentions]
    relation_tails = [relation.tail for relation in record.step_records[0].relation_mentions]

    assert concept_labels == ["green O-ring", "internal retainer"]
    assert relation_tails == ["green O-ring", "internal retainer"]


def test_extraction_to_evidence_record_prunes_contextual_structural_document_relations() -> None:
    doc = DocumentInput(
        doc_id="BATOM_002",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Verify the cooling branch connection. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_002",
        concepts=[
            {"label": "cooling branch", "description": "branch section", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "hose overmold", "description": "overmolded hose segment", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "internal retainer", "description": "retainer hardware", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "battery pack", "description": "battery pack assembly", "node_worthy": True, "semantic_type_hint": "Asset"},
            {"label": "chiller-inlet connector", "description": "connector assembly", "node_worthy": True, "semantic_type_hint": "Component"},
        ],
        relations=[
            {"label": "contains", "family": "structural", "head": "cooling branch", "tail": "hose overmold"},
            {"label": "contains", "family": "structural", "head": "cooling branch", "tail": "internal retainer"},
            {"label": "contains", "family": "structural", "head": "battery pack", "tail": "chiller-inlet connector"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    kept_edges = {(relation.head, relation.label, relation.tail) for relation in record.document_relation_mentions}

    assert ("cooling branch", "contains", "hose overmold") not in kept_edges
    assert ("chiller-inlet connector", "contains", "internal retainer") in kept_edges
    assert ("battery pack", "contains", "chiller-inlet connector") in kept_edges


def test_extraction_to_evidence_record_does_not_merge_component_into_signal_alias() -> None:
    doc = DocumentInput(
        doc_id="BATOM_002",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T2 | Expose the internal retainer. |\n"
            "| T3 | Inspect inner-retainer wear. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_002",
        concepts=[
            {"label": "internal retainer", "description": "retainer hardware", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "inner-retainer wear", "description": "wear evidence", "node_worthy": True, "semantic_type_hint": "Signal"},
        ],
        relations=[
            {"label": "exposes", "family": "task_dependency", "head": "T2", "tail": "internal retainer"},
            {"label": "observes", "family": "task_dependency", "head": "T3", "tail": "inner-retainer wear"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    t2_labels = {concept.label for concept in record.step_records[0].concept_mentions}
    t3_labels = {concept.label for concept in record.step_records[1].concept_mentions}

    assert "internal retainer" in t2_labels
    assert "inner-retainer wear" in t3_labels


def test_extraction_to_evidence_record_strips_contextual_prefixes_from_stable_labels() -> None:
    doc = DocumentInput(
        doc_id="EVMAN_002",
        doc_type="om_manual",
        domain_id="nev",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Record vehicle Aurex E-Motion-412 LR and nearby harness clip details. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="EVMAN_002",
        concepts=[
            {"label": "vehicle Aurex E-Motion-412 LR", "description": "named vehicle", "node_worthy": True, "semantic_type_hint": "Asset"},
            {"label": "nearby harness clip", "description": "nearby harness clip", "node_worthy": True, "semantic_type_hint": "Component"},
        ],
        relations=[
            {"label": "records", "family": "task_dependency", "head": "T1", "tail": "vehicle Aurex E-Motion-412 LR"},
            {"label": "records", "family": "task_dependency", "head": "T1", "tail": "nearby harness clip"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    labels = {concept.label for concept in record.step_records[0].concept_mentions}

    assert "Aurex E-Motion-412 LR" in labels
    assert "harness clip" in labels


def test_extraction_to_evidence_record_does_not_merge_distinguished_location_components() -> None:
    doc = DocumentInput(
        doc_id="BATOM_003",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Inspect the tube bead. |\n"
            "| T2 | Inspect the inlet tube bead. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_003",
        concepts=[
            {"label": "tube bead", "description": "general bead feature", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "inlet tube bead", "description": "inlet-side bead feature", "node_worthy": True, "semantic_type_hint": "Component"},
        ],
        relations=[
            {"label": "observes", "family": "task_dependency", "head": "T1", "tail": "tube bead"},
            {"label": "observes", "family": "task_dependency", "head": "T2", "tail": "inlet tube bead"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    t1_labels = {concept.label for concept in record.step_records[0].concept_mentions}
    t2_labels = {concept.label for concept in record.step_records[1].concept_mentions}

    assert "tube bead" in t1_labels
    assert "inlet tube bead" in t2_labels


def test_extraction_to_evidence_record_drops_contextual_structural_relation_without_stable_parent() -> None:
    doc = DocumentInput(
        doc_id="BATOM_002",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Inspect the cooling branch O-ring area. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_002",
        concepts=[
            {"label": "cooling branch", "description": "branch section", "node_worthy": True, "semantic_type_hint": "Component"},
            {"label": "green O-ring", "description": "seal ring", "node_worthy": True, "semantic_type_hint": "Component"},
        ],
        relations=[
            {"label": "contains", "family": "structural", "head": "cooling branch", "tail": "green O-ring"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)

    assert record.document_relation_mentions == []


def test_extraction_to_evidence_record_prefers_immediate_fault_target_for_local_damage_observations() -> None:
    doc = DocumentInput(
        doc_id="BATOM_002",
        doc_type="om_manual",
        domain_id="battery",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Inspect removed shell observations. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="BATOM_002",
        concepts=[
            {"label": "stress whitening", "description": "whitening on shell", "node_worthy": True, "semantic_type_hint": "Signal"},
            {"label": "latch-window distortion", "description": "distortion around latch window", "node_worthy": True, "semantic_type_hint": "Signal"},
            {"label": "witness marks", "description": "movement marks on shell", "node_worthy": True, "semantic_type_hint": "Signal"},
            {"label": "cracked shell", "description": "shell crack fault", "node_worthy": True, "semantic_type_hint": "Fault"},
            {"label": "broken latch ear", "description": "latch ear failure", "node_worthy": True, "semantic_type_hint": "Fault"},
            {"label": "bracket side load", "description": "off-axis side load root cause", "node_worthy": True, "semantic_type_hint": "Fault"},
        ],
        relations=[
            {"label": "indicates", "family": "communication", "head": "stress whitening", "tail": "bracket side load"},
            {"label": "indicates", "family": "communication", "head": "latch-window distortion", "tail": "bracket side load"},
            {"label": "indicates", "family": "communication", "head": "witness marks", "tail": "bracket side load"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    edges = {(relation.head, relation.label, relation.tail) for relation in record.document_relation_mentions}

    assert ("stress whitening", "indicates", "cracked shell") in edges
    assert ("latch-window distortion", "indicates", "broken latch ear") in edges
    assert ("witness marks", "indicates", "bracket side load") in edges


def test_extraction_to_evidence_record_does_not_overrewrite_plastic_stress_whitening() -> None:
    doc = DocumentInput(
        doc_id="EVMAN_002",
        doc_type="om_manual",
        domain_id="nev",
        content=(
            "| Time step | O&M sample text |\n"
            "|---|---|\n"
            "| T1 | Inspect whitening and side-load marks. |\n"
        ),
    )
    extraction = ExtractionResult(
        doc_id="EVMAN_002",
        concepts=[
            {"label": "plastic stress whitening", "description": "plastic whitening", "node_worthy": True, "semantic_type_hint": "Signal"},
            {"label": "side-load mark", "description": "mechanical stress history mark", "node_worthy": True, "semantic_type_hint": "Signal"},
            {"label": "connector shell failure", "description": "shell failure fault", "node_worthy": True, "semantic_type_hint": "Fault"},
        ],
        relations=[
            {"label": "indicates", "family": "communication", "head": "plastic stress whitening", "tail": "side-load mark"},
        ],
        extraction_quality="high",
    )

    record = extraction_to_evidence_record(doc, extraction)
    edges = {(relation.head, relation.label, relation.tail) for relation in record.document_relation_mentions}

    assert ("plastic stress whitening", "indicates", "side-load mark") in edges
    assert ("plastic stress whitening", "indicates", "connector shell failure") not in edges
