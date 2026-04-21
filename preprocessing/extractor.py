#!/usr/bin/env python3
"""LLM-based extraction for concepts and relations from O&M manuals."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from backends.llm import build_llm_backend
from pipeline.utils import render_prompt_template
from preprocessing.models import DocumentInput, ExtractionResult, PreprocessingConfig


def load_extraction_prompt(
    prompt_template_path: str,
    backbone_concepts: list[str],
    relation_families: list[str],
) -> str:
    """Load and format extraction prompt template."""
    backbone_json = json.dumps(backbone_concepts, ensure_ascii=False, indent=2)
    relation_json = json.dumps(relation_families, ensure_ascii=False, indent=2)
    template = Path(prompt_template_path).read_text(encoding="utf-8")
    return render_prompt_template(
        template,
        {
            "__BACKBONE_CONCEPTS_JSON__": backbone_json,
            "__RELATION_FAMILIES_JSON__": relation_json,
        },
    )
class LLMExtractor:
    """LLM-based concept/relation extractor for the active O&M corpus."""

    def __init__(self, config: PreprocessingConfig):
        self.config = config
        self._llm_backend = build_llm_backend(config.llm)

        self._prompt_template = load_extraction_prompt(
            config.prompt_template_path,
            config.backbone_concepts,
            config.relation_families,
        )

    def extract(self, doc: DocumentInput) -> ExtractionResult:
        """Extract concepts and relations from a single document."""
        start_time = time.time()

        prompt = render_prompt_template(
            self._prompt_template,
            {"__DOCUMENT_CONTENT__": doc.content},
        )

        response = self._call_llm(prompt)
        result = self._parse_response(response, doc.doc_id)
        result.llm_model = self.config.llm.model
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result

    def extract_batch(self, docs: list[DocumentInput]) -> list[ExtractionResult]:
        """Extract from multiple documents."""
        return [self.extract(doc) for doc in docs]

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """Call LLM API and return JSON response."""
        return self._llm_backend.generate_json(prompt)

    def _parse_response(self, response: dict, doc_id: str) -> ExtractionResult:
        """Parse LLM response into ExtractionResult."""
        concepts = response.get("concepts", [])
        relations = response.get("relations", [])
        quality = response.get("extraction_quality", "unknown")

        return ExtractionResult(
            doc_id=doc_id,
            concepts=concepts,
            relations=relations,
            extraction_quality=quality
        )


def build_extractor(config: PreprocessingConfig) -> LLMExtractor:
    """Build LLM extractor from config."""
    return LLMExtractor(config)
