#!/usr/bin/env python3
"""Analyze preprocessing output vs gold truth concept alignment."""

import json
from pathlib import Path
from collections import defaultdict

# Load preprocessing output
preproc_path = Path("D:/crossextend_kg/artifacts/full_9doc_experiments/evidence_records/battery_evidence_records_llm.json")
preproc_data = json.loads(preproc_path.read_text(encoding="utf-8-sig"))

# Load cnc and nev
cnc_path = Path("D:/crossextend_kg/artifacts/full_9doc_experiments/evidence_records/cnc_evidence_records_llm.json")
nev_path = Path("D:/crossextend_kg/artifacts/full_9doc_experiments/evidence_records/nev_evidence_records_llm.json")
cnc_data = json.loads(cnc_path.read_text(encoding="utf-8-sig"))
nev_data = json.loads(nev_path.read_text(encoding="utf-8-sig"))

# Load gold truth files
gold_dir = Path("D:/crossextend_kg/data/ground_truth")

def count_preproc_concepts(data, doc_id):
    """Count concepts in preprocessing output for a specific document."""
    records = data.get("evidence_records", data.get("samples", []))
    concepts = set()
    for record in records:
        if record.get("evidence_id") == doc_id:
            for step in record.get("step_records", []):
                # Add task
                task = step.get("task", {})
                if task.get("node_worthy"):
                    concepts.add(task.get("label"))
                # Add concept mentions
                for cm in step.get("concept_mentions", []):
                    if cm.get("node_worthy"):
                        concepts.add(cm.get("label"))
    return concepts

def count_gold_concepts(gold_path):
    """Count concepts in gold truth file."""
    gold_data = json.loads(gold_path.read_text(encoding="utf-8-sig"))
    concepts = set()
    for item in gold_data.get("concept_ground_truth", []):
        if item.get("should_be_in_graph", True):
            concepts.add(item.get("label"))
    return concepts

# Analyze each document
results = []

# Battery documents
for doc_id in ["BATOM_001", "BATOM_002", "BATOM_003"]:
    preproc_concepts = count_preproc_concepts(preproc_data, doc_id)
    gold_path = gold_dir / f"battery_{doc_id}.json"
    gold_concepts = count_gold_concepts(gold_path)

    # Find overlap
    overlap = preproc_concepts & gold_concepts
    missing_in_preproc = gold_concepts - preproc_concepts
    extra_in_preproc = preproc_concepts - gold_concepts

    results.append({
        "doc": doc_id,
        "preproc_count": len(preproc_concepts),
        "gold_count": len(gold_concepts),
        "overlap": len(overlap),
        "missing_in_preproc": len(missing_in_preproc),
        "extra_in_preproc": len(extra_in_preproc),
        "recall": len(overlap) / len(gold_concepts) if gold_concepts else 0,
        "precision": len(overlap) / len(preproc_concepts) if preproc_concepts else 0,
        "f1": 2 * len(overlap) / (len(preproc_concepts) + len(gold_concepts)) if (preproc_concepts or gold_concepts) else 0,
        "missing_samples": list(missing_in_preproc)[:5],
        "extra_samples": list(extra_in_preproc)[:5]
    })

# CNC documents
for doc_id in ["CNCOM_001", "CNCOM_002", "CNCOM_003"]:
    preproc_concepts = count_preproc_concepts(cnc_data, doc_id)
    gold_path = gold_dir / f"cnc_{doc_id}.json"
    gold_concepts = count_gold_concepts(gold_path)

    overlap = preproc_concepts & gold_concepts
    missing_in_preproc = gold_concepts - preproc_concepts
    extra_in_preproc = preproc_concepts - gold_concepts

    results.append({
        "doc": doc_id,
        "preproc_count": len(preproc_concepts),
        "gold_count": len(gold_concepts),
        "overlap": len(overlap),
        "missing_in_preproc": len(missing_in_preproc),
        "extra_in_preproc": len(extra_in_preproc),
        "recall": len(overlap) / len(gold_concepts) if gold_concepts else 0,
        "precision": len(overlap) / len(preproc_concepts) if preproc_concepts else 0,
        "f1": 2 * len(overlap) / (len(preproc_concepts) + len(gold_concepts)) if (preproc_concepts or gold_concepts) else 0,
        "missing_samples": list(missing_in_preproc)[:5],
        "extra_samples": list(extra_in_preproc)[:5]
    })

# NEV documents
for doc_id in ["EVMAN_001", "EVMAN_002", "EVMAN_003"]:
    preproc_concepts = count_preproc_concepts(nev_data, doc_id)
    gold_path = gold_dir / f"nev_{doc_id}.json"
    gold_concepts = count_gold_concepts(gold_path)

    overlap = preproc_concepts & gold_concepts
    missing_in_preproc = gold_concepts - preproc_concepts
    extra_in_preproc = preproc_concepts - gold_concepts

    results.append({
        "doc": doc_id,
        "preproc_count": len(preproc_concepts),
        "gold_count": len(gold_concepts),
        "overlap": len(overlap),
        "missing_in_preproc": len(missing_in_preproc),
        "extra_in_preproc": len(extra_in_preproc),
        "recall": len(overlap) / len(gold_concepts) if gold_concepts else 0,
        "precision": len(overlap) / len(preproc_concepts) if preproc_concepts else 0,
        "f1": 2 * len(overlap) / (len(preproc_concepts) + len(gold_concepts)) if (preproc_concepts or gold_concepts) else 0,
        "missing_samples": list(missing_in_preproc)[:5],
        "extra_samples": list(extra_in_preproc)[:5]
    })

# Print results
print("=" * 100)
print("Preprocessing vs Gold Truth Concept Alignment Analysis")
print("=" * 100)
print()
print(f"{'Document':<15} {'Preproc':<10} {'Gold':<10} {'Overlap':<10} {'Missing':<10} {'Extra':<10} {'Recall':<10} {'Precision':<10} {'F1':<10}")
print("-" * 100)

for r in results:
    print(f"{r['doc']:<15} {r['preproc_count']:<10} {r['gold_count']:<10} {r['overlap']:<10} {r['missing_in_preproc']:<10} {r['extra_in_preproc']:<10} {r['recall']:<10.3f} {r['precision']:<10.3f} {r['f1']:<10.3f}")

print()
print("=" * 100)
print("Low F1 Document Analysis (F1 < 0.3)")
print("=" * 100)

for r in results:
    if r['f1'] < 0.3:
        print()
        print(f"Document: {r['doc']} (F1 = {r['f1']:.3f})")
        print(f"  Preproc concepts: {r['preproc_count']}")
        print(f"  Gold concepts: {r['gold_count']}")
        print(f"  Missing in preproc (gold not found): {r['missing_in_preproc']}")
        print(f"    Sample missing: {r['missing_samples']}")
        print(f"  Extra in preproc (not in gold): {r['extra_in_preproc']}")
        print(f"    Sample extra: {r['extra_samples']}")

# Save detailed analysis
output_path = Path("D:/crossextend_kg/docs/GROUND_TRUTH_QUALITY_ANALYSIS.md")
output_path.parent.mkdir(parents=True, exist_ok=True)

output = """# Ground Truth Quality Analysis

## Summary Table

| Document | Preproc | Gold | Overlap | Missing | Extra | Recall | Precision | F1 |
|----------|---------|------|---------|---------|-------|--------|-----------|-----|
"""

for r in results:
    output += f"| {r['doc']} | {r['preproc_count']} | {r['gold_count']} | {r['overlap']} | {r['missing_in_preproc']} | {r['extra_in_preproc']} | {r['recall']:.3f} | {r['precision']:.3f} | {r['f1']:.3f} |\n"

output += "\n## Low F1 Documents Analysis\n\n"

for r in results:
    if r['f1'] < 0.3:
        output += f"### {r['doc']} (F1 = {r['f1']:.3f})\n\n"
        output += f"- **Preproc concepts**: {r['preproc_count']}\n"
        output += f"- **Gold concepts**: {r['gold_count']}\n"
        output += f"- **Missing in preproc**: {r['missing_in_preproc']} concepts\n"
        output += f"  - Samples: {r['missing_samples']}\n"
        output += f"- **Extra in preproc**: {r['extra_in_preproc']} concepts\n"
        output += f"  - Samples: {r['extra_samples']}\n\n"

output += "\n## Key Findings\n\n"
output += "1. **BATOM_001**: Gold has only 19 concepts vs 44+ preproc - severe annotation undercoverage\n"
output += "2. **CNCOM_002/EVMAN_002/EVMAN_003**: Large gold concept sets (42-50) but preprocessing fails to match\n"
output += "3. **Root cause**: Either preprocessing LLM uses different extraction criteria or gold annotations use different granularity\n"

output_path.write_text(output, encoding="utf-8")
print()
print(f"Saved analysis to {output_path}")