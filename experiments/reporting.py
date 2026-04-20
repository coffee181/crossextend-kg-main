#!/usr/bin/env python3
"""Round-report helpers for iterative optimization runs."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .metrics import read_json


ROUND_TEXT_FILES: tuple[str, ...] = (
    "round_summary.md",
    "change_log.md",
    "dataflow_audit.md",
    "logic_audit.md",
    "code_quality_audit.md",
    "test_report.md",
)

ROUND_SEQUENCE: tuple[str, ...] = ("round_01", "round_02", "round_03", "round_04", "round_05")

ROUND_REPORT_PLAN: dict[str, dict[str, str]] = {
    "round_01": {
        "theme": "Relation denoising and structural contraction on BATOM_002",
        "modules": "preprocessing/processor.py; rules/filtering.py; preprocessing contract tests",
        "dataflow": "Kept the single-document extraction scope fixed, rewrote contextual structural heads into stable parents, and reduced the final graph from 52/37 to 45/28 nodes/edges without adding fallback logic.",
        "architecture": "Separated semantic-safe alias handling from graph filtering so structural cleanup happened in the mainline EvidenceRecord -> candidate -> graph path.",
        "closure": "Alias over-collapse and structural over-expansion closed; semantic boundary errors carried into Round 2.",
    },
    "round_02": {
        "theme": "Semantic boundary refinement for Signal / Fault / State",
        "modules": "config/prompts/preprocessing_extraction_om.txt; rules/filtering.py; semantic regression tests",
        "dataflow": "Tightened upstream extraction semantics and downstream candidate admission so BATOM_002 removed generic extras and kept only 43 concepts / 19 relations in the final graph.",
        "architecture": "Aligned prompt-level concept typing with filtering-time anchor rescue, eliminating the earlier split between semantic hints and final anchor decisions.",
        "closure": "Battery single-doc semantic boundary largely closed; cross-domain robustness moved to Round 3.",
    },
    "round_03": {
        "theme": "Three-domain mini-regression and alignment repair",
        "modules": "round staging / alignment inputs; shared canonicalization path; multi-domain evaluation flow",
        "dataflow": "Introduced explicit CNC content-to-gold alignment so the three-domain regression could be evaluated on semantically matching staged inputs instead of misleading raw filenames.",
        "architecture": "Moved cross-domain correctness from implicit filename assumptions into explicit round-preparation artifacts, keeping the core pipeline shared across battery, CNC, and NEV.",
        "closure": "CNC alignment failure closed; NEV/CNC domain misses remained open for Round 4 full-gold validation.",
    },
    "round_04": {
        "theme": "Full 9-document human-gold validation and ablation",
        "modules": "pipeline/evidence.py; rules/filtering.py; experiments/metrics/core.py; experiments/metrics/evaluate.py; experiments/rounds.py; scripts/prepare_round_run.py; scripts/evaluate_variant_run.py",
        "dataflow": "Scaled the runbook to all 9 gold files, preserved the CNC alignment map, normalized label variants at evidence load time, and reduced full-corpus predictions from 425/195 to 415/179 concepts/relations.",
        "architecture": "Made round execution reproducible with dedicated configs, manifests, metrics diffs, and ablation outputs under artifacts/optimization_rounds/round_04 instead of ad-hoc working-directory state.",
        "closure": "Full-gold execution and ablation closed; BATOM_001 annotation mismatch and weak structural specificity remained open.",
    },
    "round_05": {
        "theme": "Frozen full-corpus replay and stability audit",
        "modules": "round freeze configs; reporting / packaging path; final artifact layout",
        "dataflow": "Restaged the same 9 aligned documents, reran preprocessing from scratch, and replayed the frozen full_llm variant twice; candidate counts stayed fixed while node counts drifted modestly and edges stayed constant.",
        "architecture": "Froze the recommended configuration and artifact structure under round_05, exposing the remaining source of nondeterminism as LLM attachment variance rather than hidden branch logic or fallback behavior.",
        "closure": "Final freeze and repeatability audit closed; residual attachment variance and BATOM_001 gold risk remain open.",
    },
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    Path(path).write_text(text.rstrip() + "\n", encoding="utf-8")


def _round_header(round_id: str, title: str, scope: list[str]) -> str:
    scope_text = ", ".join(scope) if scope else "TBD"
    return (
        f"# {round_id.upper()} - {title}\n\n"
        f"- Generated at: `{utc_now()}`\n"
        f"- Scope: `{scope_text}`\n"
    )


def initialize_round_directory(
    base_dir: str | Path,
    round_id: str,
    title: str,
    scope: list[str],
    config_path: str | None = None,
    run_commands: list[str] | None = None,
) -> Path:
    round_dir = Path(base_dir) / round_id
    round_dir.mkdir(parents=True, exist_ok=True)

    template_payload = {
        "round_id": round_id,
        "title": title,
        "scope": scope,
        "config_path": config_path or "",
        "run_commands": run_commands or [],
        "generated_at": utc_now(),
    }
    write_json(round_dir / "run_manifest.json", template_payload)

    sections: dict[str, str] = {
        "round_summary.md": (
            _round_header(round_id, title, scope)
            + "\n## Goal\n\n- TODO\n\n## Baseline\n\n- TODO\n\n## Post-Run Result\n\n- TODO\n\n## Next Focus\n\n- TODO\n"
        ),
        "change_log.md": (
            _round_header(round_id, title, scope)
            + "\n## Change Log\n\n### ISSUE-001\n\n- Problem: TODO\n- Root cause: TODO\n- Modified area: TODO\n- Expected effect: TODO\n- Actual effect: TODO\n- Status: TODO\n"
        ),
        "dataflow_audit.md": (
            _round_header(round_id, title, scope)
            + "\n## Dataflow Audit\n\n### 1. Raw Input\n\n- TODO\n\n### 2. Extraction Output\n\n- TODO\n\n### 3. EvidenceRecord\n\n- TODO\n\n### 4. SchemaCandidate\n\n- TODO\n\n### 5. Attachment / Filtering\n\n- TODO\n\n### 6. Final Graph\n\n- TODO\n\n### 7. Metrics\n\n- TODO\n"
        ),
        "logic_audit.md": (
            _round_header(round_id, title, scope)
            + "\n## Logic Audit\n\n- TODO: main logic issues\n- TODO: edge cases\n- TODO: remaining risks\n"
        ),
        "code_quality_audit.md": (
            _round_header(round_id, title, scope)
            + "\n## Code Quality Audit\n\n- TODO: naming / responsibility\n- TODO: redundancy\n- TODO: artifact cleanliness\n- TODO: open-source quality judgment\n"
        ),
        "test_report.md": (
            _round_header(round_id, title, scope)
            + "\n## Test Report\n\n- Tests run: TODO\n- Failures encountered: TODO\n- Regression tests added: TODO\n- Final status: TODO\n"
        ),
    }

    for filename, text in sections.items():
        path = round_dir / filename
        if not path.exists():
            write_text(path, text)

    return round_dir


def _metric_value(metrics: dict[str, Any], section: str, key: str) -> float:
    value = metrics.get(section, {}).get(key, 0.0)
    return float(value)


def build_metrics_diff(baseline: dict[str, Any], post: dict[str, Any]) -> dict[str, Any]:
    fields = (
        ("concept_metrics", "precision"),
        ("concept_metrics", "recall"),
        ("concept_metrics", "f1"),
        ("anchor_metrics", "accuracy"),
        ("anchor_metrics", "macro_f1"),
        ("relation_metrics", "precision"),
        ("relation_metrics", "recall"),
        ("relation_metrics", "f1"),
    )
    delta: dict[str, Any] = {"baseline_path": baseline.get("graph_path"), "post_path": post.get("graph_path"), "metrics": {}}
    for section, key in fields:
        before = _metric_value(baseline, section, key)
        after = _metric_value(post, section, key)
        delta["metrics"][f"{section}.{key}"] = {
            "before": round(before, 4),
            "after": round(after, 4),
            "delta": round(after - before, 4),
        }

    count_fields = (
        ("predicted_counts", "concepts"),
        ("predicted_counts", "relations"),
        ("gold_counts", "concepts"),
        ("gold_counts", "relations"),
    )
    delta["counts"] = {}
    for section, key in count_fields:
        before = int(baseline.get(section, {}).get(key, 0))
        after = int(post.get(section, {}).get(key, 0))
        delta["counts"][f"{section}.{key}"] = {
            "before": before,
            "after": after,
            "delta": after - before,
        }
    return delta


def write_metrics_diff(round_dir: str | Path, baseline: dict[str, Any], post: dict[str, Any]) -> Path:
    payload = build_metrics_diff(baseline, post)
    path = Path(round_dir) / "metrics_diff.json"
    write_json(path, payload)
    return path


def summarize_graph_artifacts(graph_path: str | Path, attachment_audit_path: str | Path | None = None) -> dict[str, Any]:
    graph_payload = read_json(graph_path)
    summary = {
        "graph_path": str(Path(graph_path).resolve()),
        "node_count": len(graph_payload.get("nodes", [])),
        "edge_count": len(graph_payload.get("edges", [])),
        "graph_summary": graph_payload.get("summary", {}),
        "relation_validation": graph_payload.get("relation_validation", {}),
    }
    if attachment_audit_path and Path(attachment_audit_path).exists():
        attachment_payload = read_json(attachment_audit_path)
        summary["attachment_audit_path"] = str(Path(attachment_audit_path).resolve())
        summary["attachment_summary"] = attachment_payload.get("summary", {})
    return summary


def update_run_manifest(round_dir: str | Path, updates: dict[str, Any]) -> Path:
    path = Path(round_dir) / "run_manifest.json"
    payload = read_json(path) if path.exists() else {}
    payload.update(updates)
    payload["updated_at"] = utc_now()
    write_json(path, payload)
    return path


def render_metrics_table(rows: list[dict[str, Any]]) -> str:
    header = "| Round | Concept F1 | Anchor Acc | Anchor Macro-F1 | Relation F1 |\n|---|---:|---:|---:|---:|"
    body = [
        f"| {row['round']} | {row['concept_f1']:.4f} | {row['anchor_accuracy']:.4f} | {row['anchor_macro_f1']:.4f} | {row['relation_f1']:.4f} |"
        for row in rows
    ]
    return "\n".join([header, *body])


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _round_number(round_id: str) -> str:
    match = re.search(r"(\d+)$", round_id)
    if not match:
        return round_id
    return str(int(match.group(1)))


def _round_label(round_id: str) -> str:
    return f"Round {_round_number(round_id)}"


def _clean_embedded_markdown(text: str) -> str:
    lines = text.replace("\ufeff", "").splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    while lines and (not lines[0].strip() or lines[0].startswith("- Generated at:") or lines[0].startswith("- Scope:")):
        lines = lines[1:]

    shifted: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        prefix_len = len(line) - len(stripped)
        prefix = line[:prefix_len]
        if stripped.startswith("##"):
            hashes = len(stripped) - len(stripped.lstrip("#"))
            if 2 <= hashes <= 5:
                stripped = "#" + stripped
        shifted.append(prefix + stripped)

    return "\n".join(shifted).strip() or "- Missing content."


def _read_markdown_if_exists(path: Path) -> str:
    if not path.exists():
        return "- Missing content."
    return _clean_embedded_markdown(path.read_text(encoding="utf-8-sig"))


def _strip_leading_section_heading(text: str, heading: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == heading:
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines).strip() or "- Missing content."


def _sum_graph_counts(audit_payload: dict[str, Any]) -> dict[str, int]:
    domains = audit_payload.get("domains", {})
    return {
        "candidate_count": sum(int(payload.get("candidate_count", 0)) for payload in domains.values()),
        "node_count": sum(int(payload.get("graph_summary", {}).get("node_count", 0)) for payload in domains.values()),
        "edge_count": sum(int(payload.get("graph_summary", {}).get("edge_count", 0)) for payload in domains.values()),
    }


def _round_context(round_dir: Path | None, round_id: str) -> dict[str, Any]:
    manifest = _read_json_if_exists(round_dir / "run_manifest.json") if round_dir else {}
    baseline_metrics = _read_json_if_exists(round_dir / "baseline_metrics.json") if round_dir else {}
    post_metrics = _read_json_if_exists(round_dir / "post_metrics.json") if round_dir else {}
    metrics_diff = _read_json_if_exists(round_dir / "metrics_diff.json") if round_dir else {}
    ablation_report = _read_json_if_exists(round_dir / "ablation_report.json") if round_dir else {}

    audit_files = [
        "round_audit_snapshot.post.json",
        "round_audit_snapshot.run2.json",
        "round_audit_snapshot.baseline.json",
        "round_audit_snapshot.run1.json",
    ]
    audit_payload = {}
    if round_dir:
        for filename in audit_files:
            path = round_dir / filename
            if path.exists():
                audit_payload = _read_json_if_exists(path)
                break

    texts = {}
    for filename in ROUND_TEXT_FILES:
        texts[filename] = _read_markdown_if_exists(round_dir / filename) if round_dir else "- Missing content."

    texts["change_log.md"] = _strip_leading_section_heading(texts["change_log.md"], "### Change Log")
    texts["dataflow_audit.md"] = _strip_leading_section_heading(texts["dataflow_audit.md"], "### Dataflow Audit")
    texts["logic_audit.md"] = _strip_leading_section_heading(texts["logic_audit.md"], "### Logic Audit")
    texts["code_quality_audit.md"] = _strip_leading_section_heading(texts["code_quality_audit.md"], "### Code Quality Audit")
    texts["test_report.md"] = _strip_leading_section_heading(texts["test_report.md"], "### Test Report")

    return {
        "round_id": round_id,
        "round_dir": round_dir,
        "manifest": manifest,
        "baseline_metrics": baseline_metrics,
        "post_metrics": post_metrics,
        "metrics_diff": metrics_diff,
        "audit": audit_payload,
        "ablation_report": ablation_report,
        "texts": texts,
    }


def _format_metric(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def _format_metric_transition(diff_payload: dict[str, Any], key: str) -> str:
    metric = diff_payload.get("metrics", {}).get(key, {})
    if not metric:
        return "n/a"
    return f"{metric.get('before', 0.0):.4f} -> {metric.get('after', 0.0):.4f}"


def _overview_result(context: dict[str, Any]) -> str:
    diff = context["metrics_diff"]
    if not diff:
        return "No post-run metrics recorded."
    return (
        f"concept F1 {_format_metric_transition(diff, 'concept_metrics.f1')}; "
        f"anchor acc {_format_metric_transition(diff, 'anchor_metrics.accuracy')}; "
        f"relation F1 {_format_metric_transition(diff, 'relation_metrics.f1')}"
    )


def _dataflow_summary(context: dict[str, Any]) -> str:
    round_id = context["round_id"]
    if round_id == "round_04" and context["audit"]:
        counts = _sum_graph_counts(context["audit"])
        return (
            f"{ROUND_REPORT_PLAN[round_id]['dataflow']} "
            f"Post-audit totals were {counts['candidate_count']} candidates, {counts['node_count']} nodes, and {counts['edge_count']} edges."
        )
    if round_id == "round_05":
        run1 = _read_json_if_exists(context["round_dir"] / "round_audit_snapshot.run1.json") if context["round_dir"] else {}
        run2 = _read_json_if_exists(context["round_dir"] / "round_audit_snapshot.run2.json") if context["round_dir"] else {}
        if run1 and run2:
            c1 = _sum_graph_counts(run1)
            c2 = _sum_graph_counts(run2)
            return (
                f"{ROUND_REPORT_PLAN[round_id]['dataflow']} "
                f"Run 1 totals were {c1['candidate_count']} candidates / {c1['node_count']} nodes / {c1['edge_count']} edges; "
                f"run 2 totals were {c2['candidate_count']} candidates / {c2['node_count']} nodes / {c2['edge_count']} edges."
            )
    return ROUND_REPORT_PLAN.get(round_id, {}).get("dataflow", context["manifest"].get("notes", "See round dataflow audit."))


def _issue_status(context: dict[str, Any]) -> str:
    return ROUND_REPORT_PLAN.get(context["round_id"], {}).get("closure", context["manifest"].get("open_issues", "See round logic audit."))


def _render_overview_table(contexts: list[dict[str, Any]]) -> str:
    lines = [
        "| Round | Modification Theme | Impact Module | Result |",
        "|---|---|---|---|",
    ]
    for context in contexts:
        meta = ROUND_REPORT_PLAN.get(context["round_id"], {})
        lines.append(
            f"| {_round_label(context['round_id'])} | {meta.get('theme', context['manifest'].get('title', 'TBD'))} | {meta.get('modules', 'TBD')} | {_overview_result(context)} |"
        )
    return "\n".join(lines)


def _render_dataflow_table(contexts: list[dict[str, Any]]) -> str:
    lines = [
        "| Round | Input Scope | Dataflow Change |",
        "|---|---|---|",
    ]
    for context in contexts:
        scope = ", ".join(context["manifest"].get("scope", [])) or "Missing scope"
        lines.append(f"| {_round_label(context['round_id'])} | {scope} | {_dataflow_summary(context)} |")
    return "\n".join(lines)


def _render_architecture_table(contexts: list[dict[str, Any]]) -> str:
    lines = [
        "| Round | Logic / Architecture Change | Code Paths | Effect |",
        "|---|---|---|---|",
    ]
    for context in contexts:
        meta = ROUND_REPORT_PLAN.get(context["round_id"], {})
        lines.append(
            f"| {_round_label(context['round_id'])} | {meta.get('architecture', 'See round logic audit.')} | {meta.get('modules', 'TBD')} | {meta.get('theme', context['manifest'].get('title', 'TBD'))} |"
        )
    return "\n".join(lines)


def _render_issue_table(contexts: list[dict[str, Any]]) -> str:
    lines = [
        "| Round | Open / Closed Status | Evidence |",
        "|---|---|---|",
    ]
    for context in contexts:
        status = context["manifest"].get("status", "unknown")
        issue_text = context["manifest"].get("open_issues", "No explicit open issues recorded.")
        lines.append(f"| {_round_label(context['round_id'])} | {status}: {_issue_status(context)} | {issue_text} |")
    return "\n".join(lines)


def _render_ablation_table(ablation_report: dict[str, Any]) -> str:
    evaluations = ablation_report.get("evaluations", {})
    lines = [
        "| Variant | Concept F1 | Anchor Acc | Anchor Macro-F1 | Relation F1 | Predicted Concepts | Predicted Relations |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for variant_id in (
        "full_llm",
        "no_memory_bank",
        "no_rule_filter",
        "no_embedding_routing",
        "embedding_top1",
        "deterministic",
    ):
        payload = evaluations.get(variant_id)
        if not payload:
            continue
        lines.append(
            "| {variant} | {concept} | {anchor} | {anchor_macro} | {relation} | {concept_count} | {relation_count} |".format(
                variant=variant_id,
                concept=_format_metric(payload.get("concept_metrics", {}).get("f1")),
                anchor=_format_metric(payload.get("anchor_metrics", {}).get("accuracy")),
                anchor_macro=_format_metric(payload.get("anchor_metrics", {}).get("macro_f1")),
                relation=_format_metric(payload.get("relation_metrics", {}).get("f1")),
                concept_count=int(payload.get("predicted_counts", {}).get("concepts", 0)),
                relation_count=int(payload.get("predicted_counts", {}).get("relations", 0)),
            )
        )
    return "\n".join(lines)


def _render_round_detail(context: dict[str, Any]) -> str:
    label = _round_label(context["round_id"])
    manifest = context["manifest"]
    scope = ", ".join(manifest.get("scope", [])) or "Missing scope"
    metadata_lines = [
        f"- Title: {manifest.get('title', 'Missing title')}",
        f"- Scope: {scope}",
    ]
    if manifest.get("notes"):
        metadata_lines.append(f"- Notes: {manifest['notes']}")
    if manifest.get("recommended_variant"):
        metadata_lines.append(f"- Recommended variant: {manifest['recommended_variant']}")

    sections = [
        f"## {3 + int(_round_number(context['round_id']))}. {label} Detailed Record",
        "",
        "### Round Metadata",
        "",
        *metadata_lines,
        "",
        "### Summary",
        "",
        context["texts"]["round_summary.md"],
        "",
        "### Change Log",
        "",
        context["texts"]["change_log.md"],
        "",
        "### Dataflow Audit",
        "",
        context["texts"]["dataflow_audit.md"],
        "",
        "### Logic Audit",
        "",
        context["texts"]["logic_audit.md"],
        "",
        "### Code Quality Audit",
        "",
        context["texts"]["code_quality_audit.md"],
        "",
        "### Test Report",
        "",
        context["texts"]["test_report.md"],
        "",
    ]
    return "\n".join(sections)


def compile_five_round_report(
    rounds_root: str | Path,
    output_path: str | Path,
    title: str = "Five-Round Optimization Report",
) -> Path:
    rounds_root = Path(rounds_root)
    discovered = {item.name: item for item in rounds_root.iterdir() if item.is_dir() and item.name.startswith("round_")}
    contexts = [_round_context(discovered.get(round_id), round_id) for round_id in ROUND_SEQUENCE]

    metric_rows = [
        {
            "round": _round_label(context["round_id"]),
            "concept_f1": _metric_value(context["post_metrics"], "concept_metrics", "f1"),
            "anchor_accuracy": _metric_value(context["post_metrics"], "anchor_metrics", "accuracy"),
            "anchor_macro_f1": _metric_value(context["post_metrics"], "anchor_metrics", "macro_f1"),
            "relation_f1": _metric_value(context["post_metrics"], "relation_metrics", "f1"),
        }
        for context in contexts
        if context["post_metrics"]
    ]

    round_04_context = next((context for context in contexts if context["round_id"] == "round_04"), {})
    ablation_report = round_04_context.get("ablation_report", {})

    sections: list[str] = [
        f"# {title}",
        "",
        "## 1. Background And Goal",
        "",
        "- This report records a five-round optimization program for the CrossExtend-KG O&M pipeline under a strict no-fallback rule.",
        "- Every round used real runs, audited the end-to-end dataflow, fixed mainline logic defects, reran evaluation, and synchronized the project documentation.",
        "- The fixed round scopes were BATOM_002 in Rounds 1-2, BATOM_002/CNCOM_002/EVMAN_002 in Round 3, all 9 human-gold files in Round 4, and frozen multi-document replay in Round 5.",
        "",
        "## 2. Initial State And Major Problems",
        "",
        "- Relation noise was too high, especially from over-promoted structural and step-local edges.",
        "- Signal / Fault / State boundaries were unstable, which made attachment quality sensitive to phrasing rather than semantics.",
        "- Cross-domain evaluation was partially invalid because the CNC markdown filenames and gold ids were content-misaligned.",
        "- The evaluation layer lacked a unified round-preparation, manifest, and reporting structure, which made reproducibility and ablation tracking weaker than the paper needed.",
        "- Human-gold evaluation also exposed annotation risks, most notably BATOM_001 where the staged markdown has 8 task steps but the current gold covers only 6.",
        "",
        "## 3. Five-Round Overview",
        "",
        _render_overview_table(contexts),
        "",
    ]

    for context in contexts:
        sections.extend([_render_round_detail(context)])

    sections.extend(
        [
            "## 9. Five-Round Metrics Change Table",
            "",
            render_metrics_table(metric_rows) if metric_rows else "- No metrics were recorded.",
            "",
            "## 10. Five-Round Dataflow Change Table",
            "",
            _render_dataflow_table(contexts),
            "",
            "## 11. Five-Round Code Logic And Architecture Change Table",
            "",
            _render_architecture_table(contexts),
            "",
            "## 12. Ablation Study Conclusion",
            "",
        ]
    )

    if ablation_report:
        sections.extend(
            [
                _render_ablation_table(ablation_report),
                "",
                "- `no_rule_filter` is the only ablation that clearly degrades all major metrics at once, so rule filtering is the strongest demonstrated contributor on the 9-document human-gold set.",
                "- `no_memory_bank` is slightly worse on concept F1 but effectively tied on relation F1, which means the current corpus is too small to claim a strong memory-bank advantage.",
                "- `no_embedding_routing`, `embedding_top1`, and `deterministic` stay very close to `full_llm`, so LLM attachment should be described as marginally helpful rather than decisively superior on the current benchmark.",
                "- These results support the pipeline as a whole, but they do not support an aggressive claim that the LLM attachment component is the main source of gains.",
                "",
            ]
        )
    else:
        sections.extend(["- Ablation report missing.", ""])

    sections.extend(
        [
            "## 13. Final Frozen Architecture",
            "",
            "- Frozen mainline: staged markdown -> preprocessing extraction -> step-scoped EvidenceRecord -> SchemaCandidate aggregation -> attachment/routing -> rule filtering -> final graph -> human-gold metrics and ablation.",
            "- Evidence records stay domain-split under round-scoped artifact roots, and the pipeline does not fall back to alternate paths when extraction or attachment is weak.",
            "- Evaluation is driven only by human gold for paper-facing metrics; silver or auto-generated artifacts remain diagnostic only.",
            "- Round preparation, run manifests, baseline/post metrics, metrics diff files, audit snapshots, and ablation outputs now live under `artifacts/optimization_rounds/round_xx/`, which keeps `working/` from becoming the primary evidence source.",
            "",
            "## 14. Current Remaining Risks",
            "",
            _render_issue_table(contexts),
            "",
            "- The most serious remaining risk is still BATOM_001 annotation mismatch. This should be fixed in the gold, not hidden in the evaluator.",
            "- Structural specificity is still incomplete for several gold concepts such as front-manifold and quick-coupler boundary labels.",
            "- Repeated `full_llm` runs still show modest concept-count drift, so the final paper should describe stability honestly and avoid claiming strict determinism.",
            "",
            "## 15. Next Recommendations",
            "",
            "- Repair BATOM_001 human gold so every staged step is represented before using the corpus as a final paper benchmark.",
            "- Expand human-gold coverage or repeated-run sampling if the paper wants to claim stronger evidence for memory-bank or LLM-attachment benefits.",
            "- Continue tightening structural locus labeling so concepts such as manifold face, quick connector, outlet boundary, and clamp stack map to the same specificity as gold.",
            "- Keep new experiment or paper tables routed through the round-manifest / metrics-diff / ablation-report path instead of adding new ad-hoc scripts or output folders.",
        ]
    )

    output_path = Path(output_path)
    write_text(output_path, "\n".join(sections))
    return output_path
