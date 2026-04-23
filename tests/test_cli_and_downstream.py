#!/usr/bin/env python3
"""Minimal regression tests for the cleaned CLI surface and downstream schema."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cli import _build_parser
from experiments.downstream import load_downstream_benchmark


class CliAndDownstreamTests(unittest.TestCase):
    def test_run_parser_accepts_domain_subset(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "run",
                "--config",
                "config/persistent/pipeline.deepseek.yaml",
                "--domains",
                "battery",
                "cnc",
            ]
        )
        self.assertEqual(args.command, "run")
        self.assertEqual(args.domains, ["battery", "cnc"])

    def test_load_downstream_benchmark_template(self) -> None:
        payload = {
            "schema_version": "downstream_eval.v1",
            "annotation_policy": "Blind downstream annotation from source text only.",
            "metric_boundary": "workflow-first downstream evaluation",
            "samples": [
                {
                    "task_id": "DWR_BATOM_002_01",
                    "task_type": "workflow_retrieval",
                    "domain": "battery",
                    "source_doc": "BATOM_002",
                    "query": "Coolant odor is visible after access removal. Which workflow suffix should be retrieved?",
                    "given_evidence": ["coolant odor", "front manifold face"],
                    "observed_steps": ["T1", "T2"],
                    "gold_steps": ["T3", "T4", "T5"],
                    "gold_objects": ["EPDM O-ring", "flange gap"],
                    "query_focus": "full_suffix",
                    "answer_format": "grounded_suffix",
                },
                {
                    "task_id": "RSR_BATOM_002_01",
                    "task_type": "repair_suffix_ranking",
                    "domain": "battery",
                    "source_doc": "BATOM_002",
                    "query": "Rank the most plausible repair-and-verify suffix after the inspection prefix.",
                    "observed_steps": ["T1", "T2", "T3", "T4"],
                    "candidate_suffixes": [
                        {
                            "candidate_id": "A",
                            "steps": ["T5", "T6", "T7"],
                            "objects": ["flange gap", "EPDM O-ring"],
                            "rationale": "measure and verify the sealing boundary",
                        },
                        {
                            "candidate_id": "B",
                            "steps": ["T5"],
                            "objects": ["undertray"],
                            "rationale": "stop after a superficial check",
                        },
                    ],
                    "gold_candidate_ids": ["A"],
                    "gold_suffix": ["T5", "T6", "T7"],
                    "gold_objects": ["flange gap", "EPDM O-ring"],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "benchmark.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            benchmark = load_downstream_benchmark(path)

        self.assertEqual(benchmark.schema_version, "downstream_eval.v1")
        self.assertEqual(len(benchmark.samples), 2)
        self.assertEqual(benchmark.samples[0].task_type, "workflow_retrieval")
        self.assertEqual(benchmark.samples[1].task_type, "repair_suffix_ranking")


if __name__ == "__main__":
    unittest.main()
