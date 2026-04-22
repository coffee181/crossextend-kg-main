#!/usr/bin/env python3
"""Ablation helpers and CLI for CrossExtend-KG."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

try:
    from crossextend_kg.config import load_structured_config_payload, resolve_pipeline_payload_paths
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import load_structured_config_payload, resolve_pipeline_payload_paths
from pipeline.runner import run_pipeline
from pipeline.utils import utc_now
from experiments.baselines import build_rule_records_by_domain, write_rule_records_bundle
from experiments.comparison import compare_variant_evaluations, write_comparison_csv
from experiments.metrics import evaluate_variant_run, write_ablation_csv
from experiments.ablation.specs import (
    ablation_spec_index,
    ablation_variant_metadata,
    build_default_ablation_variants,
    list_ablation_specs,
)


def _merge_payloads(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            if key in merged:
                merged[key] = _merge_payloads(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    return deepcopy(override)
def _select_comparison_baseline(
    evaluations: dict[str, Any],
    *,
    preferred_variant: str = "full_llm",
) -> str:
    if preferred_variant in evaluations:
        return preferred_variant
    if not evaluations:
        raise ValueError("cannot select comparison baseline from empty evaluations")
    return next(iter(evaluations))


def _load_base_payload(base_config_path: str | Path) -> tuple[Path, dict[str, Any]]:
    path, payload = load_structured_config_payload(base_config_path)
    return path, resolve_pipeline_payload_paths(payload, base_dir=path.parent)


def _infer_rule_data_root(payload: dict[str, Any]) -> Path | None:
    roots: set[Path] = set()
    for domain in payload.get("domains", []):
        if not isinstance(domain, dict):
            continue
        data_path = str(domain.get("data_path", "")).strip()
        if not data_path:
            continue
        parent = Path(data_path).resolve().parent
        if parent.name.startswith("evidence_records"):
            roots.add(parent.parent.resolve())
    if len(roots) == 1:
        return next(iter(roots))
    return None


def _resolve_rule_data_root(payload: dict[str, Any], data_root: str | Path | None) -> Path:
    if data_root:
        return Path(data_root).resolve()
    inferred = _infer_rule_data_root(payload)
    if inferred is not None:
        return inferred
    raise ValueError(
        "rule-based ablation variants require a raw markdown data_root. "
        "Pass --data-root explicitly when selecting no_preprocessing_llm."
    )


def _materialize_variant_payload(
    base_payload: dict[str, Any],
    spec: dict[str, Any],
    suite_root: Path,
    *,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = deepcopy(base_payload)
    base_variants = payload.get("variants", [])
    if not base_variants:
        raise ValueError("config contains no variants")

    variant = deepcopy(base_variants[0])
    variant["variant_id"] = spec["variant_id"]
    variant["description"] = spec["description"]
    variant.update(spec.get("updates", {}))
    payload["variants"] = [variant]
    if spec.get("payload_updates"):
        payload = _merge_payloads(payload, spec["payload_updates"])
    payload["benchmark_name"] = f"{payload.get('benchmark_name', 'run')}_ablation_{spec['variant_id']}"

    runtime = payload.setdefault("runtime", {})
    original_prefix = str(runtime.get("run_prefix", "run")).strip() or "run"
    runtime["artifact_root"] = str((suite_root / "runs").resolve())
    runtime["run_prefix"] = f"{original_prefix}_{spec['variant_id']}"

    if spec.get("preprocessing_source") == "rule":
        resolved_data_root = _resolve_rule_data_root(payload, data_root)
        role_values = {
            str(domain.get("role", "target")).strip() or "target"
            for domain in payload.get("domains", [])
            if isinstance(domain, dict)
        }
        if len(role_values) > 1:
            raise ValueError("rule-based preprocessing ablation currently requires a consistent role across domains")
        role = next(iter(role_values), "target")
        domain_ids = [
            str(domain.get("domain_id", "")).strip()
            for domain in payload.get("domains", [])
            if isinstance(domain, dict) and str(domain.get("domain_id", "")).strip()
        ]
        records_by_domain = build_rule_records_by_domain(resolved_data_root, domain_ids, role=role)
        evidence_paths = write_rule_records_bundle(suite_root / "rule_evidence" / spec["variant_id"], records_by_domain)
        for domain in payload.get("domains", []):
            if not isinstance(domain, dict):
                continue
            domain_id = str(domain.get("domain_id", "")).strip()
            if domain_id not in evidence_paths:
                raise KeyError(f"missing rule-preprocessed evidence path for domain {domain_id}")
            domain["data_path"] = evidence_paths[domain_id]

    return payload


def materialize_ablation_variant_config(
    base_config_path: str | Path,
    suite_root: str | Path,
    spec: dict[str, Any],
    *,
    data_root: str | Path | None = None,
) -> Path:
    _, base_payload = _load_base_payload(base_config_path)
    suite_root = Path(suite_root).resolve()
    suite_root.mkdir(parents=True, exist_ok=True)
    payload = _materialize_variant_payload(
        base_payload,
        spec,
        suite_root,
        data_root=data_root,
    )
    config_dir = suite_root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{spec['variant_id']}.config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_path


def materialize_ablation_config(
    base_config_path: str | Path,
    output_dir: str | Path,
    *,
    include_debug_aliases: bool = False,
) -> Path:
    base_config_path = Path(base_config_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    _, payload = _load_base_payload(base_config_path)
    base_variants = payload.get("variants", [])
    if not base_variants:
        raise ValueError(f"config contains no variants: {base_config_path}")

    payload["benchmark_name"] = f"{payload.get('benchmark_name', 'run')}_ablation"
    payload["variants"] = build_default_ablation_variants(
        base_variants[0],
        include_debug_aliases=include_debug_aliases,
        paper_facing_only=True,
        include_unimplemented=False,
    )

    config_path = output_dir / "ablation.config.json"
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config_path


def run_ablation_experiment(
    base_config_path: str | Path,
    output_dir: str | Path,
    ground_truth_dir: str | Path | None = None,
    variant_ids: list[str] | None = None,
    *,
    include_debug_aliases: bool = False,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    spec_map = ablation_spec_index(include_debug_aliases=include_debug_aliases)
    selected_ids = variant_ids or [
        spec["variant_id"]
        for spec in list_ablation_specs(
            include_debug_aliases=include_debug_aliases,
            paper_facing_only=True,
            include_unimplemented=False,
        )
    ]
    unknown_ids = [variant_id for variant_id in selected_ids if variant_id not in spec_map]
    if unknown_ids:
        raise ValueError(f"unknown ablation variant ids: {unknown_ids}")
    deferred_ids = [variant_id for variant_id in selected_ids if not spec_map[variant_id].get("implemented", True)]
    if deferred_ids:
        raise ValueError(
            "selected ablation variants are deferred and not wired into the current paper-facing pipeline: "
            f"{deferred_ids}"
        )

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    suite_root = output_dir / f"ablation-{utc_now().replace(':', '').replace('-', '')}"
    suite_root.mkdir(parents=True, exist_ok=True)

    variant_runs: dict[str, Any] = {}
    evaluations: dict[str, Any] = {}
    for variant_id in selected_ids:
        spec = spec_map[variant_id]
        config_path = materialize_ablation_variant_config(
            base_config_path,
            suite_root,
            spec,
            data_root=data_root,
        )
        benchmark_result = run_pipeline(str(config_path))
        variant_runs[variant_id] = {
            "config_path": str(config_path),
            "run_root": benchmark_result.run_root,
            "summary": benchmark_result.summary,
        }
        if ground_truth_dir:
            evaluation = evaluate_variant_run(
                run_root=benchmark_result.run_root,
                variant_id=variant_id,
                ground_truth_dir=ground_truth_dir,
            )
            evaluation["variant_metadata"] = ablation_variant_metadata(spec)
            evaluations[variant_id] = evaluation

    comparison = (
        compare_variant_evaluations(
            evaluations,
            baseline_variant=_select_comparison_baseline(evaluations),
        )
        if evaluations
        else {}
    )

    report = {
        "run_root": str(suite_root),
        "ablation_config_paths": {variant_id: item["config_path"] for variant_id, item in variant_runs.items()},
        "variant_runs": variant_runs,
        "ablation_matrix": [
            spec_map[variant_id]
            for variant_id in selected_ids
        ],
        "evaluations": evaluations,
        "comparison": comparison,
    }
    (suite_root / "ablation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if evaluations:
        write_ablation_csv(suite_root / "ablation_report.csv", comparison["variant_rows"])
        (suite_root / "comparison_report.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_comparison_csv(suite_root / "comparison_report.csv", comparison["deltas_vs_baseline"])

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the default ablation suite for CrossExtend-KG.")
    parser.add_argument("--config", required=True, help="Base pipeline config path")
    parser.add_argument("--output-dir", required=True, help="Directory to store ablation config and outputs")
    parser.add_argument("--ground-truth-dir", default=None, help="Optional human gold directory for evaluation")
    parser.add_argument("--variants", nargs="*", default=None, help="Optional subset of ablation variant ids")
    parser.add_argument(
        "--data-root",
        default=None,
        help="Raw markdown root required for rule-preprocessing variants such as no_preprocessing_llm",
    )
    parser.add_argument(
        "--include-debug-aliases",
        action="store_true",
        help="Include debug-only alias variants such as deterministic in the materialized config",
    )
    args = parser.parse_args()

    report = run_ablation_experiment(
        base_config_path=args.config,
        output_dir=args.output_dir,
        ground_truth_dir=args.ground_truth_dir,
        variant_ids=args.variants,
        include_debug_aliases=args.include_debug_aliases,
        data_root=args.data_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0
