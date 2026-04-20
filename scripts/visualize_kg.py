#!/usr/bin/env python3
"""Render a domain graph JSON artifact as a Mermaid flowchart."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _safe_node_id(label: str) -> str:
    normalized = []
    for char in label:
        if char.isalnum():
            normalized.append(char)
        else:
            normalized.append("_")
    return "".join(normalized).strip("_") or "node"


def build_mermaid(graph: dict) -> str:
    lines = ["flowchart TD"]
    seen_nodes: set[str] = set()

    for node in graph.get("nodes", []):
        mermaid_id = _safe_node_id(node["node_id"])
        if mermaid_id in seen_nodes:
            continue
        seen_nodes.add(mermaid_id)
        label = node.get("label", node["node_id"]).replace('"', '\\"')
        lines.append(f'  {mermaid_id}["{label}"]')

    edge_index = 0
    class_defs: dict[str, str] = {
        "task_dependency": "stroke:#1f6feb,stroke-width:2px,color:#1f2937",
        "communication": "stroke:#0f766e,stroke-width:2px,color:#1f2937",
        "propagation": "stroke:#b91c1c,stroke-width:2px,color:#1f2937",
        "structural": "stroke:#7c3aed,stroke-width:2px,color:#1f2937",
        "lifecycle": "stroke:#c2410c,stroke-width:2px,color:#1f2937",
    }

    for edge in graph.get("edges", []):
        head = _safe_node_id(f"{graph.get('domain_id', 'domain')}::{edge['head']}")
        tail = _safe_node_id(f"{graph.get('domain_id', 'domain')}::{edge['tail']}")
        label = edge.get("label", "").replace('"', '\\"')
        lines.append(f"  {head} -->|{label}| {tail}")
        family = edge.get("family", "")
        if family in class_defs:
            lines.append(f"  linkStyle {edge_index} {class_defs[family]}")
        edge_index += 1

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render final_graph.json as Mermaid")
    parser.add_argument("graph_path", help="Path to final_graph.json")
    parser.add_argument("--output", help="Optional output .mmd path")
    args = parser.parse_args()

    graph_path = Path(args.graph_path)
    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    mermaid = build_mermaid(graph)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(mermaid, encoding="utf-8")
        print(output_path)
        return

    print(mermaid)


if __name__ == "__main__":
    main()
