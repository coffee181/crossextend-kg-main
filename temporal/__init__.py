"""Optional temporal support for the current CrossExtend-KG mainline.

Provides graph versioning, lifecycle-event detection, and temporal
consistency helpers when snapshot-aware execution is enabled.
"""

from temporal.versioning import TemporalDiff, TemporalGraphStore
from temporal.lifecycle import DeviceLifecycleTracker, LifecycleEvent
from temporal.consistency import compute_temporal_metrics, validate_temporal_consistency

__all__ = [
    "TemporalGraphStore",
    "TemporalDiff",
    "DeviceLifecycleTracker",
    "LifecycleEvent",
    "validate_temporal_consistency",
    "compute_temporal_metrics",
]
