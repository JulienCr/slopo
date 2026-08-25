"""Offline quality baseline harness: drives the real analysis pipeline over a
recorded embedding cassette so the labeled corpus can be scored deterministically,
without a model, in CI. See tests/baseline/test_harness.py for unit coverage."""

from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml  # type: ignore[import-untyped]

from slopo.analysis.clustering import build_clusters, filter_clusters, reorder_clusters
from slopo.analysis.db import count_exact_copies, load_units
from slopo.analysis.dedup import fold_exact_duplicates
from slopo.analysis.models import Cluster, SimilarPair, UnitRecord
from slopo.analysis.overlap import exclude_overlapping_pairs
from slopo.analysis.rerank import rerank_all_clusters, rerank_pair_score
from slopo.analysis.similarity import find_similar_pairs
from slopo.config import Config
from slopo.db import create_db
from slopo.embedding.db import load_embeddings
from slopo.indexing.command import run_index
from slopo.indexing.normalize import LEVELS

BASELINE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASELINE_DIR / "corpus"
EXPECTATIONS_FILE = BASELINE_DIR / "expectations.yaml"
EMBEDDINGS_DIR = BASELINE_DIR / "embeddings"
SNAPSHOT_FILE = BASELINE_DIR / "snapshot.json"

# Pinned here, deliberately not read from slopo's config defaults: a future
# change to a default must produce a visible baseline update, not silent drift.
# REPRESENTATION is likewise pinned: the committed snapshot must describe one
# known configuration.


@dataclass(frozen=True)
class ModelProfile:
    model: str
    dimensions: int
    input_prefix: str | None = None


# Dimensions and prefix are measured, not guessed: the 1.5b model is a
# Matryoshka model truncated to 256 dims because that improves separation on
# this corpus (upstream's README recommends the same width for Jina code
# models), and the prefix is the code2code query instruction from its model
# card.
MODELS: dict[str, ModelProfile] = {
    "jina-v2-base-code": ModelProfile(
        model="ollama/unclemusclez/jina-embeddings-v2-base-code",
        dimensions=768,
    ),
    "jina-code-1.5b": ModelProfile(
        model="ollama/hf.co/herMaster/jina-code-embeddings-1.5b-GGUF",
        dimensions=256,
        input_prefix=(
            "Find an equivalent code snippet given the following code snippet:\n"
        ),
    ),
}

DEFAULT_MODEL = "jina-v2-base-code"

MODEL = MODELS[DEFAULT_MODEL].model
DIMENSIONS = MODELS[DEFAULT_MODEL].dimensions
SIMILARITY_THRESHOLD = 0.92
RERANK_THRESHOLD = 0.94
BODY_NODE_COUNT_THRESHOLD = 10
REPRESENTATION = "raw"

_BLOCK_SIZE = 1000
_MAX_REPORTED_MISSING_HASHES = 10


class MissingEmbeddingsError(Exception):
    def __init__(self, missing_hashes: list[str]) -> None:
        preview = ", ".join(missing_hashes[:_MAX_REPORTED_MISSING_HASHES])
        extra = len(missing_hashes) - _MAX_REPORTED_MISSING_HASHES
        suffix = f" (+{extra} more)" if extra > 0 else ""
        super().__init__(
            f"missing embeddings for {len(missing_hashes)} body hash(es) in the"
            f" cassette: {preview}{suffix}. Re-record the cassette with record.py."
        )
        self.missing_hashes = missing_hashes


class LabelError(Exception):
    pass


class CassetteError(Exception):
    pass


@dataclass(frozen=True)
class Cassette:
    model: str
    dimensions: int
    input_prefix: str | None
    thresholds: dict[str, float | int | str]
    vectors: dict[str, np.ndarray]


@dataclass(frozen=True)
class PairResult:
    name: str
    kind: str
    a: str
    b: str
    similarity: float
    rerank_score: float
    same_cluster: bool


@dataclass(frozen=True)
class BaselineReport:
    model: str
    dimensions: int
    thresholds: dict[str, float | int | str]
    corpus: dict[str, int]
    totals: dict[str, float | int | None | dict[str, dict[str, float | int | None]]]
    pairs: list[PairResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "dimensions": self.dimensions,
            "thresholds": self.thresholds,
            "corpus": self.corpus,
            "totals": {key: _round_floats(value) for key, value in self.totals.items()},
            "pairs": [
                {
                    "name": p.name,
                    "kind": p.kind,
                    "a": p.a,
                    "b": p.b,
                    "similarity": round(p.similarity, 4),
                    "rerank_score": round(p.rerank_score, 4),
                    "same_cluster": p.same_cluster,
                }
                for p in self.pairs
            ],
        }


def resolve_model(model_key: str) -> ModelProfile:
    if model_key not in MODELS:
        valid = ", ".join(sorted(MODELS))
        raise ValueError(f"invalid model {model_key!r}; must be one of {valid}")
    return MODELS[model_key]


def build_config(
    db_file: Path,
    representation: str = REPRESENTATION,
    model_key: str = DEFAULT_MODEL,
) -> Config:
    profile = resolve_model(model_key)
    parent = db_file.parent
    return Config(
        source_dir=CORPUS_DIR,
        source_dir_exclude=[],
        db_file=db_file,
        report_dir=parent / "report",
        ignore_file=parent / "slopo.ignore.txt",
        embedding_model=profile.model,
        embedding_dimensions=profile.dimensions,
        embedding_api_key=None,
        embedding_params={},
        # Ollama opens one connection per embedded input and disables keep-alive, so a
        # fast run exhausts Windows sockets. Pace the recording; replay never embeds.
        embedding_batch_size=25,
        embedding_batch_chars=100_000,
        embedding_request_delay=2,
        similarity_threshold=SIMILARITY_THRESHOLD,
        rerank_threshold=RERANK_THRESHOLD,
        body_node_count_threshold=BODY_NODE_COUNT_THRESHOLD,
        representation=representation,
        embedding_input_prefix=profile.input_prefix,
    )


def index_corpus(
    db_file: Path,
    representation: str = REPRESENTATION,
    model_key: str = DEFAULT_MODEL,
) -> sqlite3.Connection:
    cfg = build_config(db_file, representation=representation, model_key=model_key)
    conn = create_db(cfg)
    run_index(conn, cfg, lambda _message: None)
    return conn


def _slug(model: str) -> str:
    return model.replace("/", "-").replace(":", "-")


def _representation_suffix(representation: str) -> str:
    return "" if representation == "raw" else f"-{representation}"


def cassette_path(model_key: str = DEFAULT_MODEL, representation: str = "raw") -> Path:
    profile = resolve_model(model_key)
    return (
        EMBEDDINGS_DIR
        / f"{_slug(profile.model)}{_representation_suffix(representation)}.json"
    )


def _model_suffix(model_key: str) -> str:
    resolve_model(model_key)  # validates, error naming known keys
    return "" if model_key == DEFAULT_MODEL else f"-{model_key}"


def snapshot_path(
    representation: str = REPRESENTATION, model_key: str = DEFAULT_MODEL
) -> Path:
    suffix = _model_suffix(model_key) + _representation_suffix(representation)
    if not suffix:
        return SNAPSHOT_FILE
    return BASELINE_DIR / f"snapshot{suffix}.json"


def save_cassette(
    path: Path, vectors: dict[str, list[float]], model_key: str = DEFAULT_MODEL
) -> None:
    profile = resolve_model(model_key)
    encoded_vectors = {
        body_hash: base64.b64encode(
            np.asarray(vector, dtype=np.float32).tobytes()
        ).decode("ascii")
        for body_hash, vector in vectors.items()
    }
    payload = {
        "model": profile.model,
        "dimensions": profile.dimensions,
        "input_prefix": profile.input_prefix,
        "thresholds": {
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "rerank_threshold": RERANK_THRESHOLD,
            "body_node_count_threshold": BODY_NODE_COUNT_THRESHOLD,
        },
        "vectors": encoded_vectors,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cassette(path: Path, model_key: str = DEFAULT_MODEL) -> Cassette:
    profile = resolve_model(model_key)
    if not path.is_file():
        raise CassetteError(f"no cassette at {path}; run record.py to generate one")

    raw = json.loads(path.read_text(encoding="utf-8"))

    if raw["model"] != profile.model:
        raise CassetteError(
            f"cassette model {raw['model']!r} does not match pinned {profile.model!r}"
        )
    if raw["dimensions"] != profile.dimensions:
        raise CassetteError(
            f"cassette dimensions {raw['dimensions']} do not match pinned"
            f" {profile.dimensions}"
        )
    # embed_hash does not cover the prefix (see src/slopo/db.py), so a cassette
    # recorded under a different prefix would otherwise be silently accepted.
    # An absent field predates this check and must not be read as "no prefix".
    if "input_prefix" not in raw:
        raise CassetteError(
            f"cassette at {path} has no recorded input_prefix; re-record it"
            " with record.py"
        )
    if raw["input_prefix"] != profile.input_prefix:
        raise CassetteError(
            f"cassette input_prefix {raw['input_prefix']!r} does not match pinned"
            f" {profile.input_prefix!r}; re-record it with record.py"
        )

    vectors = {
        body_hash: np.frombuffer(base64.b64decode(encoded), dtype=np.float32)
        for body_hash, encoded in raw["vectors"].items()
    }
    return Cassette(
        model=raw["model"],
        dimensions=raw["dimensions"],
        input_prefix=raw["input_prefix"],
        thresholds=raw["thresholds"],
        vectors=vectors,
    )


def seed_embeddings(conn: sqlite3.Connection, cassette: Cassette) -> None:
    rows = conn.execute("SELECT DISTINCT embed_hash FROM code_units").fetchall()
    embed_hashes = [row[0] for row in rows]

    missing = [h for h in embed_hashes if h not in cassette.vectors]
    if missing:
        raise MissingEmbeddingsError(missing)

    with conn:
        conn.executemany(
            "INSERT INTO embeddings (embed_hash, embedding) VALUES (?, ?)",
            [
                (h, cassette.vectors[h].astype(np.float32).tobytes())
                for h in embed_hashes
            ],
        )


def load_all_units(conn: sqlite3.Connection) -> dict[int, UnitRecord]:
    ids = {row[0] for row in conn.execute("SELECT id FROM code_units").fetchall()}
    return load_units(conn, ids)


def resolve_labels(
    units: dict[int, UnitRecord], pairs: list[dict[str, str]]
) -> dict[str, int]:
    labels = {label for entry in pairs for label in (entry["a"], entry["b"])}
    return {label: _resolve_one_label(units, label) for label in labels}


def _resolve_one_label(units: dict[int, UnitRecord], label: str) -> int:
    if "::" not in label:
        raise LabelError(f"malformed label {label!r}, expected 'path::name'")
    path, name = label.split("::", 1)

    matches = [
        uid for uid, u in units.items() if u.file_path == path and u.name == name
    ]
    if not matches:
        raise LabelError(f"label {label!r} matches no unit")
    if len(matches) > 1:
        raise LabelError(f"label {label!r} matches multiple units: {sorted(matches)}")
    return matches[0]


def cluster_membership(
    clusters: list[Cluster], duplicates: dict[int, list[UnitRecord]]
) -> dict[int, int]:
    membership: dict[int, int] = {}
    for index, cluster in enumerate(clusters):
        for unit_id in cluster.unit_ids:
            membership[unit_id] = index
        # Exact copies were folded out of unit_ids by fold_exact_duplicates and
        # moved into `duplicates`; they still belong to their primary's cluster.
        for unit_id in cluster.unit_ids:
            for dup in duplicates.get(unit_id, []):
                membership[dup.unit_id] = index
    return membership


def separation_margin(
    duplicate_sims: list[float], distinct_sims: list[float]
) -> float | None:
    if not duplicate_sims or not distinct_sims:
        return None
    return min(duplicate_sims) - max(distinct_sims)


def zero_fp_threshold_floor(distinct_sims: list[float]) -> float | None:
    """Highest similarity among distinct pairs; any threshold strictly above
    it yields zero false positives on this corpus."""
    if not distinct_sims:
        return None
    return max(distinct_sims)


def max_recall_at_zero_fp(
    duplicate_sims: list[float], distinct_sims: list[float]
) -> float | None:
    """Best recall reachable without a single false positive, whatever
    threshold is chosen: the fraction of duplicate similarities strictly
    above the zero-FP floor."""
    floor = zero_fp_threshold_floor(distinct_sims)
    if floor is None or not duplicate_sims:
        return None
    return sum(1 for s in duplicate_sims if s > floor) / len(duplicate_sims)


_LANGUAGE_BY_SUFFIX = {".py": "python", ".ts": "typescript"}


def unit_language(label: str) -> str:
    path = label.split("::", 1)[0]
    return _LANGUAGE_BY_SUFFIX.get(Path(path).suffix, "unknown")


def pair_language(a: str, b: str) -> str:
    lang_a = unit_language(a)
    lang_b = unit_language(b)
    return lang_a if lang_a == lang_b else "cross"


def group_by_language(
    pairs: list[PairResult],
) -> dict[str, dict[str, float | int | None]]:
    groups: dict[str, list[PairResult]] = {}
    for pair in pairs:
        groups.setdefault(pair_language(pair.a, pair.b), []).append(pair)

    result: dict[str, dict[str, float | int | None]] = {}
    for language in sorted(groups):
        lang_pairs = groups[language]
        duplicate_results = [p for p in lang_pairs if p.kind == "duplicate"]
        distinct_results = [p for p in lang_pairs if p.kind == "distinct"]
        duplicate_sims = [p.similarity for p in duplicate_results]
        distinct_sims = [p.similarity for p in distinct_results]
        recall = (
            sum(1 for p in duplicate_results if p.same_cluster) / len(duplicate_results)
            if duplicate_results
            else 0.0
        )
        result[language] = {
            "duplicates": len(duplicate_results),
            "distinct": len(distinct_results),
            "recall": recall,
            "false_positives": sum(1 for p in distinct_results if p.same_cluster),
            "separation_margin": separation_margin(duplicate_sims, distinct_sims),
            "max_recall_at_zero_fp": max_recall_at_zero_fp(
                duplicate_sims, distinct_sims
            ),
        }
    return result


def _round_floats(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: _round_floats(v) for key, v in value.items()}
    return value


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def run_baseline(
    cassette_file: Path | None = None,
    representation: str = REPRESENTATION,
    model_key: str = DEFAULT_MODEL,
) -> BaselineReport:
    if representation not in LEVELS:
        valid = ", ".join(repr(level) for level in LEVELS)
        raise ValueError(
            f"invalid representation {representation!r}; must be one of {valid}"
        )
    profile = resolve_model(model_key)
    cassette = load_cassette(
        cassette_file
        or cassette_path(model_key=model_key, representation=representation),
        model_key=model_key,
    )
    expectations = yaml.safe_load(EXPECTATIONS_FILE.read_text(encoding="utf-8"))
    duplicate_entries = expectations.get("duplicates", [])
    distinct_entries = expectations.get("distinct", [])

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "baseline.db"
        conn = index_corpus(db_file, representation=representation, model_key=model_key)
        try:
            seed_embeddings(conn, cassette)

            units = load_all_units(conn)
            embeddings = load_embeddings(conn)

            pairs = find_similar_pairs(embeddings, SIMILARITY_THRESHOLD, _BLOCK_SIZE)
            pairs = exclude_overlapping_pairs(pairs, units)

            clusters = build_clusters(pairs)
            reranked_pairs = rerank_all_clusters(clusters, pairs, units)
            clusters = reorder_clusters(clusters, reranked_pairs)
            clusters = filter_clusters(clusters, RERANK_THRESHOLD)
            clusters, duplicates = fold_exact_duplicates(clusters, units)
            membership = cluster_membership(clusters, duplicates)

            labels = resolve_labels(units, duplicate_entries + distinct_entries)

            pair_results: list[PairResult] = []
            for kind, entries in (
                ("duplicate", duplicate_entries),
                ("distinct", distinct_entries),
            ):
                for entry in entries:
                    unit_a = labels[entry["a"]]
                    unit_b = labels[entry["b"]]
                    similarity = _cosine_similarity(
                        embeddings[unit_a], embeddings[unit_b]
                    )
                    rerank_score = rerank_pair_score(
                        SimilarPair(
                            similarity=similarity, unit_id_a=unit_a, unit_id_b=unit_b
                        ),
                        units[unit_a],
                        units[unit_b],
                    )
                    same_cluster = (
                        unit_a in membership
                        and unit_b in membership
                        and membership[unit_a] == membership[unit_b]
                    )
                    pair_results.append(
                        PairResult(
                            name=entry["name"],
                            kind=kind,
                            a=entry["a"],
                            b=entry["b"],
                            similarity=similarity,
                            rerank_score=rerank_score,
                            same_cluster=same_cluster,
                        )
                    )

            duplicate_results = [p for p in pair_results if p.kind == "duplicate"]
            distinct_results = [p for p in pair_results if p.kind == "distinct"]
            recall = (
                sum(1 for p in duplicate_results if p.same_cluster)
                / len(duplicate_results)
                if duplicate_results
                else 0.0
            )
            false_positives = sum(1 for p in distinct_results if p.same_cluster)
            duplicate_sims = [p.similarity for p in duplicate_results]
            distinct_sims = [p.similarity for p in distinct_results]
            margin = separation_margin(duplicate_sims, distinct_sims)
            zero_fp_floor = zero_fp_threshold_floor(distinct_sims)
            best_recall = max_recall_at_zero_fp(duplicate_sims, distinct_sims)

            files_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            units_count = conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0]
            distinct_bodies = conn.execute(
                "SELECT COUNT(DISTINCT body_hash) FROM code_units"
            ).fetchone()[0]
            exact_copies = count_exact_copies(conn)

            return BaselineReport(
                model=profile.model,
                dimensions=profile.dimensions,
                thresholds={
                    "similarity_threshold": SIMILARITY_THRESHOLD,
                    "rerank_threshold": RERANK_THRESHOLD,
                    "body_node_count_threshold": BODY_NODE_COUNT_THRESHOLD,
                    "representation": representation,
                },
                corpus={
                    "files": files_count,
                    "units": units_count,
                    "distinct_bodies": distinct_bodies,
                    "exact_copies": exact_copies,
                },
                totals={
                    "clusters": len(clusters),
                    "recall": recall,
                    "false_positives": false_positives,
                    "separation_margin": margin,
                    "zero_fp_threshold_floor": zero_fp_floor,
                    "max_recall_at_zero_fp": best_recall,
                    "by_language": group_by_language(pair_results),
                },
                pairs=pair_results,
            )
        finally:
            conn.close()
