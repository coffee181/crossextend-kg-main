from __future__ import annotations

import json
from pathlib import Path


def test_ground_truth_files_are_present_and_well_formed() -> None:
    ground_truth_dir = Path(__file__).resolve().parents[1] / "data" / "ground_truth"
    files = sorted(ground_truth_dir.glob("*.json"))

    assert files, "expected frozen gold files under data/ground_truth"

    for path in files[:3]:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        assert isinstance(payload, dict)
        assert payload
