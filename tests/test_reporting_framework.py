from __future__ import annotations

from pathlib import Path

from crossextend_kg.experiments.reporting import (
    build_metrics_diff,
    compile_five_round_report,
    initialize_round_directory,
    update_run_manifest,
)


def test_initialize_round_directory_creates_templates(tmp_path: Path) -> None:
    round_dir = initialize_round_directory(
        base_dir=tmp_path,
        round_id="round_01",
        title="Test Round",
        scope=["BATOM_002"],
        config_path="config.json",
        run_commands=["python -m crossextend_kg.cli run --config config.json"],
    )

    assert round_dir.exists()
    assert (round_dir / "run_manifest.json").exists()
    assert (round_dir / "round_summary.md").exists()
    assert (round_dir / "dataflow_audit.md").exists()


def test_build_metrics_diff_computes_expected_delta() -> None:
    baseline = {
        "graph_path": "baseline.json",
        "concept_metrics": {"precision": 0.5, "recall": 0.6, "f1": 0.55},
        "anchor_metrics": {"accuracy": 0.7, "macro_f1": 0.65},
        "relation_metrics": {"precision": 0.2, "recall": 0.3, "f1": 0.24},
        "predicted_counts": {"concepts": 10, "relations": 8},
        "gold_counts": {"concepts": 9, "relations": 7},
    }
    post = {
        "graph_path": "post.json",
        "concept_metrics": {"precision": 0.6, "recall": 0.7, "f1": 0.64},
        "anchor_metrics": {"accuracy": 0.8, "macro_f1": 0.75},
        "relation_metrics": {"precision": 0.4, "recall": 0.5, "f1": 0.44},
        "predicted_counts": {"concepts": 11, "relations": 6},
        "gold_counts": {"concepts": 9, "relations": 7},
    }

    diff = build_metrics_diff(baseline, post)

    assert diff["metrics"]["concept_metrics.f1"]["delta"] == 0.09
    assert diff["metrics"]["relation_metrics.f1"]["delta"] == 0.2
    assert diff["counts"]["predicted_counts.relations"]["delta"] == -2


def test_compile_five_round_report_reads_round_outputs(tmp_path: Path) -> None:
    round_dir = initialize_round_directory(
        base_dir=tmp_path,
        round_id="round_01",
        title="Test Round",
        scope=["BATOM_002"],
    )
    update_run_manifest(
        round_dir,
        {
            "title": "Test Round",
            "scope": ["BATOM_002"],
            "notes": "Reduced relation noise",
            "status": "completed",
        },
    )
    (round_dir / "post_metrics.json").write_text(
        """{
  "concept_metrics": {"f1": 0.8},
  "anchor_metrics": {"accuracy": 0.9, "macro_f1": 0.88},
  "relation_metrics": {"f1": 0.6}
}
""",
        encoding="utf-8",
    )
    (round_dir / "metrics_diff.json").write_text(
        """{
  "metrics": {
    "relation_metrics.f1": {"delta": 0.12}
  }
}
""",
        encoding="utf-8",
    )
    output_path = tmp_path / "FIVE_ROUND_OPTIMIZATION_REPORT.md"

    compile_five_round_report(tmp_path, output_path)
    report = output_path.read_text(encoding="utf-8")

    assert "## 1. Background And Goal" in report
    assert "## 3. Five-Round Overview" in report
    assert "| Round | Modification Theme | Impact Module | Result |" in report
    assert "## 4. Round 1 Detailed Record" in report
    assert "Reduced relation noise" in report
    assert "## 9. Five-Round Metrics Change Table" in report
    assert "| Round | Concept F1 | Anchor Acc | Anchor Macro-F1 | Relation F1 |" in report
    assert "## 10. Five-Round Dataflow Change Table" in report
    assert "## 11. Five-Round Code Logic And Architecture Change Table" in report
    assert "## 14. Current Remaining Risks" in report
    assert "| Round | Open / Closed Status | Evidence |" in report
