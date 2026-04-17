#!/usr/bin/env python3
"""
故障传播路径可视化工具
用于展示知识图谱中捕获的故障传播链

用法:
    python visualize_propagation.py --domain cnc --family propagation
    python visualize_propagation.py --domain nev --chain-depth 3
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def load_graph(graph_path: str) -> dict:
    """Load final_graph.json"""
    with open(graph_path) as f:
        return json.load(f)


def extract_propagation_chains(edges: list, family: str = "propagation") -> dict:
    """
    Extract propagation chains from edges.
    Returns: {start_node: [(next_node, relation_label), ...]}
    """
    family_edges = [e for e in edges if e["family"] == family]
    chains = defaultdict(list)
    for e in family_edges:
        chains[e["head"]].append((e["tail"], e["label"]))
    return chains


def find_multi_hop_chains(edges: list, family: str = "propagation", min_depth: int = 3) -> list:
    """
    Find multi-hop chains (A → B → C → ...).
    Returns list of chains with depth >= min_depth.
    """
    family_edges = [e for e in edges if e["family"] == family]

    # Build adjacency
    adj = defaultdict(list)
    for e in family_edges:
        adj[e["head"]].append((e["tail"], e["label"]))

    # Find start nodes (not tail of any edge)
    all_tails = set(e["tail"] for e in family_edges)
    all_heads = set(e["head"] for e in family_edges)
    start_nodes = all_heads - all_tails

    # DFS to find chains
    chains = []

    def dfs(node: str, path: list, labels: list):
        if len(path) >= min_depth:
            chains.append((path, labels))
        if len(path) > 5:  # limit depth
            return
        for next_node, label in adj.get(node, []):
            dfs(next_node, path + [next_node], labels + [label])

    for start in start_nodes:
        dfs(start, [start], [])

    return chains


def print_ascii_chain(chain: list, labels: list):
    """Print chain in ASCII tree format"""
    for i, node in enumerate(chain[:-1]):
        prefix = "    " if i > 0 else ""
        connector = "└── " if i == len(chain) - 2 else "├── "
        print(f"{prefix}{node}")
        print(f"{prefix}    {connector}[{labels[i]}] → {chain[i+1]}")


def generate_graphviz_dot(chains: list, output_path: str, title: str = "Propagation Chains"):
    """Generate Graphviz DOT file for visualization"""
    dot_content = f'''digraph "{title}" {{
  rankdir=TB;
  node [shape=box, style="rounded,filled", fillcolor="lightblue"];
  edge [color="red", fontcolor="darkred"];

'''

    for path, labels in chains:
        for i in range(len(path) - 1):
            dot_content += f'  "{path[i]}" -> "{path[i+1]}" [label="{labels[i]}"];\n'

    dot_content += "}\n"

    with open(output_path, "w") as f:
        f.write(dot_content)

    print(f"Graphviz DOT file saved to: {output_path}")
    print("To render: dot -Tpng {output_path} -o propagation.png")


def main():
    parser = argparse.ArgumentParser(description="Visualize propagation chains from KG")
    parser.add_argument("--domain", default="cnc", help="Domain ID (cnc, nev, battery)")
    parser.add_argument("--family", default="propagation", help="Relation family")
    parser.add_argument("--chain-depth", type=int, default=3, help="Minimum chain depth")
    parser.add_argument("--output-dot", help="Output Graphviz DOT file path")
    parser.add_argument("--artifact-root", default="../../artifacts/persistent_run-20260414T185408Z/full_llm/working")
    args = parser.parse_args()

    # Load graph
    graph_path = Path(args.artifact_root) / args.domain / "final_graph.json"
    if not graph_path.exists():
        print(f"Error: Graph file not found: {graph_path}")
        return

    graph = load_graph(str(graph_path))
    edges = graph["edges"]

    print(f"\n=== {args.domain} 知识图谱故障传播路径分析 ===")
    print(f"总边数: {len(edges)}")

    # Family statistics
    family_counts = defaultdict(int)
    for e in edges:
        family_counts[e["family"]] += 1

    print(f"\n关系族分布:")
    for f, c in sorted(family_counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {c}")

    # Find multi-hop chains
    chains = find_multi_hop_chains(edges, args.family, args.chain_depth)

    print(f"\n=== 多级传播链（深度 >= {args.chain_depth}）===")
    print(f"发现 {len(chains)} 条链")

    for i, (path, labels) in enumerate(chains, 1):
        print(f"\n链 {i} (长度 {len(path)}):")
        print_ascii_chain(path, labels)

    # Generate Graphviz if requested
    if args.output_dot:
        generate_graphviz_dot(chains, args.output_dot, f"{args.domain} Propagation Chains")


if __name__ == "__main__":
    main()