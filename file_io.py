#!/usr/bin/env python3
"""I/O helpers for CrossExtend-KG artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from crossextend_kg.models import EvidenceRecord
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import EvidenceRecord


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def write_jsonl(path: str | Path, items: Iterable[Any]) -> None:
    lines: list[str] = []
    for item in items:
        if hasattr(item, "model_dump"):
            payload = item.model_dump(mode="json")
        else:
            payload = item
        lines.append(json.dumps(payload, ensure_ascii=False))
    Path(path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_csv(path: str | Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_evidence_records(path: str | Path) -> list[EvidenceRecord]:
    payload = read_json(path)
    # Support multiple field names: samples, evidence_records, or direct list
    if isinstance(payload, dict):
        if "samples" in payload:
            samples = payload["samples"]
        elif "evidence_records" in payload:
            samples = payload["evidence_records"]
        elif "evidence_id" in payload:
            samples = [payload]
        else:
            raise ValueError(
                f"unsupported evidence record payload in {Path(path)}: "
                "expected a list, a single EvidenceRecord object, or a mapping containing "
                "'samples' or 'evidence_records'"
            )
    else:
        samples = payload
    return [EvidenceRecord.model_validate(item) for item in samples]

