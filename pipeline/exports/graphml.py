#!/usr/bin/env python3
"""GraphML export for CrossExtend-KG domain graphs.

GraphML files are written to a dedicated top-level directory:

    {project_root}/graphml/<mirrored-run-path>/{variant_id}/{domain_id}.graphml
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from crossextend_kg.file_io import ensure_dir
except ImportError:  # pragma: no cover - direct script execution fallback
    from file_io import ensure_dir
try:
    from crossextend_kg.models import DomainGraphArtifacts, GraphEdge, GraphNode
except ImportError:  # pragma: no cover - direct script execution fallback
    from models import DomainGraphArtifacts, GraphEdge, GraphNode


def build_node_id_from_label(domain_id: str, label: str) -> str:
    """Build a legacy node ID from domain and label."""
    return f"{domain_id}::node::{label}"


def serialize_list_property(values: list[str]) -> str:
    """Serialize list properties to a stable pipe-separated string."""
    return "|".join(str(v) for v in values) if values else ""


def _add_graphml_keys(graphml: ET.Element) -> None:
    node_keys = [
        ("label", "string"),
        ("display_label", "string"),
        ("domain_id", "string"),
        ("node_type", "string"),
        ("node_layer", "string"),
        ("parent_anchor", "string"),
        ("surface_form", "string"),
        ("step_id", "string"),
        ("order_index", "int"),
        ("provenance_evidence_ids", "string"),
        ("valid_from", "string"),
        ("valid_to", "string"),
        ("lifecycle_stage", "string"),
    ]
    for attr_name, attr_type in node_keys:
        key = ET.SubElement(graphml, "key")
        key.set("id", f"n_{attr_name}")
        key.set("for", "node")
        key.set("attr.name", attr_name)
        key.set("attr.type", attr_type)

    edge_keys = [
        ("label", "string"),
        ("domain_id", "string"),
        ("family", "string"),
        ("edge_layer", "string"),
        ("workflow_kind", "string"),
        ("head", "string"),
        ("tail", "string"),
        ("provenance_evidence_ids", "string"),
        ("valid_from", "string"),
        ("valid_to", "string"),
    ]
    for attr_name, attr_type in edge_keys:
        key = ET.SubElement(graphml, "key")
        key.set("id", f"e_{attr_name}")
        key.set("for", "edge")
        key.set("attr.name", attr_name)
        key.set("attr.type", attr_type)


def _add_node_element(graph: ET.Element, node: GraphNode) -> None:
    node_elem = ET.SubElement(graph, "node")
    node_elem.set("id", node.node_id)

    data_attrs = {
        "label": node.label,
        "display_label": node.display_label or node.label,
        "domain_id": node.domain_id,
        "node_type": node.node_type,
        "node_layer": node.node_layer,
        "parent_anchor": node.parent_anchor or "",
        "surface_form": node.surface_form or "",
        "step_id": node.step_id or "",
        "order_index": "" if node.order_index is None else str(node.order_index),
        "provenance_evidence_ids": serialize_list_property(node.provenance_evidence_ids),
        "valid_from": node.valid_from or "",
        "valid_to": node.valid_to or "",
        "lifecycle_stage": node.lifecycle_stage or "",
    }
    for attr_name, attr_value in data_attrs.items():
        if attr_value:
            data = ET.SubElement(node_elem, "data")
            data.set("key", f"n_{attr_name}")
            data.text = attr_value


def _build_node_id_lookup(nodes: list[GraphNode]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for node in nodes:
        existing = lookup.get(node.label)
        if existing and existing != node.node_id:
            raise ValueError(f"duplicate node label for GraphML export: {node.label}")
        lookup[node.label] = node.node_id
    return lookup


def _add_edge_element(graph: ET.Element, edge: GraphEdge, node_id_lookup: dict[str, str]) -> None:
    source = node_id_lookup.get(edge.head)
    target = node_id_lookup.get(edge.tail)
    if not source or not target:
        raise ValueError(
            f"edge endpoints missing from node map during GraphML export: "
            f"{edge.edge_id} ({edge.head} -> {edge.tail})"
        )

    edge_elem = ET.SubElement(graph, "edge")
    edge_elem.set("id", edge.edge_id)
    edge_elem.set("source", source)
    edge_elem.set("target", target)

    data_attrs = {
        "label": edge.label,
        "domain_id": edge.domain_id,
        "family": edge.family,
        "edge_layer": edge.edge_layer,
        "workflow_kind": edge.workflow_kind or "",
        "head": edge.head,
        "tail": edge.tail,
        "provenance_evidence_ids": serialize_list_property(edge.provenance_evidence_ids),
        "valid_from": edge.valid_from or "",
        "valid_to": edge.valid_to or "",
    }
    for attr_name, attr_value in data_attrs.items():
        if attr_value:
            data = ET.SubElement(edge_elem, "data")
            data.set("key", f"e_{attr_name}")
            data.text = attr_value


def export_graphml(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    path: Path,
) -> None:
    """Export a domain graph to GraphML format."""
    graphml = ET.Element("graphml")
    graphml.set("xmlns", "http://graphml.graphdrawing.org/xmlns")
    _add_graphml_keys(graphml)

    graph = ET.SubElement(graphml, "graph")
    graph.set("id", "G")
    graph.set("edgedefault", "directed")

    node_id_lookup = _build_node_id_lookup(nodes)
    for node in nodes:
        _add_node_element(graph, node)
    for edge in edges:
        _add_edge_element(graph, edge, node_id_lookup)

    ensure_dir(path.parent)
    tree = ET.ElementTree(graphml)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def export_domain_graphml(
    domain_graph: DomainGraphArtifacts,
    graphml_variant_root: Path,
    domain_id: str,
) -> Path:
    """Export one domain graph to the top-level GraphML directory."""
    output_path = ensure_dir(graphml_variant_root) / f"{domain_id}.graphml"
    export_graphml(
        nodes=domain_graph.nodes,
        edges=domain_graph.edges,
        path=output_path,
    )
    return output_path


def export_all_domain_graphml(
    domain_graphs: dict[str, DomainGraphArtifacts],
    graphml_variant_root: Path,
) -> None:
    """Export all domain graphs for one variant."""
    for domain_id, graph in domain_graphs.items():
        export_domain_graphml(graph, graphml_variant_root, domain_id)
