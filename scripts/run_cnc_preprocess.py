#!/usr/bin/env python3
"""Run CNC-only preprocessing with v4-pro model."""
import time, sys, os, json, shutil
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ["PYTHONUNBUFFERED"] = "1"

from preprocessing.processor import load_preprocessing_config, run_preprocessing
from preprocessing.models import PreprocessingConfig

# Backup existing file
ev_path = Path("data/evidence_records/evidence_records_llm.json")
if ev_path.exists():
    backup = ev_path.with_suffix(".json.bak")
    shutil.copy2(ev_path, backup)
    print(f"Backed up to {backup}", flush=True)

# Load config and restrict to CNC only
config = load_preprocessing_config("config/persistent/preprocessing.deepseek.yaml")
config = PreprocessingConfig.model_validate({
    **config.model_dump(),
    "domain_ids": ["cnc"],
    "output_path": str(ev_path.parent / "cnc_evidence_records_llm.json"),
})

print(f"Model: {config.llm.model}", flush=True)
print(f"Domains: {config.domain_ids}", flush=True)
print(f"Output: {config.output_path}", flush=True)
print(flush=True)

t0 = time.time()
result = run_preprocessing(config)
elapsed = time.time() - t0

print(f"\n===== CNC PREPROCESSING COMPLETE =====", flush=True)
print(f"Docs: {result.successful_docs}, Failed: {result.failed_docs}", flush=True)
print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min, {elapsed/result.successful_docs:.0f}s/doc)" if result.successful_docs else "", flush=True)
for domain, stats in result.domain_stats.items():
    print(f"  {domain}: {stats}", flush=True)
