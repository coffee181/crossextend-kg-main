#!/usr/bin/env python3
"""Markdown parser for industrial documents."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import DocumentInput


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
    doc_type: str = "fault_case"
) -> DocumentInput:
    """Parse a single markdown file into DocumentInput.

    Supports document types:
    - fault_case: Equipment failure reports
    - product_intro: Product specifications and introductions
    - maintenance_log: Maintenance activity records
    - sop: Standard operating procedures

    Args:
        file_path: Path to markdown file
        domain_id: Target domain identifier
        role: "target"
        doc_type: Document type classification

    Returns:
        DocumentInput ready for extraction
    """
    content = file_path.read_text(encoding="utf-8")

    # Extract title from first # heading or filename
    title = extract_title(content, file_path)

    # Generate document ID from filename
    doc_id = generate_doc_id(file_path)

    # Extract timestamp if present in document
    timestamp = extract_timestamp(content)

    # Extract metadata from frontmatter or header
    metadata = extract_metadata(content)

    return DocumentInput(
        doc_id=doc_id,
        doc_type=doc_type,
        domain_id=domain_id,
        role=role,
        title=title,
        content=content,
        metadata=metadata,
        timestamp=timestamp
    )


def parse_markdown_directory(
    dir_path: Path,
    domain_id: str,
    role: str,
    doc_type: str = "fault_case",
    file_pattern: str = "*.md"
) -> list[DocumentInput]:
    """Parse all markdown files in a directory.

    Args:
        dir_path: Directory containing markdown files
        domain_id: Target domain identifier
        role: "target"
        doc_type: Document type classification
        file_pattern: Glob pattern for file filtering

    Returns:
        List of DocumentInput objects
    """
    documents = []

    for file_path in sorted(dir_path.glob(file_pattern)):
        if file_path.is_file():
            doc = parse_markdown_file(file_path, domain_id, role, doc_type)
            documents.append(doc)

    return documents


def parse_domain_directory(
    domain_path: Path,
    domain_id: str,
    role: str,
    file_pattern: str = "*.md"
) -> dict[str, list[DocumentInput]]:
    """Parse a domain directory with products/ and fault_cases/ subdirs.

    Expected structure:
        domain_path/
        ├── products/*.md
        └── fault_cases/*.md

    Args:
        domain_path: Path to domain directory (e.g., data/battery)
        domain_id: Domain identifier (e.g., "battery")
        role: "target"
        file_pattern: Glob pattern for file filtering

    Returns:
        Dict mapping doc_type to list of DocumentInput
        {"product_intro": [...], "fault_case": [...]}
    """
    result: dict[str, list[DocumentInput]] = {
        "product_intro": [],
        "fault_case": []
    }

    # Parse products/
    products_dir = domain_path / "products"
    if products_dir.is_dir():
        for file_path in sorted(products_dir.glob(file_pattern)):
            if file_path.is_file():
                doc = parse_markdown_file(file_path, domain_id, role, "product_intro")
                result["product_intro"].append(doc)

    # Parse fault_cases/
    fault_cases_dir = domain_path / "fault_cases"
    if fault_cases_dir.is_dir():
        for file_path in sorted(fault_cases_dir.glob(file_pattern)):
            if file_path.is_file():
                doc = parse_markdown_file(file_path, domain_id, role, "fault_case")
                result["fault_case"].append(doc)

    return result


def parse_multi_domain_directory(
    data_root: Path,
    domain_ids: list[str],
    role: str,
    file_pattern: str = "*.md"
) -> dict[str, dict[str, list[DocumentInput]]]:
    """Parse multiple domain directories under a data root.

    Supports two directory structures:

    Structure A (nested):
        data_root/
        ├── battery/
        │   ├── products/*.md
        │   └── fault_cases/*.md

    Structure B (flat with filename pattern):
        data_root/
        ├── battery/
        │   ├── battery_product_001.md
        │   ├── battery_fault_0001.md
        │   └── ...
        ├── cnc/
        │   ├── cnc_product_001.md
        │   ├── cnc_fault_0001.md
        │   └── ...
        └── nev/
        │   └── ...

    Args:
        data_root: Root data directory (e.g., data/)
        domain_ids: List of domain identifiers (e.g., ["battery", "cnc", "nev"])
        role: "target"
        file_pattern: Glob pattern for file filtering

    Returns:
        Nested dict: {domain_id: {doc_type: [DocumentInput, ...]}}
    """
    result: dict[str, dict[str, list[DocumentInput]]] = {}

    for domain_id in domain_ids:
        domain_path = data_root / domain_id
        if not domain_path.is_dir():
            continue

        result[domain_id] = {
            "product_intro": [],
            "fault_case": []
        }

        # Check for nested structure (products/, fault_cases/)
        products_dir = domain_path / "products"
        fault_cases_dir = domain_path / "fault_cases"

        if products_dir.is_dir() or fault_cases_dir.is_dir():
            # Structure A: nested subdirectories
            if products_dir.is_dir():
                for file_path in sorted(products_dir.glob(file_pattern)):
                    if file_path.is_file():
                        doc = parse_markdown_file(file_path, domain_id, role, "product_intro")
                        result[domain_id]["product_intro"].append(doc)
            if fault_cases_dir.is_dir():
                for file_path in sorted(fault_cases_dir.glob(file_pattern)):
                    if file_path.is_file():
                        doc = parse_markdown_file(file_path, domain_id, role, "fault_case")
                        result[domain_id]["fault_case"].append(doc)
        else:
            # Structure B: flat directory with filename pattern
            for file_path in sorted(domain_path.glob(file_pattern)):
                if not file_path.is_file():
                    continue

                filename = file_path.stem.lower()
                if "fault" in filename:
                    doc_type = "fault_case"
                elif "product" in filename:
                    doc_type = "product_intro"
                else:
                    doc_type = classify_doc_type(file_path.read_text(encoding="utf-8"))

                doc = parse_markdown_file(file_path, domain_id, role, doc_type)
                result[domain_id][doc_type].append(doc)

    return result


def extract_title(content: str, file_path: Path) -> str:
    """Extract title from markdown content or filename."""
    # Try first # heading
    heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()

    # Use filename as fallback
    return file_path.stem.replace("_", " ").replace("-", " ")


def generate_doc_id(file_path: Path) -> str:
    """Generate unique document ID from file path."""
    # Use domain prefix + filename
    filename = file_path.stem
    return f"{filename}"


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

    # Use current time as fallback
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def extract_metadata(content: str) -> dict[str, Any]:
    """Extract metadata from YAML frontmatter or structured headers."""
    metadata = {}

    # Check for YAML frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        # Parse simple YAML-like key: value pairs
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"').strip("'")

    return metadata


def classify_doc_type(content: str) -> str:
    """Auto-classify document type based on content keywords."""
    content_lower = content.lower()

    # Fault case indicators
    fault_keywords = ["故障", "fault", "failure", "异常", "anomaly", "报警", "alarm", "损坏", "damage"]
    if any(kw in content_lower for kw in fault_keywords):
        return "fault_case"

    # Product intro indicators
    product_keywords = ["产品", "product", "规格", "specification", "型号", "model", "参数", "parameter"]
    if any(kw in content_lower for kw in product_keywords):
        return "product_intro"

    # Maintenance log indicators
    maint_keywords = ["维护", "maintenance", "维修", "repair", "保养", "service", "检修", "inspection"]
    if any(kw in content_lower for kw in maint_keywords):
        return "maintenance_log"

    # SOP indicators
    sop_keywords = ["操作规程", "sop", "流程", "procedure", "步骤", "step", "作业", "operation"]
    if any(kw in content_lower for kw in sop_keywords):
        return "sop"

    # Default to fault_case
    return "fault_case"


def normalize_content(content: str) -> str:
    """Normalize markdown content for LLM processing."""
    # Remove excessive whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Remove code blocks (they may confuse LLM)
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)

    # Remove HTML tags
    content = re.sub(r"<[^>]+>", "", content)

    # Normalize headers
    content = re.sub(r"^#{2,6}\s+", "# ", content, flags=re.MULTILINE)

    return content.strip()
