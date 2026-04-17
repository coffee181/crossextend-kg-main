#!/usr/bin/env python3
"""Preprocessing module for converting raw industrial documents to EvidenceRecords.

This module provides tools to:
- Parse markdown documents (fault cases, product introductions, maintenance logs)
- Extract concepts and relations using LLM
- Generate EvidenceRecords compatible with CrossExtend-KG pipeline

Supported directory structure:
    data_root/
    ├── battery/
    │   ├── products/*.md
    │   └── fault_cases/*.md
    ├── cnc/
    │   ├── products/*.md
    │   └── fault_cases/*.md
    └── nev/
    │   ├── products/*.md
    │   └── fault_cases/*.md

Public API:
- run_preprocessing: Full preprocessing pipeline from config
- preprocess_single_document: Convenience function for single files
- load_preprocessing_config: Load config from JSON file
"""

from __future__ import annotations

from .models import DocumentInput, ExtractionResult, PreprocessingConfig, PreprocessingResult
from .parser import (
    parse_markdown_file,
    parse_markdown_directory,
    parse_domain_directory,
    parse_multi_domain_directory,
    classify_doc_type,
    normalize_content,
)
from .processor import run_preprocessing, preprocess_single_document, load_preprocessing_config
from .extractor import LLMExtractor, build_extractor

__all__ = [
    # Models
    "DocumentInput",
    "ExtractionResult",
    "PreprocessingConfig",
    "PreprocessingResult",
    # Parser
    "parse_markdown_file",
    "parse_markdown_directory",
    "parse_domain_directory",
    "parse_multi_domain_directory",
    "classify_doc_type",
    "normalize_content",
    # Processor
    "run_preprocessing",
    "preprocess_single_document",
    "load_preprocessing_config",
    # Extractor
    "LLMExtractor",
    "build_extractor",
]