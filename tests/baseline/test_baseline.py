"""Offline baseline test: replays the committed embedding cassette against the
real analysis pipeline and compares against the committed snapshot. Runs in
the normal suite, with no model. See tests/baseline/record.py to regenerate."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest

from tests.baseline.harness import SNAPSHOT_FILE, run_baseline

_FLOAT_TOLERANCE = 5e-4


def _load_snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))


def _assert_matches(actual: Any, expected: Any, path: str) -> None:
    if isinstance(expected, float) or isinstance(actual, float):
        if expected is None or actual is None:
            assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"
            return
        assert abs(actual - expected) <= _FLOAT_TOLERANCE, (
            f"{path}: expected {expected!r}, got {actual!r} "
            f"(diff {abs(actual - expected)!r} > {_FLOAT_TOLERANCE})"
        )
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected dict, got {actual!r}"
        assert actual.keys() == expected.keys(), (
            f"{path}: key mismatch, expected {sorted(expected.keys())}, "
            f"got {sorted(actual.keys())}"
        )
        for key in expected:
            _assert_matches(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected list, got {actual!r}"
        assert len(actual) == len(expected), (
            f"{path}: expected {len(expected)} items, got {len(actual)}"
        )
        for index, (a, e) in enumerate(zip(actual, expected)):
            _assert_matches(a, e, f"{path}[{index}]")
    else:
        assert actual == expected, f"{path}: expected {expected!r}, got {actual!r}"


def test_baseline_matches_snapshot():
    report = run_baseline().to_dict()

    if os.environ.get("SLOPO_BASELINE_UPDATE") == "1":
        SNAPSHOT_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        pytest.skip("SLOPO_BASELINE_UPDATE=1: snapshot rewritten, not asserted")

    snapshot = _load_snapshot()
    _assert_matches(report, snapshot, "report")


def test_baseline_is_not_vacuous():
    report = run_baseline().to_dict()
    snapshot = _load_snapshot()

    assert report["totals"]["recall"] > 0, "no duplicate pair was detected at all"
    assert report["corpus"]["files"] > 0
    assert report["corpus"]["units"] > 0
    assert report["corpus"]["files"] == snapshot["corpus"]["files"]
    assert report["corpus"]["units"] == snapshot["corpus"]["units"]
