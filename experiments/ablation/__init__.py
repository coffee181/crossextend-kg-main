#!/usr/bin/env python3
"""Ablation package with explicit specs and runner utilities."""

from experiments.ablation.runner import main, materialize_ablation_config, materialize_ablation_variant_config, run_ablation_experiment
from experiments.ablation.specs import DEFAULT_ABLATION_SPECS, build_default_ablation_variants, list_ablation_specs

__all__ = [
    "DEFAULT_ABLATION_SPECS",
    "build_default_ablation_variants",
    "list_ablation_specs",
    "main",
    "materialize_ablation_config",
    "materialize_ablation_variant_config",
    "run_ablation_experiment",
]
