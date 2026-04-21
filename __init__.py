"""CrossExtend-KG: Backbone-Guided Adapter Schema Construction for Industrial Knowledge Graphs.

This package implements a framework for generalized industrial KG construction
via backbone-guided adapter schema construction.

Main components:
- config: Configuration loading and validation
- pipeline: Core pipeline implementation
- backends: LLM and embedding backends
- rules: Constraint-based filtering

Quick start:
    from crossextend_kg import load_pipeline_config, run_pipeline

    config = load_pipeline_config("config/persistent/pipeline.deepseek.yaml")
    result = run_pipeline("config/persistent/pipeline.deepseek.yaml")
"""

from .config import load_pipeline_config, PipelineConfig
from .pipeline import run_pipeline
from .exceptions import (
    CrossExtendKGError,
    ConfigValidationError,
    EvidenceLoadError,
    BackboneConstructionError,
    AttachmentDecisionError,
    GraphAssemblyError,
    ArtifactExportError,
    LLMBackendError,
    EmbeddingBackendError,
)
from .validation import (
    validate_domain_id,
    validate_variant_id,
    validate_label,
    validate_relation_family,
    validate_route,
    validate_score_range,
    validate_positive_int,
)
from .logging_config import configure_logging, get_logger
from .experiments import (
    aggregate_metric_payloads,
    aggregate_repeated_evaluations,
    build_default_ablation_variants,
    build_rule_records_by_domain,
    compare_variant_evaluations,
    collect_variant_audit_summary,
    compute_metrics,
    evaluate_round_variant,
    evaluate_variant_run,
    materialize_ablation_config,
    materialize_round_pipeline_config,
    materialize_round_preprocessing_config,
    prepare_round_workspace,
    resolve_gold_file,
    resolve_full_gold_alignment,
    run_ablation_experiment,
    run_baseline_suite,
    rule_extract_document,
    stage_aligned_input_corpus,
)

__version__ = "0.1.0"

__all__ = [
    # Main API
    "load_pipeline_config",
    "run_pipeline",
    "PipelineConfig",
    # Exceptions
    "CrossExtendKGError",
    "ConfigValidationError",
    "EvidenceLoadError",
    "BackboneConstructionError",
    "AttachmentDecisionError",
    "GraphAssemblyError",
    "ArtifactExportError",
    "LLMBackendError",
    "EmbeddingBackendError",
    # Validation
    "validate_domain_id",
    "validate_variant_id",
    "validate_label",
    "validate_relation_family",
    "validate_route",
    "validate_score_range",
    "validate_positive_int",
    # Logging
    "configure_logging",
    "get_logger",
    "aggregate_metric_payloads",
    "aggregate_repeated_evaluations",
    "build_default_ablation_variants",
    "build_rule_records_by_domain",
    "compare_variant_evaluations",
    "collect_variant_audit_summary",
    "compute_metrics",
    "evaluate_round_variant",
    "evaluate_variant_run",
    "materialize_ablation_config",
    "materialize_round_pipeline_config",
    "materialize_round_preprocessing_config",
    "prepare_round_workspace",
    "resolve_gold_file",
    "resolve_full_gold_alignment",
    "run_ablation_experiment",
    "run_baseline_suite",
    "rule_extract_document",
    "stage_aligned_input_corpus",
    # Version
    "__version__",
]
