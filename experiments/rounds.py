#!/usr/bin/env python3
"""Round-execution helpers for aligned corpus staging and audit collection."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from crossextend_kg.config import (
        load_structured_config_payload,
        resolve_pipeline_payload_paths,
        resolve_preprocessing_payload_paths,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import (
        load_structured_config_payload,
        resolve_pipeline_payload_paths,
        resolve_preprocessing_payload_paths,
    )
try:
    from crossextend_kg.file_io import ensure_dir, write_json
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import ensure_dir, write_json
from experiments.metrics import evaluate_variant_run, read_json


DEFAULT_FULL_GOLD_ALIGNMENT: dict[str, dict[str, dict[str, str]]] = {
    "battery": {
        "BATOM_001": {
            "gold_file": "data/ground_truth/battery_BATOM_001.json",
            "source_markdown": "data/battery_om_manual_en/BATOM_001.md",
            "alignment_mode": "direct",
        },
        "BATOM_002": {
            "gold_file": "data/ground_truth/battery_BATOM_002.json",
            "source_markdown": "data/battery_om_manual_en/BATOM_002.md",
            "alignment_mode": "direct",
        },
        "BATOM_003": {
            "gold_file": "data/ground_truth/battery_BATOM_003.json",
            "source_markdown": "data/battery_om_manual_en/BATOM_003.md",
            "alignment_mode": "direct",
        },
    },
    "cnc": {
        "CNCOM_001": {
            "gold_file": "data/ground_truth/cnc_CNCOM_001.json",
            "source_markdown": "data/cnc_om_manual_en/CNCOM_001.md",
            "alignment_mode": "direct",
        },
        "CNCOM_002": {
            "gold_file": "data/ground_truth/cnc_CNCOM_002.json",
            "source_markdown": "data/cnc_om_manual_en/CNCOM_002.md",
            "alignment_mode": "direct",
        },
        "CNCOM_003": {
            "gold_file": "data/ground_truth/cnc_CNCOM_003.json",
            "source_markdown": "data/cnc_om_manual_en/CNCOM_003.md",
            "alignment_mode": "direct",
        },
    },
    "nev": {
        "EVMAN_001": {
            "gold_file": "data/ground_truth/nev_EVMAN_001.json",
            "source_markdown": "data/ev_om_manual_en/EVMAN_001.md",
            "alignment_mode": "direct",
        },
        "EVMAN_002": {
            "gold_file": "data/ground_truth/nev_EVMAN_002.json",
            "source_markdown": "data/ev_om_manual_en/EVMAN_002.md",
            "alignment_mode": "direct",
        },
        "EVMAN_003": {
            "gold_file": "data/ground_truth/nev_EVMAN_003.json",
            "source_markdown": "data/ev_om_manual_en/EVMAN_003.md",
            "alignment_mode": "direct",
        },
    },
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _stable_docset_key(doc_ids: list[str], alignment: dict[str, dict[str, dict[str, str]]]) -> str:
    selected = sorted(doc_ids)
    all_doc_ids = sorted(
        doc_id
        for domain_map in alignment.values()
        for doc_id in domain_map
    )
    if selected == all_doc_ids:
        return "full_human_gold_9doc"
    digest = hashlib.sha1("|".join(selected).encode("utf-8")).hexdigest()[:10]
    return f"docset_{len(selected)}docs_{digest}"


def _persistent_evidence_root(doc_ids: list[str], alignment: dict[str, dict[str, dict[str, str]]]) -> Path:
    return _repo_root() / "data" / "evidence_records" / _stable_docset_key(doc_ids, alignment)


def resolve_full_gold_alignment(repo_root: str | Path | None = None) -> dict[str, dict[str, dict[str, str]]]:
    root = Path(repo_root).resolve() if repo_root else _repo_root()
    resolved: dict[str, dict[str, dict[str, str]]] = {}
    for domain_id, doc_map in DEFAULT_FULL_GOLD_ALIGNMENT.items():
        resolved[domain_id] = {}
        for doc_id, item in doc_map.items():
            gold_file = (root / item["gold_file"]).resolve()
            source_markdown = (root / item["source_markdown"]).resolve()
            resolved[domain_id][doc_id] = {
                "domain_id": domain_id,
                "doc_id": doc_id,
                "gold_file": str(gold_file),
                "source_markdown": str(source_markdown),
                "alignment_mode": item["alignment_mode"],
                "source_doc_id": source_markdown.stem,
            }
    return resolved


def stage_aligned_input_corpus(
    output_root: str | Path,
    doc_ids: list[str] | None = None,
    alignment: dict[str, dict[str, dict[str, str]]] | None = None,
) -> dict[str, Any]:
    output_root = Path(output_root).resolve()
    ensure_dir(output_root)
    selected_doc_ids = set(doc_ids or [])
    alignment = alignment or resolve_full_gold_alignment()

    manifest_domains: dict[str, dict[str, dict[str, str]]] = {}
    staged_count = 0
    for domain_id, doc_map in alignment.items():
        domain_manifest: dict[str, dict[str, str]] = {}
        for doc_id, item in doc_map.items():
            if selected_doc_ids and doc_id not in selected_doc_ids:
                continue
            source_markdown = Path(item["source_markdown"]).resolve()
            if not source_markdown.exists():
                raise FileNotFoundError(f"source markdown not found for {domain_id}/{doc_id}: {source_markdown}")
            gold_file = Path(item["gold_file"]).resolve()
            if not gold_file.exists():
                raise FileNotFoundError(f"gold file not found for {domain_id}/{doc_id}: {gold_file}")

            staged_path = output_root / domain_id / f"{doc_id}.md"
            ensure_dir(staged_path.parent)
            staged_path.write_text(source_markdown.read_text(encoding="utf-8-sig"), encoding="utf-8")

            domain_manifest[doc_id] = {
                "domain_id": domain_id,
                "doc_id": doc_id,
                "gold_file": str(gold_file),
                "source_markdown": str(source_markdown),
                "staged_markdown": str(staged_path),
                "alignment_mode": item["alignment_mode"],
                "source_doc_id": item.get("source_doc_id") or source_markdown.stem,
            }
            staged_count += 1
        if domain_manifest:
            manifest_domains[domain_id] = domain_manifest

    manifest = {
        "generated_at": _utc_now(),
        "doc_count": staged_count,
        "selected_doc_ids": sorted(selected_doc_ids) if selected_doc_ids else [],
        "domains": manifest_domains,
    }
    write_json(output_root / "data_alignment.json", manifest)
    return manifest


def expected_preprocessing_outputs(
    output_path: str | Path,
    domain_ids: list[str],
) -> dict[str, str]:
    output_path = Path(output_path).resolve()
    if len(domain_ids) <= 1:
        return {domain_ids[0]: str(output_path)}
    return {
        domain_id: str(output_path.with_name(f"{domain_id}_{output_path.name}"))
        for domain_id in domain_ids
    }


def materialize_round_preprocessing_config(
    base_config_path: str | Path,
    config_output_path: str | Path,
    *,
    data_root: str | Path,
    domain_ids: list[str],
    output_path: str | Path,
    llm_temperature: float | None = 0.0,
) -> Path:
    base_config_path = Path(base_config_path).resolve()
    config_output_path = Path(config_output_path).resolve()
    _, payload = load_structured_config_payload(base_config_path)
    payload = resolve_preprocessing_payload_paths(payload, base_dir=base_config_path.parent)

    payload["data_root"] = str(Path(data_root).resolve())
    payload["domain_ids"] = list(domain_ids)
    payload["output_path"] = str(Path(output_path).resolve())
    if llm_temperature is not None:
        payload.setdefault("llm", {})["temperature"] = llm_temperature

    ensure_dir(config_output_path.parent)
    config_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_output_path


def materialize_round_pipeline_config(
    base_config_path: str | Path,
    config_output_path: str | Path,
    *,
    evidence_paths_by_domain: dict[str, str],
    artifact_root: str | Path,
    benchmark_name: str,
    run_prefix: str,
    llm_temperature: float | None = 0.0,
    write_detailed_working_artifacts: bool = True,
    write_jsonl_artifacts: bool = False,
    write_graph_db_csv: bool = False,
    write_property_graph_jsonl: bool = False,
) -> Path:
    base_config_path = Path(base_config_path).resolve()
    config_output_path = Path(config_output_path).resolve()
    _, payload = load_structured_config_payload(base_config_path)
    payload = resolve_pipeline_payload_paths(payload, base_dir=base_config_path.parent)

    selected_domain_ids = list(evidence_paths_by_domain)
    domain_payloads = []
    for domain in payload.get("domains", []):
        domain_id = str(domain.get("domain_id", "")).strip()
        if domain_id not in evidence_paths_by_domain:
            continue
        item = dict(domain)
        item["data_path"] = str(Path(evidence_paths_by_domain[domain_id]).resolve())
        domain_payloads.append(item)

    if len(domain_payloads) != len(selected_domain_ids):
        discovered = {item["domain_id"] for item in domain_payloads}
        missing = [domain_id for domain_id in selected_domain_ids if domain_id not in discovered]
        raise ValueError(f"base pipeline config missing domains required by round config: {missing}")

    payload["benchmark_name"] = benchmark_name
    payload["domains"] = domain_payloads
    if llm_temperature is not None:
        payload.setdefault("llm", {})["temperature"] = llm_temperature

    runtime = payload.setdefault("runtime", {})
    runtime["artifact_root"] = str(Path(artifact_root).resolve())
    runtime["run_prefix"] = run_prefix
    runtime["write_detailed_working_artifacts"] = write_detailed_working_artifacts
    runtime["write_jsonl_artifacts"] = write_jsonl_artifacts
    runtime["write_graph_db_csv"] = write_graph_db_csv
    runtime["write_property_graph_jsonl"] = write_property_graph_jsonl

    ensure_dir(config_output_path.parent)
    config_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_output_path


def prepare_round_workspace(
    round_dir: str | Path,
    *,
    doc_ids: list[str],
    alignment: dict[str, dict[str, dict[str, str]]] | None = None,
    base_preprocess_config_path: str | Path,
    base_pipeline_config_path: str | Path,
    benchmark_name: str,
    run_prefix: str,
    llm_temperature: float | None = 0.0,
    write_detailed_working_artifacts: bool = True,
    write_jsonl_artifacts: bool = False,
    write_graph_db_csv: bool = False,
    write_property_graph_jsonl: bool = False,
) -> dict[str, Any]:
    round_dir = Path(round_dir).resolve()
    input_root = round_dir / "input"
    config_root = round_dir / "configs"
    output_root = round_dir / "output"
    alignment = alignment or resolve_full_gold_alignment()
    evidence_root = _persistent_evidence_root(doc_ids, alignment)

    alignment_manifest = stage_aligned_input_corpus(input_root, doc_ids=doc_ids, alignment=alignment)
    domain_ids = sorted(alignment_manifest["domains"])
    if not domain_ids:
        raise ValueError("prepare_round_workspace received no docs to stage")

    evidence_output_path = evidence_root / "evidence_records_llm.json"
    evidence_paths_by_domain = expected_preprocessing_outputs(evidence_output_path, domain_ids)
    preprocess_config_path = materialize_round_preprocessing_config(
        base_preprocess_config_path,
        config_root / "preprocessing.round.json",
        data_root=input_root,
        domain_ids=domain_ids,
        output_path=evidence_output_path,
        llm_temperature=llm_temperature,
    )
    pipeline_config_path = materialize_round_pipeline_config(
        base_pipeline_config_path,
        config_root / "pipeline.round.json",
        evidence_paths_by_domain=evidence_paths_by_domain,
        artifact_root=output_root,
        benchmark_name=benchmark_name,
        run_prefix=run_prefix,
        llm_temperature=llm_temperature,
        write_detailed_working_artifacts=write_detailed_working_artifacts,
        write_jsonl_artifacts=write_jsonl_artifacts,
        write_graph_db_csv=write_graph_db_csv,
        write_property_graph_jsonl=write_property_graph_jsonl,
    )

    manifest = {
        "generated_at": _utc_now(),
        "round_dir": str(round_dir),
        "doc_ids": list(doc_ids),
        "domain_ids": domain_ids,
        "input_root": str(input_root),
        "alignment_manifest_path": str((input_root / "data_alignment.json").resolve()),
        "preprocess_config_path": str(preprocess_config_path),
        "pipeline_config_path": str(pipeline_config_path),
        "artifact_root": str(output_root),
        "persistent_evidence_root": str(evidence_root),
        "evidence_paths_by_domain": evidence_paths_by_domain,
    }
    write_json(round_dir / "prepared_workspace.json", manifest)
    return manifest


def collect_variant_audit_summary(
    run_root: str | Path,
    variant_id: str,
) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    working_root = run_root / variant_id / "working"
    if not working_root.exists():
        raise FileNotFoundError(f"variant working directory not found: {working_root}")

    domains: dict[str, dict[str, Any]] = {}
    for domain_root in sorted(item for item in working_root.iterdir() if item.is_dir()):
        attachment_audit_path = domain_root / "attachment_audit.json"
        final_graph_path = domain_root / "final_graph.json"
        if not attachment_audit_path.exists() or not final_graph_path.exists():
            continue

        attachment_payload = read_json(attachment_audit_path)
        graph_payload = read_json(final_graph_path)

        relation_family_distribution: dict[str, int] = {}
        provenance_distribution: dict[str, int] = {}
        for edge in graph_payload.get("edges", []):
            family = str(edge.get("family", "")).strip() or "unknown"
            relation_family_distribution[family] = relation_family_distribution.get(family, 0) + 1
            for evidence_id in edge.get("provenance_evidence_ids", []) or []:
                provenance_distribution[evidence_id] = provenance_distribution.get(evidence_id, 0) + 1

        parent_anchor_distribution: dict[str, int] = {}
        node_type_distribution: dict[str, int] = {}
        for node in graph_payload.get("nodes", []):
            node_type = str(node.get("node_type", "")).strip() or "unknown"
            node_type_distribution[node_type] = node_type_distribution.get(node_type, 0) + 1
            anchor = str(node.get("parent_anchor") or "").strip() or (
                str(node.get("label", "")).strip() if node_type == "backbone_concept" else "unanchored"
            )
            parent_anchor_distribution[anchor] = parent_anchor_distribution.get(anchor, 0) + 1

        domains[domain_root.name] = {
            "attachment_audit_path": str(attachment_audit_path.resolve()),
            "final_graph_path": str(final_graph_path.resolve()),
            "candidate_count": int(attachment_payload.get("summary", {}).get("candidate_count", 0)),
            "accepted_adapter_candidate_count": int(
                attachment_payload.get("summary", {}).get("accepted_adapter_candidate_count", 0)
            ),
            "accepted_backbone_reuse_count": int(
                attachment_payload.get("summary", {}).get("accepted_backbone_reuse_count", 0)
            ),
            "rejected_candidate_count": int(
                attachment_payload.get("summary", {}).get("rejected_candidate_count", 0)
            ),
            "reject_reason_distribution": attachment_payload.get("summary", {}).get("rejected_by_reason", {}),
            "graph_summary": graph_payload.get("summary", {}),
            "relation_validation": graph_payload.get("relation_validation", {}),
            "relation_family_distribution": relation_family_distribution,
            "parent_anchor_distribution": parent_anchor_distribution,
            "node_type_distribution": node_type_distribution,
            "edge_provenance_distribution": provenance_distribution,
        }

    return {
        "generated_at": _utc_now(),
        "run_root": str(run_root),
        "variant_id": variant_id,
        "domains": domains,
    }


def evaluate_round_variant(
    run_root: str | Path,
    variant_id: str,
    *,
    ground_truth_dir: str | Path | None = None,
    gold_file_names: list[str] | None = None,
) -> dict[str, Any]:
    return evaluate_variant_run(
        run_root=run_root,
        variant_id=variant_id,
        ground_truth_dir=ground_truth_dir,
        gold_file_names=gold_file_names,
    )
