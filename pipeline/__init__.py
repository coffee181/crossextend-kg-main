"""Pipeline package for CrossExtend-KG."""

from pipeline.runner import run_pipeline
from pipeline.evidence import (
    load_records_by_domain,
    build_evidence_units,
    aggregate_schema_candidates,
)
from pipeline.backbone import build_backbone
from pipeline.router import retrieve_anchor_rankings, empty_retrievals
from pipeline.attachment import decide_attachments_for_domain
from pipeline.graph import build_domain_schemas, assemble_domain_graphs
from pipeline.artifacts import (
    export_variant_run,
    export_benchmark_summary,
    load_snapshot_state,
    rollback_snapshot,
)
from pipeline.utils import (
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
