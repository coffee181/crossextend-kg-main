#!/usr/bin/env python3
"""Command line interface for CrossExtend-KG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .experiments.metrics import compute_metrics, evaluate_variant_run
    from .logging_config import configure_logging
    from .pipeline.artifacts import load_snapshot_state, rollback_snapshot
    from .pipeline.runner import run_pipeline, run_pipeline_for_domains
    from .preprocessing import run_preprocessing, load_preprocessing_config
except ImportError:  # pragma: no cover - direct repo-root execution fallback
    from experiments.metrics import compute_metrics, evaluate_variant_run
    from logging_config import configure_logging
    from pipeline.artifacts import load_snapshot_state, rollback_snapshot
    from pipeline.runner import run_pipeline, run_pipeline_for_domains
    from preprocessing import run_preprocessing, load_preprocessing_config


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "persistent" / "pipeline.deepseek.yaml"
DEFAULT_PREPROCESSING_CONFIG = Path(__file__).resolve().parent / "config" / "persistent" / "preprocessing.deepseek.yaml"


def _emit_error(command: str | None, config_path: str | None, exc: Exception) -> None:
    payload = {
        "status": "error",
        "command": command,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    if config_path:
        payload["config_path"] = str(Path(config_path).resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crossextend-kg")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run the full CrossExtend-KG pipeline")
    run_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    run_parser.add_argument("--regenerate", action="store_true")
    run_parser.add_argument("--variants", nargs="*", default=None)
    run_parser.add_argument("--domains", nargs="*", default=None)
    run_parser.add_argument("--no-export", action="store_true")

    replay_parser = subparsers.add_parser("replay", help="load one exported snapshot state")
    replay_parser.add_argument("--run-dir", required=True)
    replay_parser.add_argument("--domain", required=True)
    replay_parser.add_argument("--snapshot", required=True)

    rollback_parser = subparsers.add_parser("rollback", help="load the rollback target snapshot state")
    rollback_parser.add_argument("--run-dir", required=True)
    rollback_parser.add_argument("--domain", required=True)
    rollback_parser.add_argument("--snapshot", required=True)

    preprocess_parser = subparsers.add_parser("preprocess", help="convert markdown documents to EvidenceRecords")
    preprocess_parser.add_argument("--config", default=str(DEFAULT_PREPROCESSING_CONFIG))
    preprocess_parser.add_argument("--data-root", default=None, help="override data root directory (e.g., ./data/)")
    preprocess_parser.add_argument("--domain-ids", nargs="*", default=None, help="override domain IDs (e.g., battery cnc nev)")
    preprocess_parser.add_argument("--output-path", default=None, help="override output path")
    preprocess_parser.add_argument("--role", default="target", choices=["target"], help="Domain role (unified construction: all domains are target)")

    evaluate_parser = subparsers.add_parser("evaluate", help="evaluate one graph or one run output against human gold")
    target_group = evaluate_parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--graph", default=None, help="path to one final_graph.json")
    target_group.add_argument("--run-root", default=None, help="path to one benchmark run root")
    evaluate_parser.add_argument("--gold", default=None, help="path to one gold json when evaluating a single graph")
    evaluate_parser.add_argument("--variant", default=None, help="variant id when evaluating a run root")
    evaluate_parser.add_argument("--ground-truth-dir", default=None, help="gold directory for run-level evaluation")
    evaluate_parser.add_argument("--domains", nargs="*", default=None, help="optional domain filter for run-level evaluation")
    evaluate_parser.add_argument("--gold-files", nargs="*", default=None, help="optional gold file filter for run-level evaluation")
    evaluate_parser.add_argument("--output", default=None, help="optional output json path")
    return parser


def main() -> int:
    # Configure logging to stdout
    configure_logging(level=20, stream=sys.stdout)  # INFO level

    parser = _build_parser()
    args = parser.parse_args()
    command = getattr(args, "command", None)
    config_path = getattr(args, "config", None)

    try:
        if args.command == "run":
            if args.domains:
                result = run_pipeline_for_domains(
                    config_path=args.config,
                    domain_ids=args.domains,
                    regenerate=args.regenerate,
                    variant_ids=args.variants,
                    export_artifacts=not args.no_export,
                )
            else:
                result = run_pipeline(
                    config_path=args.config,
                    regenerate=args.regenerate,
                    variant_ids=args.variants,
                    export_artifacts=not args.no_export,
                )
            print(json.dumps(result.summary, ensure_ascii=False, indent=2))
            return 0

        if args.command == "replay":
            state = load_snapshot_state(args.run_dir, args.domain, args.snapshot)
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return 0

        if args.command == "rollback":
            state = rollback_snapshot(args.run_dir, args.domain, args.snapshot)
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return 0

        if args.command == "preprocess":
            config = load_preprocessing_config(args.config)
            # Apply overrides
            if args.data_root:
                config.data_root = args.data_root
            if args.domain_ids:
                config.domain_ids = args.domain_ids
            if args.output_path:
                config.output_path = args.output_path
            if args.role:
                config.role = args.role
            result = run_preprocessing(config, config_path=args.config)
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            return 0

        if args.command == "evaluate":
            if args.graph:
                if not args.gold:
                    raise ValueError("--gold is required when --graph is used")
                payload = compute_metrics(args.gold, args.graph)
            else:
                if not args.variant:
                    raise ValueError("--variant is required when --run-root is used")
                payload = evaluate_variant_run(
                    run_root=args.run_root,
                    variant_id=args.variant,
                    ground_truth_dir=args.ground_truth_dir,
                    domain_ids=args.domains,
                    gold_file_names=args.gold_files,
                )
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
            if args.output:
                Path(args.output).write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
            return 0
    except Exception as exc:
        _emit_error(command, config_path, exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
