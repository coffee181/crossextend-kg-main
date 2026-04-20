#!/usr/bin/env python3
"""Ablation package with explicit specs and runner utilities."""

from .runner import main, materialize_ablation_config, run_ablation_experiment
from .specs import DEFAULT_ABLATION_SPECS, build_default_ablation_variants

__all__ = [
    "DEFAULT_ABLATION_SPECS",
    "build_default_ablation_variants",
    "main",
    "materialize_ablation_config",
    "run_ablation_experiment",
]
