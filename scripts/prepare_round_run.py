#!/usr/bin/env python3
"""Stage aligned round inputs and materialize round-specific configs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

from crossextend_kg.experiments.rounds import prepare_round_workspace  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a round workspace with aligned inputs and configs.")
    parser.add_argument("--round-dir", required=True, help="Round artifact directory")
    parser.add_argument("--doc-ids", nargs="+", required=True, help="Document ids to stage, e.g. BATOM_002 CNCOM_002")
    parser.add_argument("--base-preprocess-config", required=True, help="Base preprocessing config path")
    parser.add_argument("--base-pipeline-config", required=True, help="Base pipeline config path")
    parser.add_argument("--benchmark-name", required=True, help="Benchmark name for the round pipeline config")
    parser.add_argument("--run-prefix", required=True, help="Run prefix for the round pipeline config")
    parser.add_argument("--llm-temperature", type=float, default=0.0, help="LLM temperature for preprocessing and attachment")
    parser.add_argument("--no-detailed-working", action="store_true", help="Disable detailed working artifacts")
    parser.add_argument("--write-jsonl-artifacts", action="store_true", help="Enable JSONL working artifacts")
    parser.add_argument("--write-graph-db-csv", action="store_true", help="Enable graph DB CSV exports")
    parser.add_argument("--write-property-graph-jsonl", action="store_true", help="Enable property graph JSONL exports")
    args = parser.parse_args()

    manifest = prepare_round_workspace(
        round_dir=args.round_dir,
        doc_ids=args.doc_ids,
        base_preprocess_config_path=args.base_preprocess_config,
        base_pipeline_config_path=args.base_pipeline_config,
        benchmark_name=args.benchmark_name,
        run_prefix=args.run_prefix,
        llm_temperature=args.llm_temperature,
        write_detailed_working_artifacts=not args.no_detailed_working,
        write_jsonl_artifacts=args.write_jsonl_artifacts,
        write_graph_db_csv=args.write_graph_db_csv,
        write_property_graph_jsonl=args.write_property_graph_jsonl,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
