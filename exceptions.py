#!/usr/bin/env python3
"""Pipeline exceptions and error handling."""

from __future__ import annotations


class CrossExtendKGError(Exception):
    """Base exception for CrossExtend-KG pipeline errors."""
    pass


class ConfigValidationError(CrossExtendKGError):
    """Configuration validation failed."""
    pass


class EvidenceLoadError(CrossExtendKGError):
    """Failed to load evidence records from data source."""
    pass


class BackboneConstructionError(CrossExtendKGError):
    """Failed to construct backbone (predefined or dynamic extraction)."""
    pass


class AttachmentDecisionError(CrossExtendKGError):
    """Failed to generate attachment decisions."""
    pass


class GraphAssemblyError(CrossExtendKGError):
    """Failed to assemble domain graph."""
    pass


class ArtifactExportError(CrossExtendKGError):
    """Failed to export pipeline artifacts."""
    pass


class MemoryBankError(CrossExtendKGError):
    """MemoryBank operation failed."""
    pass


class LLMBackendError(CrossExtendKGError):
    """LLM backend operation failed."""
    pass


class EmbeddingBackendError(CrossExtendKGError):
    """Embedding backend operation failed."""
    pass