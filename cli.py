#!/usr/bin/env python3
"""Command line interface for CrossExtend-KG."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .logging_config import configure_logging
    from .pipeline.artifacts import load_snapshot_state, rollback_snapshot
    from .pipeline.runner import run_pipeline, run_pipeline_for_domains
    from .preprocessing import run_preprocessing, load_preprocessing_config
except ImportError:  # pragma: no cover - direct repo-root execution fallback
    from logging_config import configure_logging
    from pipeline.artifacts import load_snapshot_state, rollback_snapshot
    from pipeline.runner import run_pipeline, run_pipeline_for_domains
    from preprocessing import run_preprocessing, load_preprocessing_config


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "persistent" / "pipeline.test3.yaml"
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


def _resolve_replay_target(run_dir: str, domain: str | None, snapshot: str | None) -> tuple[str, str]:
    working_root = Path(run_dir) / "working"
    if domain is None:
        domains = sorted(path.name for path in working_root.iterdir() if path.is_dir())
        if not domains:
            raise FileNotFoundError(f"no domain working directories under {working_root}")
        domain = domains[0]
    if snapshot is None:
        snapshots_root = working_root / domain / "snapshots"
        snapshots = sorted(path.name for path in snapshots_root.iterdir() if path.is_dir())
        if not snapshots:
            raise FileNotFoundError(f"no snapshots under {snapshots_root}")
        snapshot = snapshots[-1]
    return domain, snapshot


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
    replay_parser.add_argument("--domain", default=None)
    replay_parser.add_argument("--snapshot", default=None)

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
    preprocess_parser.add_argument("--max-docs", type=int, default=None, help="limit documents per domain (useful for dry-run testing)")

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
            domain, snapshot = _resolve_replay_target(args.run_dir, args.domain, args.snapshot)
            state = load_snapshot_state(args.run_dir, domain, snapshot)
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
            result = run_preprocessing(config, config_path=args.config, max_docs=args.max_docs)
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:
        _emit_error(command, config_path, exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
