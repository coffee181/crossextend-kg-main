#!/usr/bin/env python3
"""Shared helpers for the CrossExtend-KG pipeline."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def normalize_text(text: str, normalize_whitespace: bool = True) -> str:
    if not normalize_whitespace:
        return text.strip()
    return re.sub(r"\s+", " ", text).strip()


def json_pretty(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_prompt_template(template: str, replacements: dict[str, str]) -> str:
    output = template
    for key, value in replacements.items():
        output = output.replace(key, value)
    return output

