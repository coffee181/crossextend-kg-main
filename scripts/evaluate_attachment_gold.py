#!/usr/bin/env python3
"""Evaluate attachment decisions against attachment_gold.v1 files."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def normalize_label(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    tokens: list[str] = []
    for token in text.split():
        if len(token) > 3 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 3 and token.endswith("es") and not token.endswith(("ss", "us")):
            token = token[:-2]
        elif len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us")):
            token = token[:-1]
        tokens.append(token)
    return " ".join(tokens)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_record_ids(paths: list[Path]) -> set[str]:
    ids: set[str] = set()
    for path in paths:
        payload = read_json(path)
        records = payload.get("evidence_records", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("evidence_id"), str):
                ids.add(record["evidence_id"])
    return ids


def evaluate_variant(run_dir: Path, variant_id: str, gold_files: list[Path]) -> dict[str, Any]:
    variant_dir = run_dir / variant_id
    totals = {
        "gold": 0,
        "predicted_accepted": 0,
        "matched": 0,
        "correct_anchor": 0,
        "wrong_anchor": 0,
        "missing": 0,
        "extra_predicted": 0,
    }
    per_domain: dict[str, dict[str, Any]] = {}
    wrong_examples: list[dict[str, str]] = []

    for gold_file in gold_files:
        gold_payload = read_json(gold_file)
        domain_id = gold_payload["domain"]
        gold_items = [item for item in gold_payload["gold_attachments"] if item.get("accept", True)]
        gold_by_label = {normalize_label(item["label"]): item for item in gold_items}

        decisions = read_json(variant_dir / "working" / domain_id / "attachment_decisions.json")
        predictions = {
            normalize_label(item["label"]): item
            for item in decisions.values()
            if item.get("admit_as_node")
        }

        domain_stats = {
            "gold": len(gold_by_label),
            "predicted_accepted": len(predictions),
            "matched": 0,
            "correct_anchor": 0,
            "wrong_anchor": 0,
            "missing": 0,
            "extra_predicted": 0,
        }
        for label_key, gold_item in gold_by_label.items():
            if label_key not in predictions:
                domain_stats["missing"] += 1
                continue
            domain_stats["matched"] += 1
            predicted_anchor = predictions[label_key].get("parent_anchor")
            if predicted_anchor == gold_item["parent_anchor"]:
                domain_stats["correct_anchor"] += 1
            else:
                domain_stats["wrong_anchor"] += 1
                wrong_examples.append(
                    {
                        "domain": domain_id,
                        "label": gold_item["label"],
                        "predicted_anchor": str(predicted_anchor),
                        "gold_anchor": gold_item["parent_anchor"],
                    }
                )
        domain_stats["extra_predicted"] = len(set(predictions) - set(gold_by_label))
        per_domain[domain_id] = domain_stats
        for key in totals:
            totals[key] += domain_stats[key]

    totals["coverage"] = round(totals["matched"] / totals["gold"], 4) if totals["gold"] else 0.0
    totals["anchor_accuracy_on_gold"] = round(totals["correct_anchor"] / totals["gold"], 4) if totals["gold"] else 0.0
    totals["anchor_accuracy_matched"] = (
        round(totals["correct_anchor"] / totals["matched"], 4) if totals["matched"] else 0.0
    )
    return {
        "variant_id": variant_id,
        "totals": totals,
        "per_domain": per_domain,
        "wrong_examples": wrong_examples[:50],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--gold-dir", default="data/ground_truth")
    parser.add_argument("--evidence-records", nargs="*", default=[])
    parser.add_argument("--variants", nargs="+", required=True)
    args = parser.parse_args()

    gold_files = sorted(Path(args.gold_dir).glob("attachment_gold_*.json"))
    if args.evidence_records:
        selected_docs = evidence_record_ids([Path(item) for item in args.evidence_records])
        gold_files = [
            path
            for path in gold_files
            if read_json(path).get("source_doc") in selected_docs
        ]
    payload = {
        "run_dir": str(Path(args.run_dir)),
        "gold_files": [str(path) for path in gold_files],
        "variants": [
            evaluate_variant(Path(args.run_dir), variant_id, gold_files)
            for variant_id in args.variants
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
