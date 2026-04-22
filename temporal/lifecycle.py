"""Device lifecycle tracking and knowledge conflict detection."""

from __future__ import annotations

from typing import Any

try:
    from crossextend_kg.models import (
        GraphEdge,
        LifecycleEvent,
        SnapshotState,
        TemporalAssertion,
    )
except ImportError:
    from models import (
        GraphEdge,
        LifecycleEvent,
        SnapshotState,
        TemporalAssertion,
    )


# Edge labels that imply lifecycle transitions
_LIFECYCLE_EDGE_LABELS: dict[str, str] = {
    "triggers": "creation",
    "supersedes": "replacement",
    "deprecates": "deprecation",
    "replaces": "replacement",
    "causes": "fault_occurrence",
    "maintains": "maintenance",
    "repairs": "maintenance",
    "updates": "update",
    "upgrades": "update",
}


class DeviceLifecycleTracker:
    """Detect and track device lifecycle events from graph edges and temporal assertions."""

    def detect_lifecycle_events(
        self,
        assertions: list[TemporalAssertion],
        edges: list[GraphEdge],
        domain_id: str,
    ) -> list[LifecycleEvent]:
        """Detect lifecycle events from temporal assertions and graph edges.

        Heuristics:
        - First assertion for an object → ``creation``
        - A supersedes link → ``replacement`` or ``update``
        - Edges with lifecycle-family labels → mapped event type
        """
        events: list[LifecycleEvent] = []
        seen_objects: set[str] = set()
        event_counter = 0

        # Sort assertions by transaction time
        sorted_assertions = sorted(assertions, key=lambda a: a.transaction_time)

        for assertion in sorted_assertions:
            obj_id = assertion.object_id
            if obj_id not in seen_objects:
                seen_objects.add(obj_id)
                event_counter += 1
                events.append(
                    LifecycleEvent(
                        event_id=f"{domain_id}::lifecycle::{event_counter:04d}",
                        domain_id=domain_id,
                        event_type="creation",
                        object_id=obj_id,
                        timestamp=assertion.transaction_time,
                        description=f"First observation of {obj_id}",
                    )
                )
            if assertion.supersedes:
                event_counter += 1
                events.append(
                    LifecycleEvent(
                        event_id=f"{domain_id}::lifecycle::{event_counter:04d}",
                        domain_id=domain_id,
                        event_type="update",
                        object_id=obj_id,
                        timestamp=assertion.transaction_time,
                        description=f"{obj_id} supersedes {assertion.supersedes}",
                        superseded_by=None,
                    )
                )

        for edge in edges:
            event_type = _LIFECYCLE_EDGE_LABELS.get(edge.label.lower())
            if event_type is None:
                continue
            event_counter += 1
            events.append(
                LifecycleEvent(
                    event_id=f"{domain_id}::lifecycle::{event_counter:04d}",
                    domain_id=domain_id,
                    event_type=event_type,
                    object_id=edge.head,
                    timestamp=edge.valid_from or "",
                    description=f"{edge.head} --{edge.label}--> {edge.tail}",
                )
            )

        return events

    def build_lifecycle_timeline(
        self,
        events: list[LifecycleEvent],
        object_id: str,
    ) -> list[LifecycleEvent]:
        """Return lifecycle events for *object_id* in chronological order."""
        matching = [e for e in events if e.object_id == object_id]
        matching.sort(key=lambda e: e.timestamp)
        return matching

    def detect_knowledge_conflicts(
        self,
        snapshots: list[SnapshotState],
    ) -> list[dict[str, Any]]:
        """Detect knowledge conflicts across snapshots.

        A conflict occurs when the same node has different parent anchors
        or labels in different snapshots.
        """
        conflicts: list[dict[str, Any]] = []
        node_history: dict[str, list[dict[str, Any]]] = {}

        for snapshot in snapshots:
            for node in snapshot.nodes:
                entry = {
                    "snapshot_id": snapshot.snapshot_id,
                    "label": node.label,
                    "parent_anchor": node.parent_anchor,
                    "node_type": node.node_type,
                }
                node_history.setdefault(node.node_id, []).append(entry)

        for node_id, history in node_history.items():
            if len(history) < 2:
                continue
            prev = history[0]
            for current in history[1:]:
                if current["parent_anchor"] != prev["parent_anchor"]:
                    conflicts.append(
                        {
                            "node_id": node_id,
                            "type": "anchor_change",
                            "from_snapshot": prev["snapshot_id"],
                            "to_snapshot": current["snapshot_id"],
                            "old_anchor": prev["parent_anchor"],
                            "new_anchor": current["parent_anchor"],
                        }
                    )
                prev = current

        return conflicts
