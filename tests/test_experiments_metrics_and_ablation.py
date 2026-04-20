from __future__ import annotations

import json
from pathlib import Path

from crossextend_kg.experiments.ablation import build_default_ablation_variants
from crossextend_kg.experiments.comparison import compare_variant_evaluations
from crossextend_kg.experiments.metrics import aggregate_metric_payloads, compute_metrics, evaluate_variant_run


def test_compute_metrics_filters_domain_graph_by_gold_provenance(tmp_path: Path) -> None:
    gold_path = tmp_path / "battery_BATOM_002.json"
    graph_path = tmp_path / "final_graph.json"

    gold_path.write_text(
        json.dumps(
            {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_002", "doc_type": "om_manual"}],
                "concept_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "label": "T1",
                        "should_be_in_graph": True,
                        "expected_anchor": "Task",
                    },
                    {
                        "evidence_id": "BATOM_002",
                        "label": "coolant level",
                        "should_be_in_graph": True,
                        "expected_anchor": "Signal",
                    },
                ],
                "relation_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "head": "T1",
                        "relation": "observes",
                        "tail": "coolant level",
                        "family": "task_dependency",
                        "valid": True,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "label": "BATOM_002:T1",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Task",
                        "provenance_evidence_ids": ["BATOM_002"],
                    },
                    {
                        "label": "coolant level",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Signal",
                        "provenance_evidence_ids": ["BATOM_002"],
                    },
                    {
                        "label": "other document fault",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Fault",
                        "provenance_evidence_ids": ["BATOM_999"],
                    },
                ],
                "edges": [
                    {
                        "head": "BATOM_002:T1",
                        "label": "observes",
                        "tail": "coolant level",
                        "family": "task_dependency",
                        "provenance_evidence_ids": ["BATOM_002"],
                    },
                    {
                        "head": "other document fault",
                        "label": "causes",
                        "tail": "coolant level",
                        "family": "propagation",
                        "provenance_evidence_ids": ["BATOM_999"],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics = compute_metrics(gold_path, graph_path)

    assert metrics["concept_metrics"]["f1"] == 1.0
    assert metrics["concept_label_metrics"]["f1"] == 1.0
    assert metrics["relation_metrics"]["f1"] == 1.0
    assert metrics["anchor_metrics"]["accuracy"] == 1.0


def test_compute_metrics_penalizes_anchor_mismatch_in_concept_metrics(tmp_path: Path) -> None:
    gold_path = tmp_path / "battery_BATOM_002.json"
    graph_path = tmp_path / "final_graph.json"

    gold_path.write_text(
        json.dumps(
            {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_002", "doc_type": "om_manual"}],
                "concept_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "label": "coolant level",
                        "should_be_in_graph": True,
                        "expected_anchor": "Signal",
                    }
                ],
                "relation_ground_truth": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "label": "coolant level",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Fault",
                        "provenance_evidence_ids": ["BATOM_002"],
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics = compute_metrics(gold_path, graph_path)

    assert metrics["concept_metrics"]["f1"] == 0.0
    assert metrics["concept_label_metrics"]["f1"] == 1.0
    assert metrics["anchor_metrics"]["accuracy"] == 0.0


def test_compute_metrics_emits_relaxed_diagnostics_for_alias_and_family_confusion(tmp_path: Path) -> None:
    gold_path = tmp_path / "battery_BATOM_002.json"
    graph_path = tmp_path / "final_graph.json"

    gold_path.write_text(
        json.dumps(
            {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_002", "doc_type": "om_manual"}],
                "concept_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "label": "stress whitening",
                        "should_be_in_graph": True,
                        "expected_anchor": "Signal",
                    }
                ],
                "relation_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "head": "stress whitening",
                        "relation": "indicates",
                        "tail": "cracked shell",
                        "family": "communication",
                        "valid": True,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "label": "plastic stress whitening",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Signal",
                        "provenance_evidence_ids": ["BATOM_002"],
                    }
                ],
                "edges": [
                    {
                        "head": "plastic stress whitening",
                        "label": "indicates",
                        "tail": "cracked shell",
                        "family": "propagation",
                        "provenance_evidence_ids": ["BATOM_002"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics = compute_metrics(gold_path, graph_path)

    assert metrics["concept_label_metrics"]["f1"] == 0.0
    assert metrics["relation_metrics"]["f1"] == 0.0
    assert metrics["diagnostic_metrics"]["concept_relaxed_label_metrics"]["f1"] == 1.0
    assert metrics["diagnostic_metrics"]["relation_family_agnostic_metrics"]["f1"] == 1.0
    assert metrics["diagnostic_examples"]["concept_alias_hits"]
    assert metrics["diagnostic_examples"]["relation_family_confusions"]


def test_build_default_ablation_variants_returns_expected_matrix() -> None:
    base_variant = {
        "variant_id": "placeholder",
        "description": "placeholder",
        "attachment_strategy": "llm",
        "use_embedding_routing": True,
        "use_rule_filter": True,
        "allow_free_form_growth": False,
        "enable_snapshots": True,
        "enable_memory_bank": True,
        "export_artifacts": True,
    }

    variants = build_default_ablation_variants(base_variant)
    variant_ids = [item["variant_id"] for item in variants]

    assert variant_ids == [
        "full_llm",
        "no_memory_bank",
        "no_rule_filter",
        "no_embedding_routing",
        "embedding_top1",
        "deterministic",
    ]


def test_aggregate_metric_payloads_builds_macro_summary() -> None:
    payload = aggregate_metric_payloads(
        {
            "battery_BATOM_002.json": {
                "documents": ["BATOM_002"],
                "concept_metrics": {"precision": 0.9, "recall": 0.8, "f1": 0.8471},
                "concept_label_metrics": {"precision": 1.0, "recall": 0.9, "f1": 0.9474},
                "anchor_metrics": {"accuracy": 1.0, "macro_f1": 0.95, "support": 10},
                "relation_metrics": {"precision": 0.7, "recall": 0.6, "f1": 0.6462},
                "diagnostic_metrics": {
                    "concept_relaxed_label_metrics": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
                    "relation_relaxed_metrics": {"precision": 0.8, "recall": 0.7, "f1": 0.7467},
                    "relation_family_agnostic_metrics": {"precision": 0.9, "recall": 0.8, "f1": 0.8471},
                },
                "predicted_counts": {"concepts": 12, "relations": 8},
                "gold_counts": {"concepts": 10, "relations": 7},
            },
            "cnc_CNCOM_002.json": {
                "documents": ["CNCOM_002"],
                "concept_metrics": {"precision": 0.8, "recall": 0.9, "f1": 0.8471},
                "concept_label_metrics": {"precision": 0.9, "recall": 1.0, "f1": 0.9474},
                "anchor_metrics": {"accuracy": 0.8, "macro_f1": 0.85, "support": 8},
                "relation_metrics": {"precision": 0.6, "recall": 0.7, "f1": 0.6462},
                "diagnostic_metrics": {
                    "concept_relaxed_label_metrics": {"precision": 0.9, "recall": 1.0, "f1": 0.9474},
                    "relation_relaxed_metrics": {"precision": 0.7, "recall": 0.8, "f1": 0.7467},
                    "relation_family_agnostic_metrics": {"precision": 0.8, "recall": 0.9, "f1": 0.8471},
                },
                "predicted_counts": {"concepts": 9, "relations": 6},
                "gold_counts": {"concepts": 11, "relations": 8},
            },
        }
    )

    assert payload["concept_metrics"]["precision"] == 0.85
    assert payload["concept_label_metrics"]["f1"] == 0.9474
    assert payload["anchor_metrics"]["accuracy"] == 0.9
    assert payload["relation_metrics"]["f1"] == 0.6462
    assert payload["diagnostic_metrics"]["relation_relaxed_metrics"]["f1"] == 0.7467
    assert payload["predicted_counts"]["concepts"] == 21
    assert payload["gold_counts"]["relations"] == 15


def test_evaluate_variant_run_returns_aggregate_sections(tmp_path: Path) -> None:
    ground_truth_dir = tmp_path / "ground_truth"
    variant_root = tmp_path / "benchmark" / "full_llm" / "working" / "battery"
    ground_truth_dir.mkdir(parents=True)
    variant_root.mkdir(parents=True)

    gold_path = ground_truth_dir / "battery_BATOM_002.json"
    gold_path.write_text(
        json.dumps(
            {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_002", "doc_type": "om_manual"}],
                "concept_ground_truth": [
                    {
                        "evidence_id": "BATOM_002",
                        "label": "T1",
                        "should_be_in_graph": True,
                        "expected_anchor": "Task",
                    }
                ],
                "relation_ground_truth": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (variant_root / "final_graph.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "label": "BATOM_002:T1",
                        "node_type": "adapter_concept",
                        "parent_anchor": "Task",
                        "provenance_evidence_ids": ["BATOM_002"],
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    evaluation = evaluate_variant_run(
        run_root=tmp_path / "benchmark",
        variant_id="full_llm",
        ground_truth_dir=ground_truth_dir,
    )

    assert evaluation["concept_metrics"]["f1"] == 1.0
    assert evaluation["concept_label_metrics"]["f1"] == 1.0
    assert evaluation["anchor_metrics"]["accuracy"] == 1.0
    assert evaluation["macro_average"]["concept_f1"] == 1.0
    assert evaluation["macro_average"]["concept_relaxed_label_f1"] == 1.0
    assert evaluation["evaluated_gold_files"] == ["battery_BATOM_002.json"]


def test_compare_variant_evaluations_returns_deltas_and_ranking() -> None:
    evaluations = {
        "full_llm": {
            "evaluated_gold_files": ["battery_BATOM_002.json"],
            "macro_average": {
                "concept_f1": 0.90,
                "concept_label_f1": 0.94,
                "anchor_accuracy": 0.95,
                "anchor_macro_f1": 0.94,
                "relation_f1": 0.82,
                "concept_relaxed_label_f1": 0.97,
                "relation_relaxed_f1": 0.88,
                "relation_family_agnostic_f1": 0.91,
            },
        },
        "no_memory_bank": {
            "evaluated_gold_files": ["battery_BATOM_002.json"],
            "macro_average": {
                "concept_f1": 0.88,
                "concept_label_f1": 0.93,
                "anchor_accuracy": 0.93,
                "anchor_macro_f1": 0.92,
                "relation_f1": 0.79,
                "concept_relaxed_label_f1": 0.95,
                "relation_relaxed_f1": 0.85,
                "relation_family_agnostic_f1": 0.89,
            },
        },
        "deterministic": {
            "evaluated_gold_files": ["battery_BATOM_002.json"],
            "macro_average": {
                "concept_f1": 0.84,
                "concept_label_f1": 0.90,
                "anchor_accuracy": 0.88,
                "anchor_macro_f1": 0.87,
                "relation_f1": 0.70,
                "concept_relaxed_label_f1": 0.92,
                "relation_relaxed_f1": 0.79,
                "relation_family_agnostic_f1": 0.84,
            },
        },
    }

    comparison = compare_variant_evaluations(evaluations, baseline_variant="full_llm")

    assert comparison["baseline_variant"] == "full_llm"
    assert comparison["variant_rows"][0]["variant_id"] == "full_llm"
    assert comparison["best_variant_by_metric"]["relation_f1"] == "full_llm"
    delta_rows = {row["variant_id"]: row for row in comparison["deltas_vs_baseline"]}
    assert delta_rows["no_memory_bank"]["relation_f1_delta"] == -0.03
    assert delta_rows["deterministic"]["concept_relaxed_label_f1_delta"] == -0.05
