"""Temporal knowledge management for CrossExtend-KG.

Provides bi-temporal graph storage, device lifecycle tracking,
and temporal consistency validation.
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
