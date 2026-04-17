#!/usr/bin/env python3
"""Main processor for converting raw documents to EvidenceRecords."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..io import ensure_dir, write_json
from ..models import ConceptMention, EvidenceRecord, RelationMention
from .extractor import LLMExtractor, build_extractor
from .models import DocumentInput, ExtractionResult, PreprocessingConfig, PreprocessingResult
from .parser import (
    parse_multi_domain_directory,
    normalize_content
)


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
_ACTIVE_RELATION_RULES: dict[str, tuple[str, str, bool]] = {
    "contains": ("contains", "structural", False),
    "hasstate": ("hasState", "lifecycle", False),
    "transitionsto": ("transitionsTo", "lifecycle", False),
    "indicates": ("indicates", "communication", False),
    "provides": ("provides", "communication", False),
    "emits": ("emits", "communication", False),
    "monitors": ("monitors", "communication", False),
    "requires": ("requires", "task_dependency", False),
    "measures": ("measures", "task_dependency", False),
    "confirms": ("confirms", "task_dependency", False),
    "observes": ("observes", "task_dependency", False),
    "performs": ("performs", "task_dependency", False),
    "triggers": ("triggers", "propagation", False),
    "causes": ("causes", "propagation", False),
    "comprises": ("comprises", "propagation", False),
    "causedby": ("causes", "propagation", True),
    "measuredby": ("measures", "task_dependency", True),
    "confirmedby": ("confirms", "task_dependency", True),
    "observedin": ("observes", "task_dependency", True),
    "performedby": ("performs", "task_dependency", True),
}


def _expand_env_in_string(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        default = match.group(2)
        if env_name in os.environ:
            return os.environ[env_name]
        return default or ""

    return _ENV_PATTERN.sub(replace, value)


def _expand_env(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: _expand_env(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_expand_env(item) for item in payload]
    if isinstance(payload, str):
        return _expand_env_in_string(payload)
    return payload


def _resolve_path(base_dir: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    return str((base_dir / path).resolve())


def _count_domain_documents(docs_by_type: dict[str, list[DocumentInput]]) -> int:
    return sum(len(documents) for documents in docs_by_type.values())


def _normalize_relation_label_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", label.lower())


def _normalize_relation_entry(relation_data: dict[str, Any]) -> dict[str, str] | None:
    label = str(relation_data.get("label", "")).strip()
    head = str(relation_data.get("head", "")).strip()
    tail = str(relation_data.get("tail", "")).strip()
    if not label or not head or not tail:
        return None

    family = str(relation_data.get("family", "structural")).strip() or "structural"
    normalized_label = label
    normalized_family = family
    normalized_head = head
    normalized_tail = tail

    rule = _ACTIVE_RELATION_RULES.get(_normalize_relation_label_key(label))
    if rule:
        normalized_label, normalized_family, should_flip = rule
        if should_flip:
            normalized_head, normalized_tail = tail, head

    return {
        "label": normalized_label,
        "family": normalized_family,
        "head": normalized_head,
        "tail": normalized_tail,
    }


def run_preprocessing(
    config: PreprocessingConfig,
    config_path: str | None = None,
) -> PreprocessingResult:
    """Run preprocessing pipeline from config.

    Unified Construction Method:
    - All domains are equally treated as application cases
    - LLM extraction is REQUIRED - no fallback allowed
    - Multi-domain processing is the only supported mode

    Expected structure:
    - data_root/{domain}/products/*.md
    - data_root/{domain}/fault_cases/*.md
    - Or flat: data_root/{domain}/{domain}_product_*.md

    Args:
        config: Preprocessing configuration

    Returns:
        PreprocessingResult with stats and output path

    Raises:
        ValueError: If LLM endpoint is incomplete (no fallback extraction)
    """
    start_time = time.time()

    output_path = Path(config.output_path)
    ensure_dir(output_path.parent)

    # LLM extraction is REQUIRED - no fallback allowed
    use_llm = bool(config.llm.base_url and config.llm.model)
    if not use_llm:
        raise ValueError(
            "Preprocessing requires llm.base_url and llm.model. "
            "Set them in config before running. "
            "No fallback extraction is allowed."
        )
    evidence_records = []
    errors = []
    successful = 0
    failed = 0
    domain_stats: dict[str, dict[str, int]] = {}

    # Mode 1: Multi-domain processing
    if config.data_root and config.domain_ids:
        data_root = Path(config.data_root)
        if not data_root.is_dir():
            raise FileNotFoundError(f"preprocessing data_root not found: {data_root}")
        domain_documents = parse_multi_domain_directory(
            data_root=data_root,
            domain_ids=config.domain_ids,
            role=config.role
        )
        missing_domains = [domain_id for domain_id in config.domain_ids if domain_id not in domain_documents]
        if missing_domains:
            missing_paths = [str(data_root / domain_id) for domain_id in missing_domains]
            raise FileNotFoundError(
                "configured domain directories not found under data_root: "
                + ", ".join(missing_paths)
            )

        empty_domains = [
            domain_id
            for domain_id in config.domain_ids
            if _count_domain_documents(domain_documents[domain_id]) == 0
        ]
        if empty_domains:
            raise ValueError(
                "configured domains contain no markdown documents: "
                + ", ".join(empty_domains)
            )

        extractor = build_extractor(config)

        for domain_id in config.domain_ids:
            docs_by_type = domain_documents[domain_id]
            domain_stats[domain_id] = {}

            for doc_type, documents in docs_by_type.items():
                domain_stats[domain_id][doc_type] = len(documents)

                MAX_DOC_CONTENT_LENGTH = 3000  # Truncate long documents to avoid LLM timeout

                for doc in documents:
                    # Normalize content
                    normalized_content = normalize_content(doc.content)
                    # Truncate if too long
                    if len(normalized_content) > MAX_DOC_CONTENT_LENGTH:
                        normalized_content = normalized_content[:MAX_DOC_CONTENT_LENGTH] + "\n... [truncated]"
                    doc.content = normalized_content

                    # Extract concepts and relations
                    result = extractor.extract(doc)

                    if result.extraction_quality == "failed":
                        failed += 1
                        errors.append(f"Extraction failed for {doc.doc_id} ({domain_id}/{doc_type})")
                        continue

                    # Convert to EvidenceRecord
                    record = extraction_to_evidence_record(doc, result)
                    evidence_records.append(record)
                    successful += 1

    else:
        # Unified construction requires multi-domain configuration
        raise ValueError(
            "Preprocessing requires multi-domain configuration. "
            "Set data_root and domain_ids in config. "
            "Single-domain legacy mode is not supported."
        )

    # Write output
    output_data = {
        "project_name": "crossextend_kg_preprocessing",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "domains": config.domain_ids,  # Unified construction: all domains
        "role": config.role,  # Always 'target' in unified construction
        "document_count": successful,
        "domain_stats": domain_stats,
        "evidence_records": [r.model_dump() for r in evidence_records]
    }

    write_json(output_path, output_data)

    total_docs = sum(
        sum(type_count.values()) for type_count in domain_stats.values()
    )

    return PreprocessingResult(
        config_path=str(Path(config_path).resolve()) if config_path else "",
        data_root=config.data_root,
        output_path=str(output_path),
        domain_ids=list(config.domain_ids),
        total_docs=total_docs,
        successful_docs=successful,
        failed_docs=failed,
        evidence_records_path=str(output_path),
        processing_time_sec=time.time() - start_time,
        domain_stats=domain_stats,
        errors=errors
    )


def extraction_to_evidence_record(
    doc: DocumentInput,
    extraction: ExtractionResult
) -> EvidenceRecord:
    """Convert extraction result to EvidenceRecord.

    Args:
        doc: Original document input
        extraction: LLM extraction result

    Returns:
        EvidenceRecord compatible with CrossExtend-KG pipeline
    """
    # Convert concepts
    concept_mentions = []
    for concept_data in extraction.concepts:
        mention = ConceptMention(
            label=concept_data.get("label", ""),
            description=concept_data.get("description", ""),
            node_worthy=concept_data.get("node_worthy", True)
        )
        concept_mentions.append(mention)

    # Convert relations
    relation_mentions = []
    seen_relations: set[tuple[str, str, str, str]] = set()
    for relation_data in extraction.relations:
        normalized_relation = _normalize_relation_entry(relation_data)
        if normalized_relation is None:
            continue
        relation_key = (
            normalized_relation["label"],
            normalized_relation["family"],
            normalized_relation["head"],
            normalized_relation["tail"],
        )
        if relation_key in seen_relations:
            continue
        seen_relations.add(relation_key)
        mention = RelationMention(
            label=normalized_relation["label"],
            family=normalized_relation["family"],
            head=normalized_relation["head"],
            tail=normalized_relation["tail"],
        )
        relation_mentions.append(mention)

    return EvidenceRecord(
        evidence_id=doc.doc_id,
        domain_id=doc.domain_id,
        role=doc.role,
        source_type=doc.doc_type,
        timestamp=doc.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        raw_text=doc.content,
        concept_mentions=concept_mentions,
        relation_mentions=relation_mentions
    )


def load_preprocessing_config(config_path: str) -> PreprocessingConfig:
    """Load preprocessing config from JSON file."""
    path = Path(config_path).resolve()
    data = _expand_env(json.loads(path.read_text(encoding="utf-8")))
    config = PreprocessingConfig.model_validate(data)
    base_dir = path.parent
    config.data_root = _resolve_path(base_dir, config.data_root)
    config.output_path = _resolve_path(base_dir, config.output_path)
    config.prompt_template_path = _resolve_path(base_dir, config.prompt_template_path)
    return config


def preprocess_single_document(
    doc_path: str,
    domain_id: str,
    role: str,
    llm_config: dict[str, Any],
    output_path: str
) -> EvidenceRecord:
    """Preprocess a single document (convenience function).

    Args:
        doc_path: Path to markdown file
        domain_id: Target domain
        role: "target" (unified construction: all domains are application cases)
        llm_config: LLM configuration dict
        output_path: Output JSON path

    Returns:
        EvidenceRecord
    """
    from .parser import parse_markdown_file

    doc_path_obj = Path(doc_path)

    # Build config for extractor-only usage.
    payload: dict[str, Any] = {
        "data_root": str(doc_path_obj.parent),
        "domain_ids": [domain_id],
        "output_path": output_path,
        "role": role,
    }
    if "llm" in llm_config or any(key.startswith("llm_") for key in llm_config):
        payload.update(llm_config)
    else:
        payload["llm"] = llm_config
    config = PreprocessingConfig.model_validate(payload)

    # Parse document
    doc = parse_markdown_file(
        doc_path_obj,
        domain_id=domain_id,
        role=role
    )

    # Extract
    extractor = build_extractor(config)
    result = extractor.extract(doc)

    return extraction_to_evidence_record(doc, result)
