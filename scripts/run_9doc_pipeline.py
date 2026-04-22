#!/usr/bin/env python3
"""Run full 9-document pipeline experiment."""

from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.runner import run_pipeline

def main():
    config_path = Path("config/persistent/pipeline.9doc.yaml")
    print(f"Running pipeline with config: {config_path}")

    result = run_pipeline(
        config_path=str(config_path),
        regenerate=True,
        export_artifacts=True,
    )

    print(f"\nPipeline completed!")
    print(f"Run root: {result.run_root}")
    print(f"Variants: {list(result.variant_results.keys())}")

    for variant_id, variant_result in result.variant_results.items():
        print(f"\n--- Variant: {variant_id} ---")
        for domain_id, graph in variant_result.domain_graphs.items():
            nodes = len(graph.nodes)
            edges = len(graph.edges)
            print(f"  {domain_id}: {nodes} nodes, {edges} edges")

    return result

if __name__ == "__main__":
    main()