"""Temporal consistency validation and metric computation."""

from __future__ import annotations

from typing import Any

try:
    from crossextend_kg.models import (
        LifecycleEvent,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )
except ImportError:
    from models import (
        LifecycleEvent,
        SnapshotManifest,
        SnapshotState,
        TemporalAssertion,
    )


# ---------------------------------------------------------------------------
# Consistency validation
# ---------------------------------------------------------------------------


def validate_temporal_consistency(
    assertions: list[TemporalAssertion],
    snapshots: list[SnapshotManifest],
) -> dict[str, Any]:
    """Run temporal consistency checks and return a results dictionary.

    Checks performed:
    1. No overlapping valid-time intervals for the same object.
    2. Transaction times are monotonically non-decreasing per object.
    3. Supersedes chains have no cycles.
    4. Snapshots have a connected parent chain.
    5. Node/edge counts are monotonically non-decreasing across snapshots.
    """
    checks: dict[str, dict[str, Any]] = {}

    # ---- Check 1: overlapping valid-time intervals ----
    by_object: dict[str, list[TemporalAssertion]] = {}
    for a in assertions:
        by_object.setdefault(a.object_id, []).append(a)

    overlap_violations = 0
    for obj_id, obj_assertions in by_object.items():
        intervals = [
            (a.valid_time_start or "", a.valid_time_end or "9999-12-31T23:59:59Z")
            for a in obj_assertions
        ]
        intervals.sort()
        for i in range(len(intervals) - 1):
            if intervals[i][1] > intervals[i + 1][0]:
                overlap_violations += 1
    checks["no_overlapping_intervals"] = {
        "passed": overlap_violations == 0,
        "violations": overlap_violations,
    }

    # ---- Check 2: transaction-time monotonicity ----
    monotonicity_violations = 0
    for obj_id, obj_assertions in by_object.items():
        sorted_a = sorted(obj_assertions, key=lambda a: a.assertion_id)
        for i in range(len(sorted_a) - 1):
            if sorted_a[i].transaction_time > sorted_a[i + 1].transaction_time:
                monotonicity_violations += 1
    checks["transaction_time_monotonic"] = {
        "passed": monotonicity_violations == 0,
        "violations": monotonicity_violations,
    }

    # ---- Check 3: supersedes chain acyclicity ----
    supersedes_map: dict[str, str] = {}
    for a in assertions:
        if a.supersedes:
            supersedes_map[a.assertion_id] = a.supersedes
    cycle_found = False
    for start in supersedes_map:
        visited: set[str] = set()
        current: str | None = start
        while current and current in supersedes_map:
            if current in visited:
                cycle_found = True
                break
            visited.add(current)
            current = supersedes_map.get(current)
        if cycle_found:
            break
    checks["supersedes_acyclic"] = {"passed": not cycle_found}

    # ---- Check 4: snapshot parent chain ----
    snapshot_ids = {s.snapshot_id for s in snapshots}
    orphan_count = 0
    for s in snapshots:
        if s.parent_snapshot_id and s.parent_snapshot_id not in snapshot_ids:
            orphan_count += 1
    checks["snapshot_parent_chain"] = {
        "passed": orphan_count == 0,
        "orphans": orphan_count,
    }

    # ---- Check 5: monotonic node/edge counts ----
    sorted_snapshots = sorted(snapshots, key=lambda s: s.created_at)
    non_monotonic = 0
    for i in range(len(sorted_snapshots) - 1):
        if sorted_snapshots[i + 1].node_count < sorted_snapshots[i].node_count:
            non_monotonic += 1
        if sorted_snapshots[i + 1].edge_count < sorted_snapshots[i].edge_count:
            non_monotonic += 1
    checks["monotonic_counts"] = {
        "passed": non_monotonic == 0,
        "violations": non_monotonic,
    }

    total_checks = len(checks)
    passed_checks = sum(1 for c in checks.values() if c["passed"])

    return {
        "temporal_consistency_score": round(passed_checks / total_checks, 4) if total_checks else 1.0,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "details": checks,
    }


# ---------------------------------------------------------------------------
# Temporal metrics
# ---------------------------------------------------------------------------


def compute_temporal_metrics(
    assertions: list[TemporalAssertion],
    snapshots: list[SnapshotManifest],
    snapshot_states: list[SnapshotState],
    lifecycle_events: list[LifecycleEvent],
    gold_lifecycle_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute temporal evaluation metrics.

    Returns:
        temporal_consistency_score: ratio of passed consistency checks
        lifecycle_event_coverage: recall of gold lifecycle events
        historical_query_accuracy: placeholder (requires query ground truth)
        update_monotonicity: 1.0 if node/edge counts never decrease
        knowledge_drift_rate: fraction of assertions that supersede previous ones
    """
    # Consistency
    consistency = validate_temporal_consistency(assertions, snapshots)
    tcs = consistency["temporal_consistency_score"]

    # Lifecycle event coverage (LEC)
    lec = 0.0
    if gold_lifecycle_events:
        gold_set = {
            (str(g.get("object_id", "")), str(g.get("event_type", "")))
            for g in gold_lifecycle_events
        }
        pred_set = {(e.object_id, e.event_type) for e in lifecycle_events}
        tp = len(gold_set & pred_set)
        lec = round(tp / len(gold_set), 4) if gold_set else 0.0

    # Historical query accuracy (HQA) — placeholder
    hqa = 1.0

    # Update monotonicity (UM)
    sorted_snapshots = sorted(snapshots, key=lambda s: s.created_at)
    monotonic = True
    for i in range(len(sorted_snapshots) - 1):
        if (
            sorted_snapshots[i + 1].node_count < sorted_snapshots[i].node_count
            or sorted_snapshots[i + 1].edge_count < sorted_snapshots[i].edge_count
        ):
            monotonic = False
            break
    um = 1.0 if monotonic else 0.0

    # Knowledge drift rate (KDR)
    total_assertions = len(assertions)
    superseding = sum(1 for a in assertions if a.supersedes)
    kdr = round(superseding / total_assertions, 4) if total_assertions else 0.0

    return {
        "temporal_consistency_score": tcs,
        "lifecycle_event_coverage": lec,
        "historical_query_accuracy": hqa,
        "update_monotonicity": um,
        "knowledge_drift_rate": kdr,
    }
