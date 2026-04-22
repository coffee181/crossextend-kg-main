#!/usr/bin/env python3
"""Baseline experiment runners for CrossExtend-KG."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from crossextend_kg.config import VariantConfig, load_pipeline_config
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import VariantConfig, load_pipeline_config
try:
    from crossextend_kg.models import AttachmentDecision, PipelineBenchmarkResult, VariantRunResult
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import AttachmentDecision, PipelineBenchmarkResult, VariantRunResult
from pipeline.artifacts import export_benchmark_summary, export_variant_run, write_latest_summary
from pipeline.attachment import build_deterministic_decisions
from pipeline.backbone import build_backbone
from pipeline.evidence import (
    aggregate_schema_candidates,
    build_evidence_units,
    load_records_by_domain,
    normalize_records_by_domain,
)
from pipeline.graph import assemble_domain_graphs, build_domain_schemas
from pipeline.router import empty_retrievals
from pipeline.runner import _build_variant_construction_summary
from pipeline.utils import utc_now
from rules.filtering import filter_attachment_decision, preferred_parent_anchor
from experiments.comparison import build_variant_summary_rows, compare_variant_evaluations, write_comparison_csv
from experiments.metrics import evaluate_variant_run, write_ablation_csv
from experiments.baselines.rule_preprocessing import build_rule_records_by_domain, write_rule_records_bundle


DEFAULT_BASELINE_SPECS: list[dict[str, Any]] = [
    {
        "variant_id": "rule_pipeline",
        "description": "Rule-based preprocessing with deterministic attachment and no LLM calls",
        "component": "baseline",
        "mode": "reference",
        "preprocessing_source": "rule",
        "attachment_source": "deterministic",
        "uses_llm_preprocessing": False,
        "uses_llm_attachment": False,
        "paper_table": True,
    },
    {
        "variant_id": "llm_direct_graph",
        "description": "Direct graph materialization from LLM evidence records without attachment-stage LLM routing",
        "component": "baseline",
        "mode": "reference",
        "preprocessing_source": "llm",
        "attachment_source": "direct_graph",
        "uses_llm_preprocessing": True,
        "uses_llm_attachment": False,
        "paper_table": True,
    },
]


def baseline_spec_index() -> dict[str, dict[str, Any]]:
    return {spec["variant_id"]: dict(spec) for spec in DEFAULT_BASELINE_SPECS}


def _baseline_variant_config(spec: dict[str, Any]) -> VariantConfig:
    return VariantConfig.model_validate(
        {
            "variant_id": spec["variant_id"],
            "description": spec["description"],
            "attachment_strategy": "deterministic",
            "use_embedding_routing": False,
            "use_rule_filter": spec["variant_id"] == "rule_pipeline",
            "allow_free_form_growth": False,
            "enable_snapshots": True,
            "export_artifacts": True,
        }
    )


def _build_direct_graph_decisions(
    candidates_by_domain: dict[str, list[Any]],
    backbone_concepts: set[str],
) -> dict[str, dict[str, AttachmentDecision]]:
    decisions_by_domain: dict[str, dict[str, AttachmentDecision]] = {}
    for domain_id, candidates in candidates_by_domain.items():
        domain_decisions: dict[str, AttachmentDecision] = {}
        for candidate in candidates:
            if candidate.label in backbone_concepts:
                domain_decisions[candidate.candidate_id] = AttachmentDecision(
                    candidate_id=candidate.candidate_id,
                    label=candidate.label,
                    route="reuse_backbone",
                    parent_anchor=None,
                    accept=True,
                    admit_as_node=True,
                    reject_reason=None,
                    confidence=1.0,
                    justification="direct graph baseline reused frozen backbone label",
                    evidence_ids=list(candidate.evidence_ids),
                )
                continue
            anchor = preferred_parent_anchor(candidate)
            if anchor and anchor in backbone_concepts:
                domain_decisions[candidate.candidate_id] = AttachmentDecision(
                    candidate_id=candidate.candidate_id,
                    label=candidate.label,
                    route="vertical_specialize",
                    parent_anchor=anchor,
                    accept=True,
                    admit_as_node=True,
                    reject_reason=None,
                    confidence=0.6,
                    justification="direct graph baseline inferred parent anchor from candidate semantics",
                    evidence_ids=list(candidate.evidence_ids),
                )
            else:
                domain_decisions[candidate.candidate_id] = AttachmentDecision(
                    candidate_id=candidate.candidate_id,
                    label=candidate.label,
                    route="reject",
                    parent_anchor=None,
                    accept=False,
                    admit_as_node=False,
                    reject_reason="cannot_anchor_backbone",
                    confidence=0.0,
                    justification="direct graph baseline could not infer a stable parent anchor",
                    evidence_ids=list(candidate.evidence_ids),
                )
        decisions_by_domain[domain_id] = domain_decisions
    return decisions_by_domain


def _build_rule_pipeline_decisions(
    config,
    candidates_by_domain: dict[str, list[Any]],
    backbone_concepts: set[str],
) -> tuple[dict[str, dict[str, list[Any]]], dict[str, dict[str, AttachmentDecision]]]:
    retrievals_by_domain = {
        domain_id: empty_retrievals(candidates)
        for domain_id, candidates in candidates_by_domain.items()
    }
    decisions_by_domain: dict[str, dict[str, AttachmentDecision]] = {}

    for domain in config.domains:
        candidates = candidates_by_domain.get(domain.domain_id, [])
        retrievals = retrievals_by_domain[domain.domain_id]
        decisions = {
            decision.candidate_id: decision
            for decision in build_deterministic_decisions(
                candidates,
                retrievals,
                backbone_concepts,
                allow_free_form_growth=False,
            )
        }
        filtered: dict[str, AttachmentDecision] = {}
        for candidate in candidates:
            filtered[candidate.candidate_id] = filter_attachment_decision(
                candidate=candidate,
                decision=decisions[candidate.candidate_id],
                backbone_concepts=backbone_concepts,
                allowed_routes=set(config.relations.allowed_routes),
                allow_free_form_growth=False,
                min_relation_support_count=config.runtime.min_relation_support_count,
            )
        decisions_by_domain[domain.domain_id] = filtered

    return retrievals_by_domain, decisions_by_domain


def _build_result(
    config,
    variant: VariantConfig,
    records_by_domain: dict[str, list[Any]],
    retrievals_by_domain: dict[str, dict[str, list[Any]]],
    decisions_by_domain: dict[str, dict[str, AttachmentDecision]],
    backbone_concepts: list[str],
    backbone_descriptions: dict[str, str],
    curated_backbone_concepts: list[str],
) -> VariantRunResult:
    evidence_units = build_evidence_units(config, records_by_domain)
    candidates_by_domain = aggregate_schema_candidates(records_by_domain, assume_normalized=True)
    schemas = build_domain_schemas(
        config=config,
        candidates_by_domain=candidates_by_domain,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=backbone_concepts,
    )
    domain_graphs = assemble_domain_graphs(
        config=config,
        variant=variant,
        records_by_domain=records_by_domain,
        schemas=schemas,
        decisions_by_domain=decisions_by_domain,
        backbone_concepts=backbone_concepts,
    )
    result = VariantRunResult(
        variant_id=variant.variant_id,
        variant_description=variant.description,
        seed_backbone_concepts=list(config.backbone.seed_concepts),
        seed_backbone_descriptions=dict(config.backbone.seed_descriptions),
        backbone_concepts=backbone_concepts,
        backbone_descriptions=backbone_descriptions,
        curated_backbone_concepts=curated_backbone_concepts,
        evidence_units=evidence_units,
        candidates_by_domain=candidates_by_domain,
        retrievals=retrievals_by_domain,
        attachment_decisions=decisions_by_domain,
        schemas=schemas,
        domain_graphs=domain_graphs,
        construction_summary={},
    )
    result.construction_summary = _build_variant_construction_summary(result)
    return result


def run_baseline_suite(
    base_config_path: str | Path,
    output_dir: str | Path,
    *,
    ground_truth_dir: str | Path | None = None,
    baseline_ids: list[str] | None = None,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    config = load_pipeline_config(base_config_path)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_root = output_dir / f"baseline-{utc_now().replace(':', '').replace('-', '')}"
    spec_map = baseline_spec_index()
    selected_ids = baseline_ids or [spec["variant_id"] for spec in DEFAULT_BASELINE_SPECS]
    specs = [spec_map[variant_id] for variant_id in selected_ids]

    backbone_concepts, backbone_descriptions, curated_backbone_concepts = build_backbone(config=config)
    backbone_set = set(backbone_concepts)
    variant_results: dict[str, VariantRunResult] = {}
    evaluations: dict[str, Any] = {}

    for spec in specs:
        variant = _baseline_variant_config(spec)
        if spec["variant_id"] == "rule_pipeline":
            if data_root is None:
                raise ValueError("rule_pipeline baseline requires data_root pointing to the markdown corpus")
            raw_records_by_domain = build_rule_records_by_domain(
                data_root=data_root,
                domain_ids=[domain.domain_id for domain in config.domains],
                role=config.domains[0].role,
            )
            records_by_domain = normalize_records_by_domain(raw_records_by_domain)
            write_rule_records_bundle(run_root / spec["variant_id"] / "rule_evidence", records_by_domain)
            candidates_by_domain = aggregate_schema_candidates(records_by_domain, assume_normalized=True)
            retrievals_by_domain, decisions_by_domain = _build_rule_pipeline_decisions(
                config,
                candidates_by_domain,
                backbone_set,
            )
        elif spec["variant_id"] == "llm_direct_graph":
            records_by_domain = normalize_records_by_domain(load_records_by_domain(config))
            candidates_by_domain = aggregate_schema_candidates(records_by_domain, assume_normalized=True)
            retrievals_by_domain = {
                domain_id: empty_retrievals(candidates)
                for domain_id, candidates in candidates_by_domain.items()
            }
            decisions_by_domain = _build_direct_graph_decisions(candidates_by_domain, backbone_set)
        else:
            raise ValueError(f"unsupported baseline id: {spec['variant_id']}")

        result = _build_result(
            config=config,
            variant=variant,
            records_by_domain=records_by_domain,
            retrievals_by_domain=retrievals_by_domain,
            decisions_by_domain=decisions_by_domain,
            backbone_concepts=backbone_concepts,
            backbone_descriptions=backbone_descriptions,
            curated_backbone_concepts=curated_backbone_concepts,
        )
        variant_results[variant.variant_id] = result
        export_variant_run(
            run_dir=run_root / variant.variant_id,
            result=result,
            write_detailed_working_artifacts=config.runtime.write_detailed_working_artifacts,
            write_jsonl_artifacts=config.runtime.write_jsonl_artifacts,
            write_graphml=config.runtime.write_graphml,
            write_property_graph_jsonl=config.runtime.write_property_graph_jsonl,
            write_graph_db_csv=config.runtime.write_graph_db_csv,
        )

        if ground_truth_dir:
            evaluation = evaluate_variant_run(
                run_root=run_root,
                variant_id=variant.variant_id,
                ground_truth_dir=ground_truth_dir,
            )
            evaluation["variant_metadata"] = {
                key: spec[key]
                for key in (
                    "component",
                    "mode",
                    "preprocessing_source",
                    "attachment_source",
                    "uses_llm_preprocessing",
                    "uses_llm_attachment",
                    "paper_table",
                    "description",
                )
            }
            evaluations[variant.variant_id] = evaluation

    benchmark_result = PipelineBenchmarkResult(
        project_name=config.project_name,
        benchmark_name=f"{config.benchmark_name}_baselines",
        config_path=str(Path(base_config_path).resolve()),
        run_root=str(run_root),
        variant_results=variant_results,
        summary={
            "project_name": config.project_name,
            "benchmark_name": f"{config.benchmark_name}_baselines",
            "generated_at": utc_now(),
            "variants": {
                variant_id: result.construction_summary
                for variant_id, result in variant_results.items()
            },
        },
    )
    export_benchmark_summary(run_root, benchmark_result)
    if config.runtime.save_latest_summary:
        write_latest_summary(run_root, benchmark_result.summary)

    baseline_variant = "llm_direct_graph" if "llm_direct_graph" in evaluations else next(iter(evaluations), "")
    comparison = compare_variant_evaluations(evaluations, baseline_variant=baseline_variant) if evaluations else {}
    report = {
        "run_root": str(run_root),
        "baseline_matrix": specs,
        "summary": benchmark_result.summary,
        "evaluations": evaluations,
        "comparison": comparison,
        "variant_rows": build_variant_summary_rows(evaluations) if evaluations else [],
    }
    (run_root / "baseline_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if evaluations:
        write_ablation_csv(run_root / "baseline_report.csv", report["variant_rows"])
        (run_root / "baseline_comparison.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_comparison_csv(run_root / "baseline_comparison.csv", comparison["deltas_vs_baseline"])

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CrossExtend-KG baseline experiments.")
    parser.add_argument("--config", required=True, help="Base pipeline config path")
    parser.add_argument("--output-dir", required=True, help="Directory to store baseline outputs")
    parser.add_argument("--ground-truth-dir", default=None, help="Optional human gold directory for evaluation")
    parser.add_argument("--data-root", default=None, help="Raw markdown root required for rule_pipeline")
    parser.add_argument("--baselines", nargs="*", default=None, help="Optional subset of baseline ids")
    args = parser.parse_args()

    report = run_baseline_suite(
        base_config_path=args.config,
        output_dir=args.output_dir,
        ground_truth_dir=args.ground_truth_dir,
        baseline_ids=args.baselines,
        data_root=args.data_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
