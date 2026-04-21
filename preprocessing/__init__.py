#!/usr/bin/env python3
"""Preprocessing entrypoints for converting O&M markdown into EvidenceRecords.

The active preprocessing path supports:
- O&M markdown manuals
- step-aware extraction from table rows such as `T1`, `T2`, `T3`
- current raw directory layouts such as:
  - `battery/` or `battery_om_manual_en/`
  - `cnc/` or `cnc_om_manual_en/`
  - `nev/` or `nev_om_manual_en/` or `ev_om_manual_en/`

Public API:
- `run_preprocessing`
- `preprocess_single_document`
- `load_preprocessing_config`
"""

from __future__ import annotations

from preprocessing.extractor import LLMExtractor, build_extractor
from preprocessing.models import DocumentInput, ExtractionResult, PreprocessingConfig, PreprocessingResult
from preprocessing.parser import (
    classify_doc_type,
    infer_doc_type_from_filename,
    normalize_content,
    parse_markdown_directory,
    parse_markdown_file,
    parse_multi_domain_directory,
)
from preprocessing.processor import load_preprocessing_config, preprocess_single_document, run_preprocessing

__all__ = [
    "DocumentInput",
    "ExtractionResult",
    "PreprocessingConfig",
    "PreprocessingResult",
    "parse_markdown_file",
    "parse_markdown_directory",
    "parse_multi_domain_directory",
    "classify_doc_type",
    "infer_doc_type_from_filename",
    "normalize_content",
    "run_preprocessing",
    "preprocess_single_document",
    "load_preprocessing_config",
    "LLMExtractor",
    "build_extractor",
]
