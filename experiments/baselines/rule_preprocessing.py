#!/usr/bin/env python3
"""Lightweight rule-based preprocessing for non-LLM baseline experiments."""

from __future__ import annotations

import re
from collections import OrderedDict
from datetime import timezone, datetime
from pathlib import Path
from typing import Any

try:
    from crossextend_kg.file_io import ensure_dir, write_json
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import ensure_dir, write_json
try:
    from crossextend_kg.models import EvidenceRecord
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import EvidenceRecord
from preprocessing.models import DocumentInput, ExtractionResult
from preprocessing.parser import normalize_content, parse_multi_domain_directory
from preprocessing.processor import extraction_to_evidence_record


_PHRASE_TOKEN = r"[A-Za-z0-9][A-Za-z0-9/-]*"
_STOPWORD_PREFIXES = {
    "the",
    "a",
    "an",
    "its",
    "their",
    "this",
    "that",
    "same",
    "exact",
}
_COMMAND_PREFIXES = {
    "record",
    "document",
    "inspect",
    "observe",
    "watch",
    "compare",
    "confirm",
    "measure",
    "apply",
    "repeat",
    "close",
    "install",
    "remove",
    "refit",
    "run",
    "trace",
    "mark",
    "photograph",
}
_GENERIC_LABELS = {
    "problem",
    "issue",
    "result",
    "state",
    "condition",
    "hardware",
    "history",
}
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")


def _compile_phrase_pattern(terminal_pattern: str) -> re.Pattern[str]:
    return re.compile(
        rf"\b(?:{_PHRASE_TOKEN}\s+){{0,3}}(?:{terminal_pattern})\b",
        re.IGNORECASE,
    )


_COMPONENT_PATTERN = _compile_phrase_pattern(
    r"connector|shell|retainer|o-?ring|hose|clip|rib|bead|chamfer|land|neck|interface|panel|valve|port|housing|"
    r"cylinder|seat|stack|washer|linkage|coupler|branch|outlet|inlet|seam|plate|toolholder|gauge|bracket|window|"
    r"cover|shield|manifold|channel|body|holder|tool|clamp(?:\s+stack)?"
)
_SIGNAL_PATTERN = _compile_phrase_pattern(
    r"level|color|wetness|wetting|path|angle|clocking|force|pressure|temperature|load|result|history|stroke|"
    r"clearance|offset|reading|height|depth|condition"
)
_STATE_PATTERN = re.compile(
    r"\b(as-received condition|as-found angle|operating state|surface state|hardware state|dry|wet|fully latched|"
    r"naturally supported|centered)\b",
    re.IGNORECASE,
)
_FAULT_PATTERN = re.compile(
    r"\b(cracked shell|broken latch ear|incomplete insertion|recurring seepage|fault|failure|pull-out|alarm|"
    r"short-stroke|misalignment|crack(?:ing)?|distortion|wear|burrs?|nicks?|corrosion|leak(?:age)?|seepage|"
    r"sweat|oil trace|damage|staining|stress whitening|witness marks?)\b",
    re.IGNORECASE,
)
_ASSET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:on|vehicle|pack)\s+([A-Z][A-Za-z0-9-]+(?:\s+[A-Z0-9][A-Za-z0-9-]+){1,4})"),
    re.compile(r"\b([A-Z][A-Za-z0-9-]+(?:\s+[A-Z0-9][A-Za-z0-9-]+){1,4})\b"),
)

_RELATION_PATTERNS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"\bindicates?\b", re.IGNORECASE), "indicates", "communication"),
    (re.compile(r"\bcauses?\b", re.IGNORECASE), "causes", "propagation"),
    (re.compile(r"\btransitions?\s+to\b", re.IGNORECASE), "transitionsTo", "lifecycle"),
    (re.compile(r"\bhas\s+state\b", re.IGNORECASE), "hasState", "lifecycle"),
    (re.compile(r"\bcontains?\b", re.IGNORECASE), "contains", "structural"),
)


def _normalize_phrase(raw: str) -> str:
    compact = re.sub(r"\s+", " ", raw.strip(" ,.;:()[]{}")).strip()
    if not compact:
        return ""
    tokens = compact.split()
    while tokens and tokens[0].lower() in _STOPWORD_PREFIXES | _COMMAND_PREFIXES:
        tokens = tokens[1:]
    compact = " ".join(tokens).strip(" ,.;:()[]{}")
    return compact


def _concept_entry(label: str, hint: str) -> dict[str, Any]:
    return {
        "label": label,
        "description": f"rule-based {hint.lower()} candidate",
        "node_worthy": True,
        "surface_form": label,
        "semantic_type_hint": hint,
    }


def _collect_concept_mentions(text: str) -> list[dict[str, Any]]:
    mentions: OrderedDict[str, dict[str, Any]] = OrderedDict()

    def add(label: str, hint: str) -> None:
        normalized = _normalize_phrase(label)
        if not normalized:
            return
        if normalized.lower() in _GENERIC_LABELS:
            return
        if len(normalized) < 3:
            return
        mentions.setdefault(normalized.lower(), _concept_entry(normalized, hint))

    for pattern, hint in (
        (_COMPONENT_PATTERN, "Component"),
        (_SIGNAL_PATTERN, "Signal"),
        (_STATE_PATTERN, "State"),
        (_FAULT_PATTERN, "Fault"),
    ):
        for match in pattern.finditer(text):
            add(match.group(0), hint)

    for pattern in _ASSET_PATTERNS:
        for match in pattern.finditer(text):
            label = match.group(1) if match.lastindex else match.group(0)
            add(label, "Asset")

    return list(mentions.values())


def _collect_sentence_spans(sentence: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for pattern, hint in (
        (_COMPONENT_PATTERN, "Component"),
        (_SIGNAL_PATTERN, "Signal"),
        (_STATE_PATTERN, "State"),
        (_FAULT_PATTERN, "Fault"),
    ):
        for match in pattern.finditer(sentence):
            label = _normalize_phrase(match.group(0))
            if not label or label.lower() in _GENERIC_LABELS:
                continue
            spans.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "label": label,
                    "hint": hint,
                }
            )
    return sorted(spans, key=lambda item: (item["start"], item["end"]))


def _collect_relation_mentions(text: str) -> list[dict[str, Any]]:
    relations: OrderedDict[tuple[str, str, str, str], dict[str, Any]] = OrderedDict()
    for sentence in _SENTENCE_SPLIT_PATTERN.split(text):
        spans = _collect_sentence_spans(sentence)
        if len(spans) < 2:
            continue
        for pattern, relation_label, family in _RELATION_PATTERNS:
            for match in pattern.finditer(sentence):
                left = [item for item in spans if item["end"] <= match.start()]
                right = [item for item in spans if item["start"] >= match.end()]
                if not left or not right:
                    continue
                head = left[-1]["label"]
                tail = right[0]["label"]
                if head.lower() == tail.lower():
                    continue
                key = (relation_label, family, head.lower(), tail.lower())
                relations.setdefault(
                    key,
                    {
                        "label": relation_label,
                        "family": family,
                        "head": head,
                        "tail": tail,
                    },
                )
    return list(relations.values())


def rule_extract_document(doc: DocumentInput) -> ExtractionResult:
    content = normalize_content(doc.content)
    concepts = _collect_concept_mentions(content)
    relations = _collect_relation_mentions(content)
    return ExtractionResult(
        doc_id=doc.doc_id,
        concepts=concepts,
        relations=relations,
        extraction_quality="rule_based",
        llm_model="rule_pipeline",
        processing_time_ms=0,
    )


def build_rule_records_by_domain(
    data_root: str | Path,
    domain_ids: list[str],
    *,
    role: str = "target",
) -> dict[str, list[EvidenceRecord]]:
    root = Path(data_root).resolve()
    docs_by_domain = parse_multi_domain_directory(root, domain_ids, role)
    records_by_domain: dict[str, list[EvidenceRecord]] = {domain_id: [] for domain_id in domain_ids}
    for domain_id in domain_ids:
        for doc_type, documents in docs_by_domain.get(domain_id, {}).items():
            for doc in documents:
                extraction = rule_extract_document(doc)
                record = extraction_to_evidence_record(doc, extraction)
                if doc_type != record.source_type:
                    raise ValueError(f"rule preprocessing doc_type mismatch for {doc.doc_id}: {doc_type} vs {record.source_type}")
                records_by_domain[domain_id].append(record)
        records_by_domain[domain_id].sort(key=lambda item: item.timestamp)
    return records_by_domain


def write_rule_records_bundle(
    output_root: str | Path,
    records_by_domain: dict[str, list[EvidenceRecord]],
) -> dict[str, str]:
    root = Path(output_root).resolve()
    ensure_dir(root)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    output_paths: dict[str, str] = {}
    for domain_id, records in records_by_domain.items():
        path = root / f"{domain_id}_rule_evidence_records.json"
        write_json(
            path,
            {
                "project_name": "crossextend_kg_rule_preprocessing",
                "generated_at": generated_at,
                "domains": [domain_id],
                "role": "target",
                "document_count": len(records),
                "domain_stats": {domain_id: {"om_manual": len(records)}},
                "evidence_records": [record.model_dump(mode="json") for record in records],
            },
        )
        output_paths[domain_id] = str(path)
    return output_paths
