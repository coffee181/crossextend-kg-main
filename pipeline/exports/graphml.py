#!/usr/bin/env python3
"""GraphML export for CrossExtend-KG domain graphs.

This module provides GraphML format export for knowledge graphs,
enabling visualization with tools like Gephi, yEd, and NetworkX.

GraphML Format:
    - Node IDs: {domain_id}::node::{label}
    - Edge IDs: {domain_id}::edge::{edge_id}
    - Attributes: label, node_type, parent_anchor, family, provenance_evidence_ids

Usage:
    from pipeline.exports.graphml import export_domain_graphml

    export_domain_graphml(domain_graph, root, domain_id)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ...io import ensure_dir
from ...models import DomainGraphArtifacts, GraphEdge, GraphNode


def build_node_id_from_label(domain_id: str, label: str) -> str:
    """Build a unique node ID from domain and label.

    Args:
        domain_id: Domain identifier (e.g., "battery")
        label: Node label (e.g., "coolant level")

    Returns:
        Unique node ID (e.g., "battery::node::coolant level")
    """
    return f"{domain_id}::node::{label}"


def serialize_list_property(values: list[str]) -> str:
    """Serialize list property to pipe-separated string.

    Args:
        values: List of string values

    Returns:
        Pipe-separated string (e.g., "BATOM_001|BATOM_002")
    """
    return "|".join(str(v) for v in values) if values else ""


def _add_graphml_keys(graphml: ET.Element) -> None:
    """Add standard GraphML attribute keys.

    Args:
        graphml: Root GraphML element
    """
    # Node attributes
    node_keys = [
        ("label", "string"),
        ("node_type", "string"),
        ("parent_anchor", "string"),
        ("surface_form", "string"),
        ("provenance_evidence_ids", "string"),
    ]
    for attr_name, attr_type in node_keys:
        key = ET.SubElement(graphml, "key")
        key.set("id", f"d_{attr_name}")
        key.set("for", "node")
        key.set("attr.name", attr_name)
        key.set("attr.type", attr_type)

    # Edge attributes
    edge_keys = [
        ("label", "string"),
        ("family", "string"),
        ("provenance_evidence_ids", "string"),
    ]
    for attr_name, attr_type in edge_keys:
        key = ET.SubElement(graphml, "key")
        key.set("id", f"d_{attr_name}")
        key.set("for", "edge")
        key.set("attr.name", attr_name)
        key.set("attr.type", attr_type)


def _add_node_element(graph: ET.Element, node: GraphNode, domain_id: str) -> None:
    """Add a GraphML node element.

    Args:
        graph: Graph element
        node: GraphNode to add
        domain_id: Domain identifier
    """
    node_id = build_node_id_from_label(domain_id, node.label)

    node_elem = ET.SubElement(graph, "node")
    node_elem.set("id", node_id)

    # Add node data elements
    data_attrs = {
        "label": node.label,
        "node_type": node.node_type,
        "parent_anchor": node.parent_anchor or "",
        "surface_form": node.surface_form or "",
        "provenance_evidence_ids": serialize_list_property(node.provenance_evidence_ids),
    }
    for attr_name, attr_value in data_attrs.items():
        if attr_value:
            data = ET.SubElement(node_elem, "data")
            data.set("key", f"d_{attr_name}")
            data.text = attr_value


def _add_edge_element(graph: ET.Element, edge: GraphEdge, domain_id: str) -> None:
    """Add a GraphML edge element.

    Args:
        graph: Graph element
        edge: GraphEdge to add
        domain_id: Domain identifier
    """
    source = build_node_id_from_label(domain_id, edge.head)
    target = build_node_id_from_label(domain_id, edge.tail)
    edge_id = f"{domain_id}::edge::{edge.edge_id}"

    edge_elem = ET.SubElement(graph, "edge")
    edge_elem.set("id", edge_id)
    edge_elem.set("source", source)
    edge_elem.set("target", target)

    # Add edge data elements
    data_attrs = {
        "label": edge.label,
        "family": edge.family,
        "provenance_evidence_ids": serialize_list_property(edge.provenance_evidence_ids),
    }
    for attr_name, attr_value in data_attrs.items():
        if attr_value:
            data = ET.SubElement(edge_elem, "data")
            data.set("key", f"d_{attr_name}")
            data.text = attr_value


def export_graphml(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    path: Path,
    domain_id: str,
) -> None:
    """Export domain graph to GraphML format.

    Args:
        nodes: List of GraphNode objects
        edges: List of GraphEdge objects
        path: Output file path
        domain_id: Domain identifier for node ID construction
    """
    # Build GraphML document
    graphml = ET.Element("graphml")
    graphml.set("xmlns", "http://graphml.graphdrawing.org/xmlns")

    # Add attribute keys
    _add_graphml_keys(graphml)

    # Add graph element
    graph = ET.SubElement(graphml, "graph")
    graph.set("id", "G")
    graph.set("edgedefault", "directed")

    # Add nodes
    for node in nodes:
        _add_node_element(graph, node, domain_id)

    # Add edges
    for edge in edges:
        _add_edge_element(graph, edge, domain_id)

    # Write to file
    ensure_dir(path.parent)
    tree = ET.ElementTree(graphml)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def export_domain_graphml(
    domain_graph: DomainGraphArtifacts,
    root: Path,
    domain_id: str,
) -> None:
    """Export a domain graph to GraphML.

    Creates a GraphML file in the exports/graphml directory.

    Args:
        domain_graph: DomainGraphArtifacts containing nodes and edges
        root: Root directory for exports (e.g., working/{domain}/exports)
        domain_id: Domain identifier
    """
    graphml_root = ensure_dir(root / "exports" / "graphml")
    output_path = graphml_root / f"{domain_id}_graph.graphml"

    export_graphml(
        nodes=domain_graph.nodes,
        edges=domain_graph.edges,
        path=output_path,
        domain_id=domain_id,
    )


def export_all_domain_graphml(
    domain_graphs: dict[str, DomainGraphArtifacts],
    working_root: Path,
) -> None:
    """Export all domain graphs to GraphML.

    Args:
        domain_graphs: Dict mapping domain_id to DomainGraphArtifacts
        working_root: Working directory root (e.g., artifacts/{run}/working)
    """
    for domain_id, graph in domain_graphs.items():
        domain_root = working_root / domain_id
        export_domain_graphml(graph, domain_root, domain_id)