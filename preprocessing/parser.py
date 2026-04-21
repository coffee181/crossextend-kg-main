#!/usr/bin/env python3
"""Markdown parser for the active O&M manual corpus."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preprocessing.models import DocumentInput


_TIMESTAMP_PATTERNS: list[tuple[re.Pattern[str], str | None]] = [
    (
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
        ),
        None,
    ),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "%Y-%m-%d"),
    (re.compile(r"\b\d{4}/\d{2}/\d{2}\b"), "%Y/%m/%d"),
    (re.compile(r"\b\d{2}-\d{2}-\d{4}\b"), "%d-%m-%Y"),
]

_OM_FILENAME_PREFIXES = (
    "evman",
    "batom",
    "batteryman",
    "cncom",
    "cncman",
    "nevom",
)
_OM_CONTENT_MARKERS = (
    "time step",
    "o&m sample",
    "| time step |",
    "| t1 |",
    "| t2 |",
    "| t3 |",
    "| t4 |",
    "| t5 |",
    "| t6 |",
    "| t7 |",
    "| t8 |",
    "| t9 |",
)
_DOMAIN_DIRECTORY_CANDIDATES: dict[str, tuple[str, ...]] = {
    "battery": ("battery", "battery_om_manual_en"),
    "cnc": ("cnc", "cnc_om_manual_en"),
    "nev": ("nev", "nev_om_manual_en", "ev_om_manual_en"),
}


def _read_markdown_text(file_path: Path) -> str:
    """Read markdown text while stripping an optional UTF-8 BOM."""
    return file_path.read_text(encoding="utf-8-sig")


def infer_doc_type_from_filename(file_path: Path) -> str | None:
    """Infer the active doc_type from filename conventions when available."""
    filename = file_path.stem.lower()
    if filename.startswith(_OM_FILENAME_PREFIXES) or "_om_" in filename:
        return "om_manual"
    return None


def _normalize_timestamp_match(raw_value: str, parse_format: str | None) -> str:
    if parse_format is None:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    else:
        parsed = datetime.strptime(raw_value, parse_format)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_markdown_file(
    file_path: Path,
    domain_id: str,
    role: str,
    doc_type: str,
) -> DocumentInput:
    """Parse a single markdown O&M file into DocumentInput."""
    content = _read_markdown_text(file_path)
    title = extract_title(content, file_path)
    doc_id = generate_doc_id(file_path)
    timestamp = extract_timestamp(content)
    metadata = extract_metadata(content)

    return DocumentInput(
        doc_id=doc_id,
        doc_type=doc_type,
        domain_id=domain_id,
        role=role,
        title=title,
        content=content,
        metadata=metadata,
        timestamp=timestamp,
    )


def parse_markdown_directory(
    dir_path: Path,
    domain_id: str,
    role: str,
    doc_type: str,
    file_pattern: str = "*.md",
) -> list[DocumentInput]:
    """Parse all markdown files in a directory."""
    documents = []
    for file_path in sorted(dir_path.glob(file_pattern)):
        if file_path.is_file():
            documents.append(parse_markdown_file(file_path, domain_id, role, doc_type))
    return documents


def parse_multi_domain_directory(
    data_root: Path,
    domain_ids: list[str],
    role: str,
    file_pattern: str = "*.md",
) -> dict[str, dict[str, list[DocumentInput]]]:
    """Parse the active three-domain O&M directory layout.

    Expected structure:
        data_root/
        ├── battery/
        │   └── BATOM_001.md
        ├── cnc/
        │   └── CNCOM_001.md
        └── nev/
            └── EVMAN_001.md

    No fallback doc-type routing is allowed. Every markdown file must be
    recognized as `om_manual` either by filename or by O&M content markers.
    """
    result: dict[str, dict[str, list[DocumentInput]]] = {}

    for domain_id in domain_ids:
        domain_path = _resolve_domain_directory(data_root, domain_id)
        if domain_path is None:
            continue

        result[domain_id] = {"om_manual": []}

        for file_path in sorted(domain_path.glob(file_pattern)):
            if not file_path.is_file():
                continue

            content = _read_markdown_text(file_path)
            doc_type = infer_doc_type_from_filename(file_path)
            if doc_type is None:
                try:
                    doc_type = classify_doc_type(content)
                except ValueError as exc:
                    raise ValueError(
                        f"unsupported markdown input for the active O&M pipeline: {file_path}"
                    ) from exc

            doc = parse_markdown_file(file_path, domain_id, role, doc_type)
            result[domain_id][doc_type].append(doc)

    return result


def _resolve_domain_directory(data_root: Path, domain_id: str) -> Path | None:
    candidates = _DOMAIN_DIRECTORY_CANDIDATES.get(domain_id, (domain_id,))
    matches = [candidate for name in candidates if (candidate := data_root / name).is_dir()]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(
            f"ambiguous raw directory layout for domain '{domain_id}' under {data_root}: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


def extract_title(content: str, file_path: Path) -> str:
    """Extract title from markdown content or filename."""
    heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()
    return file_path.stem.replace("_", " ").replace("-", " ")


def generate_doc_id(file_path: Path) -> str:
    """Generate unique document ID from file path."""
    return file_path.stem


def extract_timestamp(content: str) -> str:
    """Extract a document timestamp and normalize it to ISO UTC format."""
    for pattern, parse_format in _TIMESTAMP_PATTERNS:
        match = pattern.search(content)
        if not match:
            continue
        try:
            return _normalize_timestamp_match(match.group(0), parse_format)
        except ValueError:
            continue

    # The current corpus does not carry explicit timestamps, so preprocessing
    # uses the transaction time of ingestion as a stable runtime timestamp.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_metadata(content: str) -> dict[str, Any]:
    """Extract metadata from YAML frontmatter or structured headers."""
    metadata = {}
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"').strip("'")
    return metadata


def classify_doc_type(content: str) -> str:
    """Classify active markdown content for the O&M-only pipeline."""
    content_lower = content.lower()
    if any(marker in content_lower for marker in _OM_CONTENT_MARKERS):
        return "om_manual"
    raise ValueError("document does not match the active om_manual content contract")


def normalize_content(content: str) -> str:
    """Normalize markdown content for LLM processing.

    Markdown tables are preserved because O&M step extraction depends on them.
    """
    content = content.lstrip("\ufeff")
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"<[^>]+>", "", content)
    content = re.sub(r"^#{2,6}\s+", "# ", content, flags=re.MULTILINE)
    return content.strip()
