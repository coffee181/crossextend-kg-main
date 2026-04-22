#!/usr/bin/env python3
"""Top-level CrossExtend-KG pipeline runner."""

from __future__ import annotations

import logging
from pathlib import Path

from backends.embeddings import build_embedding_backend
from backends.faiss_cache import build_cached_embedding_backend
from backends.llm import build_llm_backend
try:
    from crossextend_kg.config import load_pipeline_config
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import load_pipeline_config
try:
    from crossextend_kg.models import PipelineBenchmarkResult, VariantRunResult
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import PipelineBenchmarkResult, VariantRunResult
from rules.filtering import filter_attachment_decision
from pipeline.artifacts import export_benchmark_summary, export_variant_run, write_latest_summary
from pipeline.attachment import decide_attachments_for_domain
from pipeline.backbone import build_backbone
from pipeline.evidence import (
    aggregate_schema_candidates,
    build_evidence_units,
    load_records_by_domain,
    normalize_records_by_domain,
)
from pipeline.graph import assemble_domain_graphs, build_domain_schemas
from pipeline.router import empty_retrievals, retrieve_anchor_rankings
from pipeline.utils import utc_now

logger = logging.getLogger(__name__)


def _build_variant_construction_summary(result: VariantRunResult) -> dict[str, object]:
    per_domain: dict[str, dict[str, int]] = {}
    for domain_id, graph in result.domain_graphs.items():
        candidates = result.candidates_by_domain.get(domain_id, [])
        decisions = result.attachment_decisions.get(domain_id, {})
        schema = result.schemas[domain_id]
        accepted_adapter_candidates = 0
        accepted_backbone_reuse = 0
        rejected_candidates = 0
        for candidate in candidates:
            decision = decisions[candidate.candidate_id]
            if not decision.admit_as_node:
                rejected_candidates += 1
            elif decision.route == "reuse_backbone":
                accepted_backbone_reuse += 1
            else:
                accepted_adapter_candidates += 1
        per_domain[domain_id] = {
            "candidate_count": len(candidates),
            "accepted_adapter_candidate_count": accepted_adapter_candidates,
            "accepted_backbone_reuse_count": accepted_backbone_reuse,
            "rejected_candidate_count": rejected_candidates,
            "adapter_concept_count": len(schema.adapter_concepts),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "candidate_triple_count": len(graph.triples),
            "accepted_triple_count": sum(1 for triple in graph.triples if triple.status == "accepted"),
            "rejected_triple_count": sum(1 for triple in graph.triples if triple.status != "accepted"),
            "snapshot_count": len(graph.snapshots),
        }
    return {
        "variant_id": result.variant_id,
        "variant_description": result.variant_description,
        "backbone_size": len(result.backbone_concepts),
        "curated_backbone_concept_count": len(result.curated_backbone_concepts),
        "evidence_unit_count": len(result.evidence_units),
        "per_domain": per_domain,
    }


def _build_summary(config, benchmark_result: dict[str, VariantRunResult]) -> dict:
    variant_summary = {
        variant_id: result.construction_summary
        for variant_id, result in benchmark_result.items()
    }
    return {
        "project_name": config.project_name,
        "benchmark_name": config.benchmark_name,
        "domains": [domain.domain_id for domain in config.all_domains()],
        "generated_at": utc_now(),
        "relation_families": config.relations.relation_families,
        "variants": variant_summary,
    }


def run_pipeline(
    config_path: str,
    regenerate: bool = False,
    variant_ids: list[str] | None = None,
    export_artifacts: bool = True,
) -> PipelineBenchmarkResult:
    logger.info("Loading pipeline config from %s", config_path)
    config = load_pipeline_config(config_path)
    llm_backend = build_llm_backend(config.llm)
    base_embedding_backend = build_embedding_backend(config.embedding)
    embedding_backend = build_cached_embedding_backend(
        base_embedding_backend,
        cache_dir=config.runtime.embedding_cache_dir or None,
        dimension=config.embedding.dimensions,
        model_name=config.embedding.model,
        enabled=config.runtime.enable_embedding_cache,
    )

    required_paths = [Path(domain.data_path) for domain in config.domains]
    missing_paths = [str(p) for p in required_paths if not p.exists()]
    if missing_paths:
        raise FileNotFoundError(
            f"Data paths not found: {missing_paths}. "
            f"Please run preprocessing first: crossextend-kg preprocess --data-root ./data/"
        )

    logger.info("Loading records by domain")
    records_by_domain = normalize_records_by_domain(load_records_by_domain(config))
    evidence_units = build_evidence_units(config, records_by_domain)
    candidates_by_domain = aggregate_schema_candidates(records_by_domain, assume_normalized=True)

    if variant_ids:
        selected = {variant.variant_id for variant in config.variants if variant.variant_id in set(variant_ids)}
        variants = [variant for variant in config.variants if variant.variant_id in selected]
        if not variants:
            raise ValueError(f"none of the requested variants exist in config: {variant_ids}")
    else:
        variants = list(config.variants)

    logger.info("Running %d variants", len(variants))
    run_root = Path(config.runtime.artifact_root) / f"{config.runtime.run_prefix}-{utc_now().replace(':', '').replace('-', '')}"
    variant_results: dict[str, VariantRunResult] = {}
    backbone_concepts, backbone_descriptions, curated_backbone_concepts = build_backbone(config=config)

    for variant in variants:
        logger.info("Processing variant: %s", variant.variant_id)
        backbone_set = set(backbone_concepts)
        retrievals_by_domain: dict[str, dict[str, list]] = {}
        decisions_by_domain = {}

        for domain in config.domains:
            logger.info("Processing domain %s (%d candidates)", domain.domain_id, len(candidates_by_domain.get(domain.domain_id, [])))
            candidates = candidates_by_domain.get(domain.domain_id, [])
            if variant.use_embedding_routing:
                retrievals = retrieve_anchor_rankings(
                    embedding_backend=embedding_backend,
                    backbone_descriptions=backbone_descriptions,
                    candidates=candidates,
                    top_k=config.runtime.retrieval_top_k,
                    domain_id=domain.domain_id,
                )
            else:
                retrievals = empty_retrievals(candidates)
            retrievals_by_domain[domain.domain_id] = retrievals

            decisions = decide_attachments_for_domain(
                config=config,
                variant=variant,
                llm_backend=llm_backend,
                domain_id=domain.domain_id,
                candidates=candidates,
                retrievals=retrievals,
                backbone_descriptions=backbone_descriptions,
                backbone_concepts=backbone_set,
            )
            if variant.use_rule_filter:
                filtered = {}
                for candidate in candidates:
                    filtered[candidate.candidate_id] = filter_attachment_decision(
                        candidate=candidate,
                        decision=decisions[candidate.candidate_id],
                        backbone_concepts=backbone_set,
                        allowed_routes=set(config.relations.allowed_routes),
                        allow_free_form_growth=variant.allow_free_form_growth,
                        min_relation_support_count=config.runtime.min_relation_support_count,
                    )
                decisions = filtered
            decisions_by_domain[domain.domain_id] = decisions

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

        variant_run_dir = run_root / variant.variant_id

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
        variant_results[variant.variant_id] = result

        if export_artifacts and variant.export_artifacts:
            export_variant_run(
                run_dir=variant_run_dir,
                result=result,
                write_detailed_working_artifacts=config.runtime.write_detailed_working_artifacts,
                write_jsonl_artifacts=config.runtime.write_jsonl_artifacts,
                write_graphml=config.runtime.write_graphml,
                write_property_graph_jsonl=config.runtime.write_property_graph_jsonl,
                write_graph_db_csv=config.runtime.write_graph_db_csv,
            )

    summary = _build_summary(config, variant_results)
    benchmark_result = PipelineBenchmarkResult(
        project_name=config.project_name,
        benchmark_name=config.benchmark_name,
        config_path=str(Path(config_path).resolve()),
        run_root=str(run_root),
        variant_results=variant_results,
        summary=summary,
    )

    if export_artifacts:
        export_benchmark_summary(run_root, benchmark_result)
        if config.runtime.save_latest_summary:
            write_latest_summary(config.runtime.artifact_root, summary)
    if hasattr(embedding_backend, "save_all_caches"):
        embedding_backend.save_all_caches()
    return benchmark_result


def run_pipeline_for_domains(
    config_path: str,
    domain_ids: list[str],
    regenerate: bool = False,
    variant_ids: list[str] | None = None,
    export_artifacts: bool = True,
) -> PipelineBenchmarkResult:
    """Convenience wrapper: run pipeline on a subset of domains.

    Loads the config, filters to only the specified domains, and runs
    the pipeline. Useful for LODO and domain-specific experiments.
    """
    config = load_pipeline_config(config_path)
    filtered_config = config.config_for_domains(domain_ids)

    # Write filtered config to a temporary file and run
    import json
    import tempfile
    from pathlib import Path as _Path

    payload = filtered_config.model_dump(mode="json")
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name

    try:
        return run_pipeline(
            config_path=tmp_path,
            regenerate=regenerate,
            variant_ids=variant_ids,
            export_artifacts=export_artifacts,
        )
    finally:
        _Path(tmp_path).unlink(missing_ok=True)
