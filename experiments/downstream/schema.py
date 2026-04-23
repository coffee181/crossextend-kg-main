#!/usr/bin/env python3
"""Typed schemas for workflow-first downstream evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class BaseDownstreamSample(BaseModel):
    task_id: str
    task_type: str
    domain: Literal["battery", "cnc", "nev"]
    source_doc: str
    query: str
    given_evidence: list[str] = Field(default_factory=list)
    notes: str = ""


class WorkflowRetrievalSample(BaseDownstreamSample):
    task_type: Literal["workflow_retrieval"] = "workflow_retrieval"
    query_focus: Literal[
        "fault_localization",
        "repair_execution",
        "verification_release",
        "full_suffix",
    ] = "full_suffix"
    observed_steps: list[str] = Field(default_factory=list)
    gold_steps: list[str] = Field(default_factory=list)
    gold_objects: list[str] = Field(default_factory=list)
    answer_format: Literal["ranked_steps", "ordered_suffix", "grounded_suffix"] = "grounded_suffix"


class SuffixCandidate(BaseModel):
    candidate_id: str
    steps: list[str] = Field(default_factory=list)
    objects: list[str] = Field(default_factory=list)
    rationale: str = ""


class RepairSuffixRankingSample(BaseDownstreamSample):
    task_type: Literal["repair_suffix_ranking"] = "repair_suffix_ranking"
    observed_steps: list[str] = Field(default_factory=list)
    candidate_suffixes: list[SuffixCandidate] = Field(default_factory=list)
    gold_candidate_ids: list[str] = Field(default_factory=list)
    gold_suffix: list[str] = Field(default_factory=list)
    gold_objects: list[str] = Field(default_factory=list)
    ranking_target: Literal["repair_suffix", "repair_verify_suffix"] = "repair_verify_suffix"


DownstreamSample = Annotated[
    WorkflowRetrievalSample | RepairSuffixRankingSample,
    Field(discriminator="task_type"),
]


_SAMPLE_ADAPTER = TypeAdapter(list[DownstreamSample])


class DownstreamBenchmark(BaseModel):
    schema_version: Literal["downstream_eval.v1"] = "downstream_eval.v1"
    annotation_policy: str
    metric_boundary: str
    samples: list[DownstreamSample]

    @classmethod
    def from_payload(cls, payload: dict) -> "DownstreamBenchmark":
        data = dict(payload)
        data["samples"] = _SAMPLE_ADAPTER.validate_python(data.get("samples", []))
        return cls.model_validate(data)


def load_downstream_benchmark(path: str | Path) -> DownstreamBenchmark:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    return DownstreamBenchmark.from_payload(payload)
