"""Record real embeddings for the baseline corpus into a versioned cassette,
then regenerate snapshot.json by replaying it. Run via
`uv run python -m tests.baseline.record` from the repo root. See
tests/baseline/harness.py for the replay path this script feeds."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import cast

import numpy as np
from dotenv import load_dotenv

from slopo.embedding.command import run_embed
from slopo.indexing.normalize import LEVELS
from tests.baseline import harness


def _export_vectors(conn: sqlite3.Connection) -> dict[str, list[float]]:
    rows = conn.execute("SELECT embed_hash, embedding FROM embeddings").fetchall()
    return {
        embed_hash: np.frombuffer(blob, dtype=np.float32).tolist()
        for embed_hash, blob in rows
    }


def _corpus_counts(conn: sqlite3.Connection) -> dict[str, int]:
    files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    units = conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0]
    distinct_bodies = conn.execute(
        "SELECT COUNT(DISTINCT body_hash) FROM code_units"
    ).fetchone()[0]
    return {"files": files, "units": units, "distinct_bodies": distinct_bodies}


def _print_summary(report: harness.BaselineReport) -> None:
    corpus = report.corpus
    totals = report.totals
    print()
    print(
        f"files: {corpus['files']}  units: {corpus['units']}  "
        f"distinct_bodies: {corpus['distinct_bodies']}  "
        f"exact_copies: {corpus['exact_copies']}"
    )
    print(
        f"clusters: {totals['clusters']}  recall: {totals['recall']}  "
        f"max_recall_at_zero_fp: {totals['max_recall_at_zero_fp']}  "
        f"false_positives: {totals['false_positives']}  "
        f"separation_margin: {totals['separation_margin']}  "
        f"zero_fp_threshold_floor: {totals['zero_fp_threshold_floor']}"
    )
    by_language = cast(
        "dict[str, dict[str, float | int | None]]", totals["by_language"]
    )
    for language in sorted(by_language):
        stats = by_language[language]
        print(
            f"  {language:<10} duplicates: {stats['duplicates']:<3} "
            f"distinct: {stats['distinct']:<3} recall: {stats['recall']}  "
            f"max_recall_at_zero_fp: {stats['max_recall_at_zero_fp']}  "
            f"false_positives: {stats['false_positives']}  "
            f"separation_margin: {stats['separation_margin']}"
        )
    print()
    header = f"{'name':<62} {'kind':<10} {'similarity':>10} {'same_cluster':>13}"
    print(header)
    print("-" * len(header))
    for pair in report.pairs:
        print(
            f"{pair.name:<62} {pair.kind:<10} {pair.similarity:>10.4f} "
            f"{str(pair.same_cluster):>13}"
        )


def record(dry_run: bool, representation: str) -> None:
    # litellm happens to load .env on import, so OLLAMA_API_BASE resolves even
    # without this call. Do not rely on that side effect.
    load_dotenv()

    print(f"representation: {representation}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "record.db"
        conn = harness.index_corpus(db_file, representation=representation)
        try:
            counts = _corpus_counts(conn)
            if dry_run:
                print(f"files: {counts['files']}")
                print(f"units: {counts['units']}")
                print(f"distinct bodies to embed: {counts['distinct_bodies']}")
                return

            cfg = harness.build_config(db_file, representation=representation)
            run_embed(conn, cfg, lambda message: print(message))

            vectors = _export_vectors(conn)
            harness.save_cassette(
                harness.cassette_path(representation=representation), vectors
            )
        finally:
            conn.close()

    report = harness.run_baseline(representation=representation)
    snapshot_file = harness.snapshot_path(representation)
    snapshot_file.write_text(
        json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    print(f"snapshot written to {snapshot_file}")
    _print_summary(report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the baseline embedding cassette and snapshot."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="index the corpus and report counts without calling the model",
    )
    parser.add_argument(
        "--representation",
        default=harness.REPRESENTATION,
        choices=LEVELS,
        help="AST normalization level to embed and record (default: %(default)s)",
    )
    args = parser.parse_args()
    record(dry_run=args.dry_run, representation=args.representation)


if __name__ == "__main__":
    main()
