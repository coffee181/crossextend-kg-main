#!/usr/bin/env python3
"""Evidence normalization and schema-candidate extraction."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from ..config import PipelineConfig
from ..io import load_evidence_records
from ..models import EvidenceRecord, EvidenceUnit, SchemaCandidate
from .utils import normalize_text


def load_records_by_domain(config: PipelineConfig) -> dict[str, list[EvidenceRecord]]:
    cache: dict[str, list[EvidenceRecord]] = {}
    records_by_domain: dict[str, list[EvidenceRecord]] = {}
    for domain in config.domains:
        if domain.data_path not in cache:
            cache[domain.data_path] = load_evidence_records(domain.data_path)
        for record in cache[domain.data_path]:
            if record.domain_id == domain.domain_id and record.role != domain.role:
                raise ValueError(
                    f"record role mismatch for domain {domain.domain_id}: "
                    f"expected {domain.role}, got {record.role}"
                )
        records = [
            record
            for record in cache[domain.data_path]
            if record.domain_id == domain.domain_id and record.source_type in domain.source_types
        ]
        records.sort(key=lambda item: item.timestamp)
        records_by_domain[domain.domain_id] = records
    return records_by_domain


def build_evidence_units(config: PipelineConfig, records_by_domain: dict[str, list[EvidenceRecord]]) -> list[EvidenceUnit]:
    units: list[EvidenceUnit] = []
    for domain in config.domains:
        for index, record in enumerate(records_by_domain[domain.domain_id]):
            units.append(
                EvidenceUnit(
                    evidence_id=record.evidence_id,
                    domain_id=record.domain_id,
                    role=record.role,
                    source_id=Path(domain.data_path).name,
                    source_type=record.source_type,
                    locator=f"{domain.domain_id}/{record.source_type}/{index}",
                    raw_text=record.raw_text,
                    normalized_text=normalize_text(record.raw_text, config.data.normalize_whitespace),
                    metadata={"timestamp": record.timestamp},
                )
            )
    return units


def aggregate_schema_candidates(records_by_domain: dict[str, list[EvidenceRecord]]) -> dict[str, list[SchemaCandidate]]:
    grouped: dict[tuple[str, str], dict] = {}
    descriptions: dict[tuple[str, str], list[str]] = defaultdict(list)
    relation_participation: Counter[tuple[str, str]] = Counter()
    relation_head_participation: Counter[tuple[str, str]] = Counter()
    relation_tail_participation: Counter[tuple[str, str]] = Counter()
    relation_families: dict[tuple[str, str], set[str]] = defaultdict(set)

    for domain_id, records in records_by_domain.items():
        for record in records:
            for relation in record.relation_mentions:
                head_key = (domain_id, relation.head)
                tail_key = (domain_id, relation.tail)
                relation_participation[head_key] += 1
                relation_participation[tail_key] += 1
                relation_head_participation[head_key] += 1
                relation_tail_participation[tail_key] += 1
                relation_families[head_key].add(relation.family)
                relation_families[tail_key].add(relation.family)
            for mention in record.concept_mentions:
                if not mention.node_worthy:
                    continue
                key = (domain_id, mention.label)
                grouped.setdefault(
                    key,
                    {
                        "candidate_id": f"{domain_id}::{mention.label}",
                        "domain_id": domain_id,
                        "role": record.role,
                        "label": mention.label,
                        "description": mention.description,
                        "evidence_ids": [],
                        "evidence_texts": [],
                        "support_count": 0,
                        "routing_features": {},
                    },
                )
                grouped[key]["evidence_ids"].append(record.evidence_id)
                grouped[key]["evidence_texts"].append(record.raw_text)
                grouped[key]["support_count"] += 1
                if mention.description:
                    descriptions[key].append(mention.description)

    results: dict[str, list[SchemaCandidate]] = {domain_id: [] for domain_id in records_by_domain}
    for key, item in grouped.items():
        description = Counter(descriptions[key]).most_common(1)[0][0] if descriptions[key] else item["description"]
        item["description"] = description
        item["routing_features"] = {
            "support_count": item["support_count"],
            "evidence_count": len(item["evidence_ids"]),
            "relation_participation_count": relation_participation[key],
            "relation_head_count": relation_head_participation[key],
            "relation_tail_count": relation_tail_participation[key],
            "relation_families": sorted(relation_families[key]),
        }
        results[item["domain_id"]].append(SchemaCandidate.model_validate(item))

    for domain_id in results:
        results[domain_id].sort(key=lambda candidate: candidate.label)
    return results
