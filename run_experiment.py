#!/usr/bin/env python3
"""Run experiment using direct imports."""

import sys
import os

# This is the key: set the project root as the package root
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now all relative imports will work because Python sees project_root as the package root
# But we need to import using the module names directly (not crossextend_kg.xxx)

from pipeline.runner import run_pipeline
try:
    from crossextend_kg.config import load_pipeline_config
except ImportError:  # pragma: no cover - direct script execution fallback
    from config import load_pipeline_config

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/persistent/pipeline.deepseek.yaml"
    print(f"Running experiment with config: {config_path}")
    print(f"Project root: {project_root}")

    # Load config first to verify
    config = load_pipeline_config(config_path)
    print(f"Project: {config.project_name}")
    print(f"Domains: {[d.domain_id for d in config.domains]}")
    print(f"Variants: {[v.variant_id for v in config.variants]}")

    # Run pipeline
    result = run_pipeline(config_path)

    print(f"\n{'='*50}")
    print("Experiment completed!")
    print(f"{'='*50}")
    print(f"Variants: {list(result.variant_results.keys())}")
    for variant_id, variant_result in result.variant_results.items():
        print(f"\n{variant_id}:")
        for domain_id, graph in variant_result.domain_graphs.items():
            print(f"  {domain_id}: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
