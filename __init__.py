"""CrossExtend-KG public package surface."""

from .config import PipelineConfig, load_pipeline_config
from .exceptions import (
    ArtifactExportError,
    AttachmentDecisionError,
    BackboneConstructionError,
    ConfigValidationError,
    CrossExtendKGError,
    EmbeddingBackendError,
    EvidenceLoadError,
    GraphAssemblyError,
    LLMBackendError,
)
from .experiments import (
    DownstreamBenchmark,
    RepairSuffixRankingSample,
    SuffixCandidate,
    WorkflowRetrievalSample,
    aggregate_metric_payloads,
    compute_metrics,
    evaluate_variant_run,
    load_downstream_benchmark,
    resolve_gold_file,
    write_evaluation_csv,
)
from .logging_config import configure_logging, get_logger
from .pipeline import run_pipeline, run_pipeline_for_domains
from .validation import (
    validate_domain_id,
    validate_label,
    validate_positive_int,
    validate_relation_family,
    validate_route,
    validate_score_range,
    validate_variant_id,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ArtifactExportError",
    "AttachmentDecisionError",
    "BackboneConstructionError",
    "ConfigValidationError",
    "CrossExtendKGError",
    "DownstreamBenchmark",
    "EmbeddingBackendError",
    "EvidenceLoadError",
    "GraphAssemblyError",
    "LLMBackendError",
    "PipelineConfig",
    "RepairSuffixRankingSample",
    "SuffixCandidate",
    "WorkflowRetrievalSample",
    "aggregate_metric_payloads",
    "compute_metrics",
    "configure_logging",
    "evaluate_variant_run",
    "get_logger",
    "load_downstream_benchmark",
    "load_pipeline_config",
    "resolve_gold_file",
    "run_pipeline",
    "run_pipeline_for_domains",
    "validate_domain_id",
    "validate_label",
    "validate_positive_int",
    "validate_relation_family",
    "validate_route",
    "validate_score_range",
    "validate_variant_id",
    "write_evaluation_csv",
]
