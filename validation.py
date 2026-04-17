#!/usr/bin/env python3
"""Validation utilities for CrossExtend-KG."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .exceptions import ConfigValidationError


def validate_json_path(path: str | Path, must_exist: bool = True) -> Path:
    """Validate that a path points to a JSON file.

    Args:
        path: Path to validate
        must_exist: If True, raise error if file doesn't exist

    Returns:
        Resolved Path object

    Raises:
        ConfigValidationError: If path is invalid or file doesn't exist
    """
    resolved = Path(path).resolve()
    if must_exist and not resolved.exists():
        raise ConfigValidationError(f"Path does not exist: {resolved}")
    if resolved.suffix != ".json":
        raise ConfigValidationError(f"Expected .json file: {resolved}")
    return resolved


def validate_domain_id(domain_id: str) -> str:
    """Validate domain identifier format.

    Args:
        domain_id: Domain identifier to validate

    Returns:
        Validated domain_id

    Raises:
        ConfigValidationError: If domain_id format is invalid
    """
    if not domain_id:
        raise ConfigValidationError("domain_id cannot be empty")
    if not re.match(r"^[a-z][a-z0-9_]*$", domain_id):
        raise ConfigValidationError(
            f"domain_id must start with lowercase letter and contain only "
            f"lowercase letters, digits, and underscores: {domain_id}"
        )
    return domain_id


def validate_variant_id(variant_id: str) -> str:
    """Validate variant identifier format.

    Args:
        variant_id: Variant identifier to validate

    Returns:
        Validated variant_id

    Raises:
        ConfigValidationError: If variant_id format is invalid
    """
    if not variant_id:
        raise ConfigValidationError("variant_id cannot be empty")
    if not re.match(r"^[a-z][a-z0-9_]*$", variant_id):
        raise ConfigValidationError(
            f"variant_id must start with lowercase letter and contain only "
            f"lowercase letters, digits, and underscores: {variant_id}"
        )
    return variant_id


def validate_label(label: str) -> str:
    """Validate concept/relation label format.

    Args:
        label: Label to validate

    Returns:
        Validated label

    Raises:
        ConfigValidationError: If label format is invalid
    """
    if not label:
        raise ConfigValidationError("label cannot be empty")
    # Allow alphanumeric, underscores, hyphens, and CJK characters
    if not re.match(r"^[a-zA-Z0-9_\-\u4e00-\u9fff]+$", label):
        raise ConfigValidationError(
            f"label contains invalid characters: {label}"
        )
    return label.strip()


def validate_relation_family(family: str, allowed_families: set[str]) -> str:
    """Validate relation family.

    Args:
        family: Relation family to validate
        allowed_families: Set of allowed relation families

    Returns:
        Validated family

    Raises:
        ConfigValidationError: If family is not in allowed set
    """
    if family not in allowed_families:
        raise ConfigValidationError(
            f"relation_family '{family}' not in allowed families: "
            f"{sorted(allowed_families)}"
        )
    return family


def validate_route(route: str, allowed_routes: set[str]) -> str:
    """Validate attachment route.

    Args:
        route: Route to validate
        allowed_routes: Set of allowed routes

    Returns:
        Validated route

    Raises:
        ConfigValidationError: If route is not in allowed set
    """
    if route not in allowed_routes:
        raise ConfigValidationError(
            f"route '{route}' not in allowed routes: {sorted(allowed_routes)}"
        )
    return route


def validate_score_range(score: float, name: str) -> float:
    """Validate that a score is in [0, 1] range.

    Args:
        score: Score to validate
        name: Name of the score for error message

    Returns:
        Validated score

    Raises:
        ConfigValidationError: If score is out of range
    """
    if not 0.0 <= score <= 1.0:
        raise ConfigValidationError(
            f"{name} must be in range [0, 1], got {score}"
        )
    return round(score, 4)


def validate_positive_int(value: int, name: str) -> int:
    """Validate that an integer is positive.

    Args:
        value: Value to validate
        name: Name of the value for error message

    Returns:
        Validated value

    Raises:
        ConfigValidationError: If value is not positive
    """
    if value <= 0:
        raise ConfigValidationError(
            f"{name} must be positive, got {value}"
        )
    return value