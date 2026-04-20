from __future__ import annotations

import json
from pathlib import Path

from crossextend_kg.experiments.rounds import prepare_round_workspace


def test_prepare_round_workspace_stages_inputs_and_writes_configs(tmp_path: Path) -> None:
    source_doc = tmp_path / "sources" / "battery" / "BATOM_SRC.md"
    source_doc.parent.mkdir(parents=True)
    source_doc.write_text("| Time step | O&M sample text |\n|---|---|\n| T1 | Example step. |\n", encoding="utf-8")

    gold_file = tmp_path / "gold" / "battery_BATOM_999.json"
    gold_file.parent.mkdir(parents=True)
    gold_file.write_text(
        json.dumps(
            {
                "domain_id": "battery",
                "documents": [{"doc_id": "BATOM_999", "doc_type": "om_manual"}],
                "concept_ground_truth": [],
                "relation_ground_truth": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    prompt_root = tmp_path / "config"
    (prompt_root / "prompts").mkdir(parents=True)
    (prompt_root / "prompts" / "preprocessing_extraction_om.txt").write_text("prompt", encoding="utf-8")
    (prompt_root / "prompts" / "attachment_judge.txt").write_text("prompt", encoding="utf-8")
    (prompt_root / "persistent").mkdir(parents=True)
    (prompt_root / "persistent" / "relation_constraints.json").write_text("{}", encoding="utf-8")

    preprocess_config = prompt_root / "persistent" / "preprocessing.base.json"
    preprocess_config.write_text(
        json.dumps(
            {
                "data_root": "../../data",
                "domain_ids": ["battery"],
                "output_path": "../../data/evidence_records/evidence_records_llm.json",
                "role": "target",
                "prompt_template_path": "../prompts/preprocessing_extraction_om.txt",
                "llm": {
                    "base_url": "https://api.deepseek.com",
                    "api_key": "${DEEPSEEK_API_KEY}",
                    "model": "deepseek-chat",
                    "timeout_sec": 600,
                    "max_tokens": 8000,
                    "temperature": 0.1,
                },
                "batch_size": 5,
                "relation_families": ["task_dependency"],
                "backbone_concepts": ["Task"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    pipeline_config = prompt_root / "persistent" / "pipeline.base.json"
    pipeline_config.write_text(
        json.dumps(
            {
                "project_name": "CrossExtend-KG",
                "benchmark_name": "base",
                "prompts": {"attachment_judge_template_path": "../prompts/attachment_judge.txt"},
                "llm": {
                    "base_url": "https://api.deepseek.com",
                    "api_key": "${DEEPSEEK_API_KEY}",
                    "model": "deepseek-chat",
                    "timeout_sec": 600,
                    "max_tokens": 4096,
                    "temperature": 0.1,
                },
                "embedding": {
                    "base_url": "http://127.0.0.1:11434/v1",
                    "api_key": "",
                    "model": "bge-m3:latest",
                    "timeout_sec": 300,
                    "dimensions": 1024,
                },
                "backbone": {
                    "seed_concepts": ["Task"],
                    "seed_descriptions": {"Task": "maintenance task"},
                },
                "relations": {
                    "relation_families": ["task_dependency"],
                    "family_descriptions": {"task_dependency": "dependencies"},
                    "allowed_routes": ["reuse_backbone", "vertical_specialize", "reject"],
                },
                "data": {"normalize_whitespace": True},
                "runtime": {
                    "artifact_root": "../../artifacts",
                    "retrieval_top_k": 3,
                    "min_relation_support_count": 1,
                    "llm_attachment_batch_size": 8,
                    "enable_temporal_memory_bank": True,
                    "temporal_memory_top_k": 3,
                    "temporal_memory_max_entries": 4000,
                    "temporal_memory_path": None,
                    "save_latest_summary": True,
                    "write_detailed_working_artifacts": False,
                    "write_jsonl_artifacts": False,
                    "write_graph_db_csv": False,
                    "write_property_graph_jsonl": False,
                    "run_prefix": "base",
                    "relation_constraints_path": "./relation_constraints.json",
                    "enable_relation_validation": True,
                },
                "variants": [
                    {
                        "variant_id": "full_llm",
                        "description": "main",
                        "attachment_strategy": "llm",
                        "use_embedding_routing": True,
                        "use_rule_filter": True,
                        "allow_free_form_growth": False,
                        "enable_snapshots": True,
                        "enable_memory_bank": True,
                        "export_artifacts": True,
                    }
                ],
                "domains": [
                    {
                        "domain_id": "battery",
                        "domain_name": "Battery",
                        "role": "target",
                        "data_path": "../../data/evidence_records/battery_evidence_records_llm.json",
                        "source_types": ["om_manual"],
                        "domain_keywords": ["battery"],
                        "ontology_seed_path": None,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    alignment = {
        "battery": {
            "BATOM_999": {
                "gold_file": str(gold_file),
                "source_markdown": str(source_doc),
                "alignment_mode": "content_aligned_alias",
            }
        }
    }

    round_dir = tmp_path / "artifacts" / "round_99"
    manifest = prepare_round_workspace(
        round_dir=round_dir,
        doc_ids=["BATOM_999"],
        alignment=alignment,
        base_preprocess_config_path=preprocess_config,
        base_pipeline_config_path=pipeline_config,
        benchmark_name="round99",
        run_prefix="round99",
    )

    staged_doc = round_dir / "input" / "battery" / "BATOM_999.md"
    assert staged_doc.exists()
    assert staged_doc.read_text(encoding="utf-8") == source_doc.read_text(encoding="utf-8")

    preprocess_payload = json.loads(Path(manifest["preprocess_config_path"]).read_text(encoding="utf-8"))
    pipeline_payload = json.loads(Path(manifest["pipeline_config_path"]).read_text(encoding="utf-8"))

    assert preprocess_payload["data_root"] == str((round_dir / "input").resolve())
    assert Path(preprocess_payload["prompt_template_path"]).is_absolute()
    assert pipeline_payload["benchmark_name"] == "round99"
    assert pipeline_payload["runtime"]["run_prefix"] == "round99"
    assert pipeline_payload["domains"][0]["data_path"] == manifest["evidence_paths_by_domain"]["battery"]
    assert Path(pipeline_payload["prompts"]["attachment_judge_template_path"]).is_absolute()
