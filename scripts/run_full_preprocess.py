#!/usr/bin/env python3
"""Run full 400-document preprocessing with incremental writes."""
import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PYTHONUNBUFFERED"] = "1"

print("Loading config...", flush=True)
from preprocessing.processor import load_preprocessing_config, run_preprocessing

config = load_preprocessing_config("config/persistent/preprocessing.deepseek.yaml")
print(f"Domains: {config.domain_ids}", flush=True)
print(f"Output: {config.output_path}", flush=True)
print(f"Incremental writes: every doc saved to disk", flush=True)

t0 = time.time()
result = run_preprocessing(config)
elapsed = time.time() - t0

print(f"\n===== FULL PREPROCESSING COMPLETE =====", flush=True)
print(f"Total docs: {result.successful_docs}", flush=True)
print(f"Total time: {elapsed:.0f}s ({elapsed/60:.1f} min)", flush=True)
print(f"Avg: {elapsed/result.successful_docs:.0f}s/doc", flush=True)
for domain, stats in result.domain_stats.items():
    print(f"  {domain}: {stats}", flush=True)
