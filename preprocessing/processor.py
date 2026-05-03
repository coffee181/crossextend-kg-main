#!/usr/bin/env python3
"""Main processor for converting O&M markdown to EvidenceRecords."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from crossextend_kg.config import load_structured_config_payload, resolve_preprocessing_payload_paths
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import load_structured_config_payload, resolve_preprocessing_payload_paths
try:
    from crossextend_kg.file_io import ensure_dir, read_json, write_json
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import ensure_dir, read_json, write_json
try:
    from crossextend_kg.models import (
        ConceptMention,
        CrossStepRelation,
        DiagnosticEdge,
        EvidenceRecord,
        ProcedureMeta,
        RelationMention,
        SemanticTypeHint,
        SharedHypernym,
        StepAction,
        StepConceptMention,
        StepPhase,
        StepRecord,
        StateTransition,
        StructuralEdge,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import (
        ConceptMention,
        CrossStepRelation,
        DiagnosticEdge,
        EvidenceRecord,
        ProcedureMeta,
        RelationMention,
        SemanticTypeHint,
        SharedHypernym,
        StepAction,
        StepConceptMention,
        StepPhase,
        StepRecord,
        StateTransition,
        StructuralEdge,
    )
logger = logging.getLogger(__name__)

from preprocessing.extractor import build_extractor
from preprocessing.models import DocumentInput, ExtractionResult, PreprocessingConfig, PreprocessingResult
from preprocessing.parser import (
    classify_doc_type,
    infer_doc_type_from_filename,
    normalize_content,
    parse_markdown_file,
    parse_multi_domain_directory,
)


_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
_STEP_ID_PATTERN = re.compile(r"^(T\d+)\b", re.IGNORECASE)
_STEP_ROW_PATTERN = re.compile(r"^\|\s*(T\d+)\s*\|\s*(.*?)\s*\|\s*$", re.IGNORECASE)
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
    "records": ("records", "task_dependency", False),
    "confirms": ("confirms", "task_dependency", False),
    "separates": ("confirms", "task_dependency", False),
    "observes": ("observes", "task_dependency", False),
    "performs": ("performs", "task_dependency", False),
    "triggers": ("triggers", "task_dependency", False),
    "causes": ("causes", "propagation", False),
    "comprises": ("comprises", "propagation", False),
    "causedby": ("causes", "propagation", True),
    "measuredby": ("measures", "task_dependency", True),
    "confirmedby": ("confirms", "task_dependency", True),
    "observedin": ("observes", "task_dependency", True),
    "performedby": ("performs", "task_dependency", True),
}
_FAMILY_PRESERVE_BY_LABEL: dict[str, set[str]] = {
    "contains": {"structural"},
    "hasState": {"lifecycle"},
    "transitionsTo": {"lifecycle"},
    "indicates": {"communication"},
    "provides": {"communication"},
    "emits": {"communication"},
    "monitors": {"communication"},
    "requires": {"task_dependency"},
    "measures": {"task_dependency"},
    "records": {"task_dependency"},
    "confirms": {"task_dependency"},
    "observes": {"task_dependency"},
    "performs": {"task_dependency"},
    "triggers": {"task_dependency", "propagation"},
    "causes": {"propagation"},
    "comprises": {"propagation"},
}
_MAX_DOC_CONTENT_LENGTH = 20000
_SEMANTIC_TYPE_HINT_MAP: dict[str, SemanticTypeHint] = {
    "asset": "Asset",
    "component": "Component",
    "signal": "Signal",
    "state": "State",
    "fault": "Fault",
}
_SHARED_HYPONYM_MAP: dict[str, SharedHypernym] = {
    "seal": "Seal",
    "connector": "Connector",
    "sensor": "Sensor",
    "controller": "Controller",
    "coolant": "Coolant",
    "actuator": "Actuator",
    "power": "Power",
    "housing": "Housing",
    "fastener": "Fastener",
    "media": "Media",
}
_STEP_PHASE_PATTERNS: list[tuple[re.Pattern[str], StepPhase]] = [
    (re.compile(r"\b(verify|verifies|verified|verifying|confirm|confirms|confirmed|confirming|validate|validates|validated|validating|test|tests|tested|testing|prove|proves|proved|proving|monitor|monitors|monitored|monitoring|circulate|circulates|circulated|circulating|pressurize|pressurizes|pressurized|pressurizing)\b", re.IGNORECASE), "verify"),
    (re.compile(r"\b(record|records|observe|observes|inspect|inspects|inspection|measure|measures|capture|captures|note|notes|check|checks|review|reviews|examine|examines|identify|identifies|trace|traces)\b", re.IGNORECASE), "observe"),
    (re.compile(r"\b(diagnose|diagnoses|diagnosed|diagnosing|analyze|analyzes|analyzed|analyzing|compare|compares|compared|comparing|evaluate|evaluates|evaluated|evaluating|assess|assesses|assessed|assessing|determine|determines|determined|determining)\b", re.IGNORECASE), "diagnose"),
    (re.compile(r"\b(repair|repairs|replace|replaces|replacement|reseat|reseats|reset|resets|correct|corrects|refit|refits|install|installs|renew|renews|restore|restores|torque|torques|tighten|tightens|lubricate|lubricates|adjust|adjusts)\b", re.IGNORECASE), "repair"),
]
_ALIAS_TOKEN_EQUIVALENTS: dict[str, str] = {
    "inner": "internal",
}
_ALIAS_DISTINGUISHING_TOKENS: frozenset[str] = frozenset(
    {
        "inlet",
        "outlet",
        "front",
        "rear",
        "left",
        "right",
        "upper",
        "lower",
        "upstream",
        "downstream",
    }
)
_LEADING_CONTEXT_PREFIX_PATTERN = re.compile(r"^(nearby|adjacent)\s+", re.IGNORECASE)
_STRUCTURAL_CONTEXTUAL_HEAD_PATTERN = re.compile(r"\b(branch|path|condition|state)\b", re.IGNORECASE)
_STRUCTURAL_CONTEXTUAL_TAIL_PATTERN = re.compile(r"\b(hose|clip|rib|panel|overmold)\b", re.IGNORECASE)
_CONNECTOR_PARENT_PATTERN = re.compile(r"\b(connector|coupler|joint)\b", re.IGNORECASE)
_CONNECTOR_SUBCOMPONENT_PATTERN = re.compile(r"\b(shell|retainer|o-?ring)\b", re.IGNORECASE)
_GENERIC_COMPONENT_PATTERN = re.compile(r"\b(replacement|new|old|removed|spare|fresh)\b", re.IGNORECASE)
_INDICATES_LOCAL_DAMAGE_RULES: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(r"^stress whitening$", re.IGNORECASE),
        re.compile(r"\b(shell|crack|cracked|shell failure)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\blatch[- ]window distortion\b", re.IGNORECASE),
        re.compile(r"\b(latch|ear)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\bwitness marks?\b", re.IGNORECASE),
        re.compile(r"\b(side load|off-axis|preload|routing)\b", re.IGNORECASE),
    ),
)
_BROAD_ROOT_CAUSE_TARGET_PATTERN = re.compile(r"\b(side load|off-axis|preload|routing issue|history)\b", re.IGNORECASE)
_COMMUNICATION_TARGET_ALLOWED_HINTS: frozenset[SemanticTypeHint] = frozenset({"Signal", "State", "Fault"})


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
        normalized_label, default_family, should_flip = rule
        if should_flip:
            normalized_head, normalized_tail = tail, head
        allowed_input_families = _FAMILY_PRESERVE_BY_LABEL.get(normalized_label, {default_family})
        normalized_family = family if family in allowed_input_families else default_family

    return {
        "label": normalized_label,
        "family": normalized_family,
        "head": normalized_head,
        "tail": normalized_tail,
    }


def _extract_step_rows(raw_text: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in raw_text.splitlines():
        match = _STEP_ROW_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append((match.group(1).upper(), match.group(2).strip()))
    return rows


def _extract_step_id(value: str) -> str | None:
    match = _STEP_ID_PATTERN.match(value.strip())
    if not match:
        return None
    return match.group(1).upper()


def _normalize_endpoint(value: str) -> str:
    step_id = _extract_step_id(value)
    if step_id:
        return step_id
    return value.strip()


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _build_concept_mention(concept_data: dict[str, Any], *, fallback_label: str | None = None) -> ConceptMention:
    raw_label = str(concept_data.get("label", "")).strip()
    label = str(fallback_label or raw_label).strip()
    surface_form = str(concept_data.get("surface_form", raw_label or label)).strip() or label
    return ConceptMention(
        label=label,
        description=str(concept_data.get("description", "")).strip(),
        node_worthy=bool(concept_data.get("node_worthy", True)),
        surface_form=surface_form,
        semantic_type_hint=_extract_semantic_type_hint(concept_data),
        shared_hypernym=_extract_shared_hypernym(concept_data),
    )


def _extract_semantic_type_hint(concept_data: dict[str, Any]) -> SemanticTypeHint | None:
    for key in ("semantic_type_hint", "parent_gold", "gold_parent"):
        value = concept_data.get(key)
        if not isinstance(value, str):
            continue
        normalized = _SEMANTIC_TYPE_HINT_MAP.get(value.strip().lower())
        if normalized is not None:
            return normalized
    return None


def _extract_shared_hypernym(concept_data: dict[str, Any]) -> SharedHypernym | None:
    value = concept_data.get("shared_hypernym")
    if not isinstance(value, str):
        return None
    return _SHARED_HYPONYM_MAP.get(value.strip().lower())


def _merge_concept_mention(store: dict[str, ConceptMention], mention: ConceptMention) -> None:
    existing = store.get(mention.label)
    if existing is None:
        store[mention.label] = mention
        return
    if not existing.description and mention.description:
        existing.description = mention.description
    if not existing.surface_form and mention.surface_form:
        existing.surface_form = mention.surface_form
    if existing.semantic_type_hint is None and mention.semantic_type_hint is not None:
        existing.semantic_type_hint = mention.semantic_type_hint
    existing.node_worthy = existing.node_worthy or mention.node_worthy


def _infer_step_ids_from_surface(label: str, step_rows: dict[str, str]) -> list[str]:
    normalized_label = " ".join(label.lower().split())
    if len(normalized_label) < 5:
        return []
    if len(normalized_label.split()) == 1 and len(normalized_label) < 8:
        return []
    matches: list[str] = []
    pattern = re.compile(rf"(?<!\w){re.escape(normalized_label)}(?!\w)")
    for step_id, row_text in step_rows.items():
        normalized_row = " ".join(row_text.lower().split())
        if pattern.search(normalized_row):
            matches.append(step_id)
    return matches if len(matches) == 1 else []


def _infer_step_phase(surface_form: str) -> StepPhase | None:
    text = surface_form.strip()
    if not text:
        return None
    for pattern, phase in _STEP_PHASE_PATTERNS:
        if pattern.search(text):
            return phase
    return None


def _infer_procedure_meta(raw_text: str, evidence_id: str) -> ProcedureMeta | None:
    lines = raw_text.strip().splitlines()
    title = lines[0].strip().lstrip("#").strip() if lines else ""
    asset_name = None
    procedure_type = None
    primary_fault_type = None
    for line in lines[:5]:
        lower = line.lower()
        if not asset_name:
            asset_match = re.search(r"(?:pack|vehicle|machine|cabinet|controller|motor|compressor|spindle|axis|drive|battery|chiller|pump)", lower)
            if asset_match:
                asset_name = asset_match.group(0).title()
        if not procedure_type:
            if any(kw in lower for kw in ("diagnosis", "diagnostic")):
                procedure_type = "diagnosis"
            elif any(kw in lower for kw in ("inspection", "inspect", "review")):
                procedure_type = "inspection"
            elif any(kw in lower for kw in ("replacement", "replace", "install")):
                procedure_type = "replacement"
            elif any(kw in lower for kw in ("repair", "reseat", "correct")):
                procedure_type = "repair"
            elif any(kw in lower for kw in ("verification", "verify", "validate")):
                procedure_type = "verification"
        if not primary_fault_type:
            fault_match = re.search(r"\b(leak|seepage|corrosion|crack|overheat|misalignment|contamination|drift|drop|offset|noise|vibration|fault|failure)\b", lower)
            if fault_match:
                primary_fault_type = fault_match.group(0)
    if not asset_name and not procedure_type and not primary_fault_type:
        return None
    return ProcedureMeta(
        asset_name=asset_name,
        procedure_type=procedure_type,
        primary_fault_type=primary_fault_type,
    )


def _alias_tokens(label: str) -> list[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", label.lower())
    tokens = [token for token in normalized.split() if token]
    return [_ALIAS_TOKEN_EQUIVALENTS.get(token, token) for token in tokens]


def _is_subsequence(short_tokens: list[str], long_tokens: list[str]) -> bool:
    if len(short_tokens) > len(long_tokens):
        return False
    index = 0
    for token in long_tokens:
        if index < len(short_tokens) and token == short_tokens[index]:
            index += 1
    return index == len(short_tokens)


def _adds_distinguishing_alias_tokens(short_tokens: list[str], long_tokens: list[str]) -> bool:
    extras: list[str] = []
    index = 0
    for token in long_tokens:
        if index < len(short_tokens) and token == short_tokens[index]:
            index += 1
            continue
        extras.append(token)
    return any(token in _ALIAS_DISTINGUISHING_TOKENS for token in extras)


def _build_document_alias_map(
    concept_rows: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
) -> dict[str, str]:
    labels: set[str] = set()
    concept_types: dict[str, SemanticTypeHint | None] = {}
    for concept_row in concept_rows:
        label = str(concept_row.get("label", "")).strip()
        if label and not _extract_step_id(label):
            labels.add(label)
            concept_types[label] = _extract_semantic_type_hint(concept_row)
    for relation_row in relation_rows:
        for endpoint in (relation_row.get("head", ""), relation_row.get("tail", "")):
            label = str(endpoint).strip()
            if label and not _extract_step_id(label):
                labels.add(label)

    token_map = {label: _alias_tokens(label) for label in labels}
    alias_map: dict[str, str] = {}
    for label in sorted(labels, key=lambda item: (len(token_map[item]), len(item))):
        short_tokens = token_map[label]
        if not short_tokens:
            continue
        if len(short_tokens) == 1 and short_tokens[0] not in {"retainer"}:
            continue
        matches = [
            candidate
            for candidate in labels
            if candidate != label
            and len(token_map[candidate]) > len(short_tokens)
            and _is_subsequence(short_tokens, token_map[candidate])
            and not _adds_distinguishing_alias_tokens(short_tokens, token_map[candidate])
            and (
                concept_types.get(label) is None
                or concept_types.get(candidate) is None
                or concept_types.get(label) == concept_types.get(candidate)
            )
        ]
        if len(matches) == 1:
            alias_map[label] = matches[0]
    return alias_map


def _canonicalize_label(label: str, alias_map: dict[str, str]) -> str:
    compact = label.strip()
    if not compact or _extract_step_id(compact):
        return compact
    compact = _LEADING_CONTEXT_PREFIX_PATTERN.sub("", compact).strip()
    if compact.lower().startswith("vehicle "):
        vehicle_stripped = compact[len("vehicle ") :].strip()
        if vehicle_stripped and any(char.isupper() for char in vehicle_stripped):
            compact = vehicle_stripped
    return alias_map.get(compact, compact)


def _should_keep_document_relation(relation: RelationMention) -> bool:
    if relation.family != "structural":
        return True
    if _STRUCTURAL_CONTEXTUAL_HEAD_PATTERN.search(relation.head):
        return False
    if _STRUCTURAL_CONTEXTUAL_TAIL_PATTERN.search(relation.tail):
        return False
    return True


def _select_structural_parent_for_contextual_head(
    concept_catalog: dict[str, ConceptMention],
) -> str | None:
    ranked: list[tuple[int, str]] = []
    for label, mention in concept_catalog.items():
        if not _CONNECTOR_PARENT_PATTERN.search(label):
            continue
        if _CONNECTOR_SUBCOMPONENT_PATTERN.search(label):
            continue
        score = 0
        if mention.semantic_type_hint == "Component":
            score += 2
        if not _GENERIC_COMPONENT_PATTERN.search(label):
            score += 2
        if "connector" in label.lower():
            score += 1
        ranked.append((score, label))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None
    return ranked[0][1]


def _rewrite_document_relation(
    relation: RelationMention,
    concept_catalog: dict[str, ConceptMention],
) -> RelationMention:
    if relation.family != "structural":
        return relation
    if not _STRUCTURAL_CONTEXTUAL_HEAD_PATTERN.search(relation.head):
        return relation
    if not _CONNECTOR_SUBCOMPONENT_PATTERN.search(relation.tail):
        return relation

    structural_parent = _select_structural_parent_for_contextual_head(concept_catalog)
    if structural_parent is None or structural_parent == relation.tail:
        return relation
    return relation.model_copy(update={"head": structural_parent})


def _score_indicates_target(head_label: str, target_label: str) -> int:
    score = 0
    for head_pattern, target_pattern in _INDICATES_LOCAL_DAMAGE_RULES:
        if not head_pattern.search(head_label):
            continue
        if target_pattern.search(target_label):
            score += 6
        elif _BROAD_ROOT_CAUSE_TARGET_PATTERN.search(target_label):
            score -= 2
    return score


def _rewrite_communication_relation(
    relation: RelationMention,
    concept_catalog: dict[str, ConceptMention],
) -> RelationMention:
    if relation.family != "communication" or relation.label != "indicates":
        return relation

    current_score = _score_indicates_target(relation.head, relation.tail)
    ranked_targets: list[tuple[int, str]] = []
    for label, mention in concept_catalog.items():
        if label == relation.head:
            continue
        if mention.semantic_type_hint is not None and mention.semantic_type_hint not in _COMMUNICATION_TARGET_ALLOWED_HINTS:
            continue
        score = _score_indicates_target(relation.head, label)
        if score <= 0:
            continue
        ranked_targets.append((score, label))

    if not ranked_targets:
        return relation

    ranked_targets.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_label = ranked_targets[0]
    if best_score <= current_score:
        return relation
    if len(ranked_targets) > 1 and ranked_targets[1][0] == best_score:
        return relation
    return relation.model_copy(update={"tail": best_label})


def _dedupe_relations(relations: list[RelationMention]) -> list[RelationMention]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[RelationMention] = []
    for relation in relations:
        key = (relation.label, relation.family, relation.head, relation.tail)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(relation)
    return deduped


def _build_domain_output_path(output_path: Path, domain_id: str, domain_count: int) -> Path:
    if domain_count <= 1:
        return output_path
    return output_path.with_name(f"{domain_id}_{output_path.name}")


def _write_output(
    output_path: Path,
    config: Any,
    successful: int,
    domain_stats: dict[str, dict[str, int]],
    evidence_records: list[Any],
) -> None:
    """Incrementally write output JSON so work is never lost on failure.

    Writes both the combined file and per-domain files.
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    serialized = [record.model_dump(mode="json") for record in evidence_records]

    # Combined output
    write_json(
        output_path,
        {
            "project_name": "crossextend_kg_preprocessing",
            "generated_at": generated_at,
            "domains": config.domain_ids,
            "role": config.role,
            "document_count": successful,
            "domain_stats": domain_stats,
            "evidence_records": serialized,
        },
    )

    # Per-domain output
    domain_count = len(config.domain_ids)
    records_by_domain: dict[str, list[dict]] = {d: [] for d in config.domain_ids}
    for record in evidence_records:
        records_by_domain.setdefault(record.domain_id, []).append(record)

    for domain_id in config.domain_ids:
        domain_path = _build_domain_output_path(output_path, domain_id, domain_count)
        domain_records = [r.model_dump(mode="json") for r in records_by_domain.get(domain_id, [])]
        domain_doc_count = len(domain_records)
        write_json(
            domain_path,
            {
                "project_name": "crossextend_kg_preprocessing",
                "generated_at": generated_at,
                "domains": [domain_id],
                "role": config.role,
                "document_count": domain_doc_count,
                "domain_stats": {domain_id: domain_stats.get(domain_id, {})},
                "evidence_records": domain_records,
            },
        )


def run_preprocessing(
    config: PreprocessingConfig,
    config_path: str | None = None,
    max_docs: int | None = None,
) -> PreprocessingResult:
    """Run preprocessing pipeline from config."""
    start_time = time.time()

    output_path = Path(config.output_path)
    ensure_dir(output_path.parent)

    use_llm = bool(config.llm.base_url and config.llm.model)
    if not use_llm:
        raise ValueError(
            "Preprocessing requires llm.base_url and llm.model. "
            "Set them in config before running. "
            "No fallback extraction is allowed."
        )

    evidence_records: list[EvidenceRecord] = []
    errors: list[str] = []
    successful = 0
    failed = 0
    domain_stats: dict[str, dict[str, int]] = {}

    # Resume from existing output if present.
    # Try per-domain files first (more granular, less data loss on corruption),
    # then fall back to the combined file.
    processed_doc_ids: set[str] = set()
    domain_count = len(config.domain_ids) if config.domain_ids else 1
    resume_sources: list[Path] = []
    if domain_count > 1:
        for domain_id in config.domain_ids:
            domain_path = _build_domain_output_path(output_path, domain_id, domain_count)
            if domain_path.exists():
                resume_sources.append(domain_path)
    if not resume_sources and output_path.exists():
        resume_sources.append(output_path)

    # Safety: back up existing files before touching them
    backup_dir: Path | None = None
    if resume_sources:
        backup_dir = output_path.parent / ".preprocess_backups"
        backup_dir.mkdir(exist_ok=True)
        for src in resume_sources:
            if src.exists():
                bak = backup_dir / f"{src.name}.bak"
                bak.write_bytes(src.read_bytes())
        print(f"[preprocess] backed up {len(resume_sources)} existing file(s) to {backup_dir}", flush=True)

    for source_path in resume_sources:
        try:
            existing_data = read_json(source_path)
            existing_records = existing_data.get("evidence_records", [])
            loaded = 0
            for record_data in existing_records:
                doc_id = record_data.get("evidence_id", "") or record_data.get("doc_id", "")
                if doc_id and doc_id not in processed_doc_ids:
                    processed_doc_ids.add(doc_id)
                    evidence_records.append(EvidenceRecord.model_validate(record_data))
                    successful += 1
                    loaded += 1
            if loaded:
                logger.info(
                    "Resumed %d records from %s", loaded, source_path,
                )
        except Exception as exc:
            logger.warning("Failed to load existing output %s: %s", source_path, exc)
            print(
                f"[preprocess] ERROR: failed to load {source_path}: {exc}",
                flush=True,
            )
            print(
                f"[preprocess] Backup saved at {backup_dir}. Will NOT overwrite — aborting.",
                flush=True,
            )
            raise RuntimeError(
                f"Failed to load existing output {source_path}. "
                f"Backup saved at {backup_dir}. Fix the issue before restarting."
            ) from exc

    if processed_doc_ids:
        print(
            f"[preprocess] resumed {len(processed_doc_ids)} existing records from {len(resume_sources)} file(s)",
            flush=True,
        )

    if config.data_root and config.domain_ids:
        data_root = Path(config.data_root)
        if not data_root.is_dir():
            raise FileNotFoundError(f"preprocessing data_root not found: {data_root}")
        domain_documents = parse_multi_domain_directory(
            data_root=data_root,
            domain_ids=config.domain_ids,
            role=config.role,
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
                limited_docs = documents[:max_docs] if max_docs is not None else documents
                domain_stats[domain_id][doc_type] = len(limited_docs)
                for doc in limited_docs:
                    # Skip already-processed documents (resume support)
                    if doc.doc_id in processed_doc_ids:
                        continue

                    normalized_content = normalize_content(doc.content)
                    if len(normalized_content) > _MAX_DOC_CONTENT_LENGTH:
                        normalized_content = normalized_content[:_MAX_DOC_CONTENT_LENGTH] + "\n... [truncated]"
                    doc.content = normalized_content

                    result = extractor.extract(doc)
                    if result.extraction_quality == "failed":
                        raise RuntimeError(
                            f"LLM extraction returned failed for {doc.doc_id} ({domain_id}/{doc_type})"
                        )

                    evidence_record = extraction_to_evidence_record(doc, result)
                    evidence_records.append(evidence_record)
                    successful += 1
                    if True:
                        elapsed = time.time() - start_time
                        step_count = len(evidence_record.step_records)
                        step_concepts = sum(len(sr.concept_mentions) for sr in evidence_record.step_records)
                        step_relations = sum(len(sr.relation_mentions) for sr in evidence_record.step_records)
                        step_actions = sum(len(sr.step_actions) for sr in evidence_record.step_records)
                        diag_edges = sum(len(sr.diagnostic_edges) for sr in evidence_record.step_records)
                        doc_concepts = len(evidence_record.document_concept_mentions)
                        doc_relations = len(evidence_record.document_relation_mentions)
                        print(
                            f"[preprocess] {successful:>4d} | {doc.doc_id} | "
                            f"LLM: {len(result.concepts)}c/{len(result.relations)}r/{len(result.diagnostic_edges)}d | "
                            f"Evidence: {step_count}steps {step_concepts}c/{step_relations}r/{step_actions}a/{diag_edges}d + "
                            f"doc:{doc_concepts}c/{doc_relations}r | "
                            f"{elapsed:.0f}s ({elapsed / successful:.0f}s/doc)",
                            flush=True,
                        )
                        logger.info(
                            "[preprocess] %s | LLM: concepts=%d relations=%d diag=%d | "
                            "Evidence: steps=%d step_c=%d step_r=%d actions=%d diag=%d doc_c=%d doc_r=%d | %.1fs",
                            doc.doc_id,
                            len(result.concepts), len(result.relations), len(result.diagnostic_edges),
                            step_count, step_concepts, step_relations, step_actions, diag_edges,
                            doc_concepts, doc_relations,
                            elapsed,
                        )

                    # Incremental write: save after every document so work is never lost
                    _write_output(output_path, config, successful, domain_stats, evidence_records)
    else:
        raise ValueError(
            "Preprocessing requires multi-domain configuration. "
            "Set data_root and domain_ids in config. "
            "Single-domain legacy mode is not supported."
        )

    output_data = {
        "project_name": "crossextend_kg_preprocessing",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "domains": config.domain_ids,
        "role": config.role,
        "document_count": successful,
        "domain_stats": domain_stats,
        "evidence_records": [record.model_dump(mode="json") for record in evidence_records],
    }
    write_json(output_path, output_data)

    records_by_domain: dict[str, list[EvidenceRecord]] = {domain_id: [] for domain_id in config.domain_ids}
    for record in evidence_records:
        records_by_domain.setdefault(record.domain_id, []).append(record)

    domain_output_paths: dict[str, str] = {}
    for domain_id in config.domain_ids:
        domain_output_path = _build_domain_output_path(output_path, domain_id, len(config.domain_ids))
        write_json(
            domain_output_path,
            {
                "project_name": "crossextend_kg_preprocessing",
                "generated_at": output_data["generated_at"],
                "domains": [domain_id],
                "role": config.role,
                "document_count": len(records_by_domain.get(domain_id, [])),
                "domain_stats": {domain_id: domain_stats.get(domain_id, {})},
                "evidence_records": [
                    record.model_dump(mode="json") for record in records_by_domain.get(domain_id, [])
                ],
            },
        )
        domain_output_paths[domain_id] = str(domain_output_path)

    total_docs = sum(sum(type_count.values()) for type_count in domain_stats.values())
    evidence_records_path = str(output_path.parent if len(config.domain_ids) > 1 else output_path)

    return PreprocessingResult(
        config_path=str(Path(config_path).resolve()) if config_path else "",
        data_root=config.data_root,
        output_path=str(output_path),
        domain_output_paths=domain_output_paths,
        domain_ids=list(config.domain_ids),
        total_docs=total_docs,
        successful_docs=successful,
        failed_docs=failed,
        evidence_records_path=evidence_records_path,
        processing_time_sec=time.time() - start_time,
        domain_stats=domain_stats,
        errors=errors,
    )


def extraction_to_evidence_record(doc: DocumentInput, extraction: ExtractionResult) -> EvidenceRecord:
    """Convert extraction result to step-aware EvidenceRecord."""
    step_rows_list = _extract_step_rows(doc.content)
    step_rows = {step_id: row_text for step_id, row_text in step_rows_list}
    alias_map = _build_document_alias_map(extraction.concepts, extraction.relations)

    if not step_rows:
        concept_mentions = [
            _build_concept_mention(
                concept_data,
                fallback_label=_canonicalize_label(str(concept_data.get("label", "")).strip(), alias_map),
            )
            for concept_data in extraction.concepts
            if str(concept_data.get("label", "")).strip()
        ]
        relation_mentions: list[RelationMention] = []
        for relation_data in extraction.relations:
            normalized_relation = _normalize_relation_entry(relation_data)
            if normalized_relation is None:
                continue
            relation_mentions.append(
                RelationMention(
                    label=normalized_relation["label"],
                    family=normalized_relation["family"],
                    head=_normalize_endpoint(_canonicalize_label(normalized_relation["head"], alias_map)),
                    tail=_normalize_endpoint(_canonicalize_label(normalized_relation["tail"], alias_map)),
                )
            )
        return EvidenceRecord(
            evidence_id=doc.doc_id,
            domain_id=doc.domain_id,
            role=doc.role,
            source_type=doc.doc_type,
            timestamp=doc.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            raw_text=doc.content,
            step_records=[],
            document_concept_mentions=concept_mentions,
            document_relation_mentions=_dedupe_relations(relation_mentions),
            procedure_meta=_infer_procedure_meta(doc.content, doc.doc_id),
        )

    concept_catalog: dict[str, ConceptMention] = {}
    for concept_data in extraction.concepts:
        canonical_label = _canonicalize_label(str(concept_data.get("label", "")).strip(), alias_map)
        mention = _build_concept_mention(concept_data, fallback_label=canonical_label)
        if not mention.label:
            continue
        if _extract_step_id(mention.label) in step_rows:
            continue
        _merge_concept_mention(concept_catalog, mention)

    step_concepts: dict[str, dict[str, ConceptMention]] = {step_id: {} for step_id in step_rows}
    step_relations: dict[str, list[RelationMention]] = {step_id: [] for step_id in step_rows}
    document_relations: list[RelationMention] = []

    for relation_data in extraction.relations:
        normalized_relation = _normalize_relation_entry(relation_data)
        if normalized_relation is None:
            continue
        head = _normalize_endpoint(_canonicalize_label(normalized_relation["head"], alias_map))
        tail = _normalize_endpoint(_canonicalize_label(normalized_relation["tail"], alias_map))
        family = normalized_relation["family"]
        if normalized_relation["label"] == "triggers" and _extract_step_id(head) and _extract_step_id(tail):
            family = "task_dependency"

        relation = RelationMention(
            label=normalized_relation["label"],
            family=family,
            head=head,
            tail=tail,
        )
        head_step = _extract_step_id(head)
        tail_step = _extract_step_id(tail)
        owner_step = head_step if head_step in step_rows else (tail_step if tail_step in step_rows else None)
        if owner_step is None:
            relation = _rewrite_document_relation(relation, concept_catalog)
            relation = _rewrite_communication_relation(relation, concept_catalog)
            if not _should_keep_document_relation(relation):
                continue
            document_relations.append(relation)
            continue

        step_relations[owner_step].append(relation)
        for endpoint in (head, tail):
            if _extract_step_id(endpoint):
                continue
            mention = concept_catalog.get(endpoint) or ConceptMention(
                label=endpoint,
                description="",
                node_worthy=True,
                surface_form=endpoint,
            )
            _merge_concept_mention(step_concepts[owner_step], mention)

    assigned_labels = {label for mentions in step_concepts.values() for label in mentions}
    document_concepts: dict[str, ConceptMention] = {}
    for label, mention in concept_catalog.items():
        if label in assigned_labels:
            continue
        inferred_step_ids = _infer_step_ids_from_surface(label, step_rows)
        if inferred_step_ids:
            for step_id in inferred_step_ids:
                _merge_concept_mention(step_concepts[step_id], mention)
            continue
        _merge_concept_mention(document_concepts, mention)

    step_ids = list(step_rows)
    for index, step_id in enumerate(step_ids[:-1]):
        next_step_id = step_ids[index + 1]
        trigger_relation = RelationMention(
            label="triggers",
            family="task_dependency",
            head=step_id,
            tail=next_step_id,
        )
        step_relations[step_id].append(trigger_relation)

    step_records: list[StepRecord] = []
    step_ids_list = list(step_rows)
    for index, step_id in enumerate(step_ids_list):
        surface_form_text = step_rows[step_id]
        step_phase = _infer_step_phase(surface_form_text)
        step_summary = surface_form_text.split(".")[0].strip()[:72] if surface_form_text else ""
        sequence_next = step_ids_list[index + 1] if index + 1 < len(step_ids_list) else None

        # Extract step_actions from task_dependency relations where head=this step, tail=concept
        step_actions: list[StepAction] = []
        for rel in step_relations.get(step_id, []):
            if rel.family == "task_dependency" and _extract_step_id(rel.head) == step_id and not _extract_step_id(rel.tail):
                step_actions.append(StepAction(action_type=rel.label, target_label=rel.tail))

        # Separate structural edges from relation_mentions
        structural_edges: list[StructuralEdge] = []
        for rel in step_relations.get(step_id, []):
            if rel.family == "structural":
                structural_edges.append(StructuralEdge(label=rel.label, family=rel.family, head=rel.head, tail=rel.tail))

        # Separate diagnostic edges (communication/propagation)
        diag_edges: list[DiagnosticEdge] = []
        for rel in step_relations.get(step_id, []):
            if rel.family in ("communication", "propagation"):
                diag_edges.append(DiagnosticEdge(
                    evidence_label=rel.head,
                    indicated_label=rel.tail,
                    mechanism=rel.family,
                ))

        # Extract state transitions from lifecycle relations
        state_transitions: list[StateTransition] = []
        for rel in step_relations.get(step_id, []):
            if rel.family == "lifecycle" and rel.label in ("transitionsTo", "hasState"):
                state_transitions.append(StateTransition(
                    from_state=rel.head,
                    to_state=rel.tail,
                    trigger_step=step_id,
                ))

        step_records.append(
            StepRecord(
                step_id=step_id,
                task=StepConceptMention(
                    label=step_id,
                    description="",
                    node_worthy=True,
                    surface_form=surface_form_text,
                ),
                concept_mentions=sorted(step_concepts[step_id].values(), key=lambda item: item.label.lower()),
                relation_mentions=_dedupe_relations(step_relations[step_id]),
                step_phase=step_phase,
                step_summary=step_summary,
                surface_form=surface_form_text,
                step_actions=step_actions,
                structural_edges=structural_edges,
                state_transitions=state_transitions,
                diagnostic_edges=diag_edges,
                sequence_next=sequence_next,
            )
        )

    # Extract state_transitions and diagnostic_edges from LLM output
    llm_state_transitions: list[StateTransition] = []
    for st_data in getattr(extraction, "state_transitions", []) or []:
        if not isinstance(st_data, dict):
            continue
        llm_state_transitions.append(StateTransition(
            from_state=str(st_data.get("from_state", "")).strip(),
            to_state=str(st_data.get("to_state", "")).strip(),
            trigger_step=str(st_data.get("trigger_step", "")).strip() or None,
            evidence_label=str(st_data.get("evidence_label", "")).strip() or None,
        ))

    llm_diagnostic_edges: list[DiagnosticEdge] = []
    for de_data in getattr(extraction, "diagnostic_edges", []) or []:
        if not isinstance(de_data, dict):
            continue
        llm_diagnostic_edges.append(DiagnosticEdge(
            evidence_label=str(de_data.get("evidence_label", "")).strip(),
            indicated_label=str(de_data.get("indicated_label", "")).strip(),
            mechanism=str(de_data.get("mechanism", "")).strip() or None,
        ))

    step_record_by_id = {step.step_id: step for step in step_records}
    for transition in llm_state_transitions:
        if transition.trigger_step and transition.trigger_step in step_record_by_id:
            step_record_by_id[transition.trigger_step].state_transitions.append(transition)

    for diagnostic_edge in llm_diagnostic_edges:
        for step_id, concepts in step_concepts.items():
            if diagnostic_edge.evidence_label in concepts or diagnostic_edge.indicated_label in concepts:
                step_record_by_id[step_id].diagnostic_edges.append(diagnostic_edge)

    # Build cross_step_relations from document-level communication/propagation relations
    cross_step_relations: list[CrossStepRelation] = []
    for rel in document_relations:
        if rel.family in ("communication", "propagation"):
            head_step = None
            tail_step = None
            for sid, concepts in step_concepts.items():
                if rel.head in concepts:
                    head_step = sid
                if rel.tail in concepts:
                    tail_step = sid
            if head_step or tail_step:
                cross_step_relations.append(CrossStepRelation(
                    label=rel.label,
                    family=rel.family,
                    head=rel.head,
                    tail=rel.tail,
                    head_step=head_step,
                    tail_step=tail_step,
                ))

    procedure_meta = _infer_procedure_meta(doc.content, doc.doc_id)

    return EvidenceRecord(
        evidence_id=doc.doc_id,
        domain_id=doc.domain_id,
        role=doc.role,
        source_type=doc.doc_type,
        timestamp=doc.timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        raw_text=doc.content,
        step_records=step_records,
        document_concept_mentions=sorted(document_concepts.values(), key=lambda item: item.label.lower()),
        document_relation_mentions=_dedupe_relations(document_relations),
        procedure_meta=procedure_meta,
        cross_step_relations=cross_step_relations,
    )


def load_preprocessing_config(config_path: str) -> PreprocessingConfig:
    """Load preprocessing config from a JSON or YAML file."""
    path, data = load_structured_config_payload(config_path)
    data = resolve_preprocessing_payload_paths(data, base_dir=path.parent)
    config = PreprocessingConfig.model_validate(data)
    return config


def preprocess_single_document(
    doc_path: str,
    domain_id: str,
    role: str,
    llm_config: dict[str, Any],
    output_path: str,
) -> EvidenceRecord:
    """Preprocess a single document (convenience function)."""
    doc_path_obj = Path(doc_path)

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

    inferred_doc_type = infer_doc_type_from_filename(doc_path_obj)
    if inferred_doc_type is None:
        inferred_doc_type = classify_doc_type(doc_path_obj.read_text(encoding="utf-8-sig"))
    doc = parse_markdown_file(
        doc_path_obj,
        domain_id=domain_id,
        role=role,
        doc_type=inferred_doc_type,
    )

    extractor = build_extractor(config)
    result = extractor.extract(doc)
    return extraction_to_evidence_record(doc, result)
