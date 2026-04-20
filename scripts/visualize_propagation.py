#!/usr/bin/env python3
"""Inspect propagation chains from a final graph artifact."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_graph(graph_path: Path) -> dict:
    return json.loads(graph_path.read_text(encoding="utf-8-sig"))


def extract_family_edges(edges: list[dict], family: str) -> list[dict]:
    return [edge for edge in edges if edge.get("family") == family]


def build_adjacency(edges: list[dict]) -> dict[str, list[tuple[str, str]]]:
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["head"]].append((edge["tail"], edge.get("label", "")))
    return adjacency


def find_multi_hop_chains(edges: list[dict], family: str = "propagation", min_depth: int = 3) -> list[tuple[list[str], list[str]]]:
    family_edges = extract_family_edges(edges, family)
    adjacency = build_adjacency(family_edges)
    all_heads = {edge["head"] for edge in family_edges}
    all_tails = {edge["tail"] for edge in family_edges}
    start_nodes = sorted(all_heads - all_tails) or sorted(all_heads)

    chains: list[tuple[list[str], list[str]]] = []

    def dfs(node: str, path: list[str], labels: list[str]) -> None:
        if len(path) >= min_depth:
            chains.append((path, labels))
        if len(path) >= 6:
            return
        for next_node, label in adjacency.get(node, []):
            if next_node in path:
                continue
            dfs(next_node, path + [next_node], labels + [label])

    for start in start_nodes:
        dfs(start, [start], [])
    return chains


def render_chain(path: list[str], labels: list[str]) -> str:
    parts = [path[0]]
    for label, node in zip(labels, path[1:], strict=False):
        parts.append(f"-[{label}]-> {node}")
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize propagation chains from final_graph.json")
    parser.add_argument("graph_path", help="Path to final_graph.json")
    parser.add_argument("--family", default="propagation", help="Relation family to inspect")
    parser.add_argument("--min-depth", type=int, default=3, help="Minimum chain depth to print")
    args = parser.parse_args()

    graph = load_graph(Path(args.graph_path))
    edges = graph.get("edges", [])
    family_edges = extract_family_edges(edges, args.family)

    print(f"domain={graph.get('domain_id', 'unknown')}")
    print(f"total_edges={len(edges)}")
    print(f"{args.family}_edges={len(family_edges)}")

    chains = find_multi_hop_chains(edges, family=args.family, min_depth=args.min_depth)
    if not chains:
        print("no multi-hop chains found")
        return

    for index, (path, labels) in enumerate(chains, start=1):
        print(f"{index}. {render_chain(path, labels)}")


if __name__ == "__main__":
    main()
