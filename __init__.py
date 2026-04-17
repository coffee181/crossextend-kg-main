"""CrossExtend-KG: Backbone-Guided Adapter Schema Construction for Industrial Knowledge Graphs.

This package implements a framework for generalized industrial KG construction
via backbone-guided adapter schema construction.

Main components:
- config: Configuration loading and validation
- pipeline: Core pipeline implementation
- backends: LLM and embedding backends
- rules: Constraint-based filtering
- memory: Temporal memory bank for retrieval-augmented construction

Quick start:
    from crossextend_kg import load_pipeline_config, run_pipeline

    config = load_pipeline_config("config/persistent/pipeline.deepseek.json")
    result = run_pipeline("config/persistent/pipeline.deepseek.json")
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
    MemoryBankError,
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
    "MemoryBankError",
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
    # Version
    "__version__",
]

