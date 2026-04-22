"""Bi-temporal graph storage with snapshot query, diff, and rollback."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

try:
    from crossextend_kg.models import (
        GraphEdge,
        GraphNode,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )
except ImportError:
    from models import (
        GraphEdge,
        GraphNode,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )


class TemporalDiff(BaseModel):
    """Differences between two snapshot states."""

    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)
    modified_nodes: list[str] = Field(default_factory=list)


class TemporalGraphStore:
    """Bi-temporal graph store supporting point-in-time queries and rollback.

    Maintains two time dimensions:
      - *valid time*: when a fact is true in the real world
      - *transaction time*: when a fact was recorded in the system
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, SnapshotManifest] = {}
        self._snapshot_states: dict[str, SnapshotState] = {}
        self._assertions: list[TemporalAssertion] = []
        self._snapshot_order: list[str] = []

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_snapshot(
        self,
        manifest: SnapshotManifest,
        state: SnapshotState,
    ) -> None:
        """Ingest a snapshot manifest and its corresponding graph state."""
        self._snapshots[manifest.snapshot_id] = manifest
        self._snapshot_states[manifest.snapshot_id] = state
        if manifest.snapshot_id not in self._snapshot_order:
            self._snapshot_order.append(manifest.snapshot_id)

    def ingest_assertions(self, assertions: list[TemporalAssertion]) -> None:
        self._assertions.extend(assertions)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query_at_time(self, valid_time: str) -> SnapshotState:
        """Return the graph state valid at *valid_time*.

        Iterates snapshots in reverse chronological order and returns the
        first whose ``created_at`` is <= *valid_time*.
        """
        best: SnapshotManifest | None = None
        for sid in reversed(self._snapshot_order):
            manifest = self._snapshots[sid]
            if manifest.created_at <= valid_time:
                if best is None or manifest.created_at > best.created_at:
                    best = manifest
        if best is None:
            return SnapshotState(snapshot_id="__empty__", nodes=[], edges=[])
        return deepcopy(self._snapshot_states[best.snapshot_id])

    def query_transaction_history(self, object_id: str) -> list[TemporalAssertion]:
        """Return all temporal assertions for *object_id*, sorted by transaction time."""
        matching = [a for a in self._assertions if a.object_id == object_id]
        matching.sort(key=lambda a: a.transaction_time)
        return matching

    def list_snapshots(self) -> list[SnapshotManifest]:
        return [self._snapshots[sid] for sid in self._snapshot_order]

    # ------------------------------------------------------------------
    # Diff & rollback
    # ------------------------------------------------------------------

    def diff_snapshots(self, id_a: str, id_b: str) -> TemporalDiff:
        """Compute the difference between two snapshot states."""
        state_a = self._snapshot_states.get(id_a)
        state_b = self._snapshot_states.get(id_b)
        if state_a is None or state_b is None:
            raise KeyError(f"snapshot not found: {id_a if state_a is None else id_b}")

        nodes_a = {n.node_id for n in state_a.nodes}
        nodes_b = {n.node_id for n in state_b.nodes}
        edges_a = {e.edge_id for e in state_a.edges}
        edges_b = {e.edge_id for e in state_b.edges}

        # Detect modified nodes (same id but different label/parent)
        node_map_a = {n.node_id: n for n in state_a.nodes}
        node_map_b = {n.node_id: n for n in state_b.nodes}
        modified = []
        for nid in nodes_a & nodes_b:
            na = node_map_a[nid]
            nb = node_map_b[nid]
            if na.label != nb.label or na.parent_anchor != nb.parent_anchor:
                modified.append(nid)

        return TemporalDiff(
            added_nodes=sorted(nodes_b - nodes_a),
            removed_nodes=sorted(nodes_a - nodes_b),
            added_edges=sorted(edges_b - edges_a),
            removed_edges=sorted(edges_a - edges_b),
            modified_nodes=sorted(modified),
        )

    def rollback_to(self, snapshot_id: str) -> SnapshotState:
        """Return a copy of the graph state at *snapshot_id*."""
        if snapshot_id not in self._snapshot_states:
            raise KeyError(f"snapshot not found: {snapshot_id}")
        return deepcopy(self._snapshot_states[snapshot_id])
