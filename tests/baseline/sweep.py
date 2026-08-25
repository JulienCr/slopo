"""Sweep similarity thresholds through the real pipeline for one model.

Run via `uv run python -m tests.baseline.sweep`. Replays a committed cassette, so it
needs no model. See doc/threshold-calibration.md for how to read the result.
"""

from __future__ import annotations

import argparse

from tests.baseline import harness

_DEFAULT_THRESHOLDS = (0.92, 0.88, 0.85, 0.82, 0.80, 0.78, 0.76, 0.74, 0.72, 0.70)
_RERANK_OFFSET = 0.02


def sweep(model_key: str, representation: str, thresholds: tuple[float, ...]) -> None:
    profile = harness.resolve_model(model_key)
    print(f"model: {model_key} ({profile.model})  representation: {representation}")
    print(
        f"{'similarity':>11}{'rerank':>9}{'recall':>9}{'false pos':>11}{'clusters':>10}"
    )

    original = (harness.SIMILARITY_THRESHOLD, harness.RERANK_THRESHOLD)
    try:
        for similarity in thresholds:
            # run_baseline reads these at call time; there is no per-call override.
            harness.SIMILARITY_THRESHOLD = similarity
            harness.RERANK_THRESHOLD = round(similarity + _RERANK_OFFSET, 4)
            totals = harness.run_baseline(
                model_key=model_key, representation=representation
            ).to_dict()["totals"]
            print(
                f"{similarity:>11.2f}{harness.RERANK_THRESHOLD:>9.2f}"
                f"{totals['recall']:>9.2f}{totals['false_positives']:>11}"
                f"{totals['clusters']:>10}"
            )
    finally:
        harness.SIMILARITY_THRESHOLD, harness.RERANK_THRESHOLD = original


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default=harness.DEFAULT_MODEL, choices=sorted(harness.MODELS)
    )
    parser.add_argument(
        "--representation", default=harness.REPRESENTATION, choices=harness.LEVELS
    )
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=list(_DEFAULT_THRESHOLDS),
        help="similarity thresholds to try; rerank follows at +0.02",
    )
    args = parser.parse_args()
    sweep(args.model, args.representation, tuple(args.thresholds))


if __name__ == "__main__":
    main()
