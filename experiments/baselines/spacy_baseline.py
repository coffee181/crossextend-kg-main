"""Draft-only SpaCy baseline helper.

Extracts entities via SpaCy NER and builds relations from dependency parse
trees without any LLM calls. This module is not wired into the current
paper-facing baseline suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from crossextend_kg.models import (
        AttachmentDecision,
        DomainGraphArtifacts,
        GraphEdge,
        GraphNode,
    )
except ImportError:
    from models import (
        AttachmentDecision,
        DomainGraphArtifacts,
        GraphEdge,
        GraphNode,
    )


BASELINE_SPEC: dict[str, Any] = {
    "variant_id": "spacy_ner_re",
    "description": "SpaCy NER + dependency-parse relation extraction baseline",
    "component": "baseline",
    "mode": "reference",
    "preprocessing_source": "spacy",
    "attachment_source": "rule",
    "uses_llm_preprocessing": False,
    "uses_llm_attachment": False,
    "paper_table": False,
}


def _try_load_spacy(model_name: str = "en_core_web_sm") -> Any:
    """Attempt to load a SpaCy model; return None if unavailable."""
    try:
        import spacy
        return spacy.load(model_name)
    except (ImportError, OSError):
        return None


def extract_entities_and_relations(
    text: str,
    domain_id: str,
    doc_id: str,
    nlp: Any | None = None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Extract entities and relations from raw text using SpaCy.

    Falls back to regex-based extraction if SpaCy is unavailable.
    """
    import re

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_labels: set[str] = set()
    node_counter = 0
    edge_counter = 0

    if nlp is not None:
        doc = nlp(text)
        for ent in doc.ents:
            label = ent.text.strip()
            if label and label not in seen_labels:
                seen_labels.add(label)
                node_counter += 1
                nodes.append(
                    GraphNode(
                        node_id=f"{domain_id}::spacy::node::{node_counter:04d}",
                        label=label,
                        domain_id=domain_id,
                        node_type="adapter_concept",
                        parent_anchor=_map_ner_label(ent.label_),
                        surface_form=ent.text,
                        provenance_evidence_ids=[doc_id],
                    )
                )
        # Extract verb-mediated relations from dependency tree
        for sent in doc.sents:
            for token in sent:
                if token.dep_ in ("nsubj", "nsubjpass") and token.head.pos_ == "VERB":
                    subject = token.text.strip()
                    verb = token.head.lemma_
                    for child in token.head.children:
                        if child.dep_ in ("dobj", "attr", "pobj"):
                            obj = child.text.strip()
                            if subject in seen_labels and obj in seen_labels:
                                edge_counter += 1
                                edges.append(
                                    GraphEdge(
                                        edge_id=f"{domain_id}::spacy::edge::{edge_counter:04d}",
                                        domain_id=domain_id,
                                        label=verb,
                                        family=_infer_family(verb),
                                        head=subject,
                                        tail=obj,
                                        provenance_evidence_ids=[doc_id],
                                    )
                                )
    else:
        # Regex fallback: extract capitalized multi-word terms
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[a-z]+){0,3})\b", text):
            label = match.group(1).strip()
            if label and label not in seen_labels and len(label) > 3:
                seen_labels.add(label)
                node_counter += 1
                nodes.append(
                    GraphNode(
                        node_id=f"{domain_id}::spacy::node::{node_counter:04d}",
                        label=label,
                        domain_id=domain_id,
                        node_type="adapter_concept",
                        parent_anchor="Component",
                        surface_form=label,
                        provenance_evidence_ids=[doc_id],
                    )
                )

    return nodes, edges


def _map_ner_label(spacy_label: str) -> str:
    """Map SpaCy NER label to CrossExtend-KG backbone anchor."""
    mapping = {
        "ORG": "Asset",
        "PRODUCT": "Asset",
        "FAC": "Component",
        "EVENT": "Fault",
        "QUANTITY": "Signal",
    }
    return mapping.get(spacy_label, "Component")


def _infer_family(verb: str) -> str:
    """Infer relation family from verb lemma."""
    verb_lower = verb.lower()
    if verb_lower in ("contain", "include", "comprise", "have"):
        return "structural"
    if verb_lower in ("cause", "lead", "result", "produce"):
        return "propagation"
    if verb_lower in ("indicate", "show", "signal", "suggest"):
        return "communication"
    if verb_lower in ("trigger", "follow", "precede", "require"):
        return "task_dependency"
    return "lifecycle"
