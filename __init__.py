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
    "EmbeddingBackendError",
    "EvidenceLoadError",
    "GraphAssemblyError",
    "LLMBackendError",
    "PipelineConfig",
    "configure_logging",
    "get_logger",
    "load_pipeline_config",
    "run_pipeline",
    "run_pipeline_for_domains",
    "validate_domain_id",
    "validate_label",
    "validate_positive_int",
    "validate_relation_family",
    "validate_route",
    "validate_score_range",
    "validate_variant_id",
]
