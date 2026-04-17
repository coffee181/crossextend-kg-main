"""Pipeline package for CrossExtend-KG."""

from .runner import run_pipeline
from .evidence import (
    load_records_by_domain,
    build_evidence_units,
    aggregate_schema_candidates,
)
from .backbone import build_backbone
from .router import retrieve_anchor_rankings, empty_retrievals
from .attachment import decide_attachments_for_domain
from .memory import (
    load_persistent_memory_bank,
    save_temporal_memory_bank,
    retrieve_historical_context,
    build_variant_memory_entries,
    top_historical_parent_anchor,
    # Analysis utilities
    count_memory_entries_by_type,
    filter_entries_by_domain,
    filter_entries_by_label,
    get_unique_parent_anchors,
    summarize_memory_bank,
    # Scoring constants
    MEMORY_HIT_THRESHOLD,
    EMBEDDING_WEIGHT,
    LABEL_MATCH_WEIGHT,
    TOKEN_OVERLAP_WEIGHT,
    DOMAIN_AFFINITY_WEIGHT,
    TIME_DECAY_WEIGHT,
    ANCHOR_SCORE_WEIGHT,
)
from .graph import build_domain_schemas, assemble_domain_graphs
from .artifacts import (
    export_variant_run,
    export_benchmark_summary,
    load_snapshot_state,
    rollback_snapshot,
)
from .utils import (
    utc_now,
    load_text,
    normalize_text,
    json_pretty,
    render_prompt_template,
)

__all__ = [
    # Runner
    "run_pipeline",
    # Evidence
    "load_records_by_domain",
    "build_evidence_units",
    "aggregate_schema_candidates",
    # Backbone
    "build_backbone",
    # Router
    "retrieve_anchor_rankings",
    "empty_retrievals",
    # Attachment
    "decide_attachments_for_domain",
    # Memory
    "load_persistent_memory_bank",
    "save_temporal_memory_bank",
    "retrieve_historical_context",
    "build_variant_memory_entries",
    "top_historical_parent_anchor",
    # Memory analysis
    "count_memory_entries_by_type",
    "filter_entries_by_domain",
    "filter_entries_by_label",
    "get_unique_parent_anchors",
    "summarize_memory_bank",
    # Memory constants
    "MEMORY_HIT_THRESHOLD",
    "EMBEDDING_WEIGHT",
    "LABEL_MATCH_WEIGHT",
    "TOKEN_OVERLAP_WEIGHT",
    "DOMAIN_AFFINITY_WEIGHT",
    "TIME_DECAY_WEIGHT",
    "ANCHOR_SCORE_WEIGHT",
    # Graph
    "build_domain_schemas",
    "assemble_domain_graphs",
    # Artifacts
    "export_variant_run",
    "export_benchmark_summary",
    "load_snapshot_state",
    "rollback_snapshot",
    # Utils
    "utc_now",
    "load_text",
    "normalize_text",
    "json_pretty",
    "render_prompt_template",
]
