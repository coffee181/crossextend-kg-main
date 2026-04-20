#!/usr/bin/env python3
"""Experiment utilities for metrics, ablations, comparisons, and reporting."""

from .ablation import (
    DEFAULT_ABLATION_SPECS,
    build_default_ablation_variants,
    main as ablation_main,
    materialize_ablation_config,
    run_ablation_experiment,
)
from .comparison import (
    build_variant_summary_rows,
    compare_variant_evaluations,
    write_comparison_csv,
)
from .metrics import (
    aggregate_metric_payloads,
    classification_metrics,
    compute_metrics,
    evaluate_variant_run,
    f1_score,
    list_gold_files,
    normalize_step_label,
    resolve_gold_file,
    safe_div,
    set_metrics,
    write_ablation_csv,
)
from .reporting import (
    ROUND_TEXT_FILES,
    compile_five_round_report,
    initialize_round_directory,
    summarize_graph_artifacts,
    update_run_manifest,
    write_metrics_diff,
)
from .rounds import (
    DEFAULT_FULL_GOLD_ALIGNMENT,
    collect_variant_audit_summary,
    evaluate_round_variant,
    expected_preprocessing_outputs,
    materialize_round_pipeline_config,
    materialize_round_preprocessing_config,
    prepare_round_workspace,
    resolve_full_gold_alignment,
    stage_aligned_input_corpus,
)

__all__ = [
    "DEFAULT_ABLATION_SPECS",
    "ablation_main",
    "build_default_ablation_variants",
    "build_variant_summary_rows",
    "compare_variant_evaluations",
    "materialize_ablation_config",
    "run_ablation_experiment",
    "aggregate_metric_payloads",
    "classification_metrics",
    "compute_metrics",
    "evaluate_variant_run",
    "f1_score",
    "list_gold_files",
    "normalize_step_label",
    "resolve_gold_file",
    "safe_div",
    "set_metrics",
    "write_ablation_csv",
    "write_comparison_csv",
    "ROUND_TEXT_FILES",
    "compile_five_round_report",
    "initialize_round_directory",
    "summarize_graph_artifacts",
    "update_run_manifest",
    "write_metrics_diff",
    "DEFAULT_FULL_GOLD_ALIGNMENT",
    "collect_variant_audit_summary",
    "evaluate_round_variant",
    "expected_preprocessing_outputs",
    "materialize_round_pipeline_config",
    "materialize_round_preprocessing_config",
    "prepare_round_workspace",
    "resolve_full_gold_alignment",
    "stage_aligned_input_corpus",
]
