#!/usr/bin/env python3
"""Logging configuration for CrossExtend-KG."""

from __future__ import annotations

import logging
import sys
from typing import TextIO


def configure_logging(
    level: int = logging.INFO,
    format_string: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure logging for CrossExtend-KG.

    Args:
        level: Logging level (default: INFO)
        format_string: Log format string
        stream: Output stream (default: sys.stderr)

    Returns:
        Root logger for the package
    """
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(format_string))

    logger = logging.getLogger("crossextend_kg")
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (e.g., "pipeline.runner")

    Returns:
        Logger instance
    """
    return logging.getLogger(f"crossextend_kg.{name}")