import sqlite3
from typing import Iterator

import numpy as np
import pytest

from tests.baseline.harness import (
    DIMENSIONS,
    Cassette,
    CassetteError,
    LabelError,
    MissingEmbeddingsError,
    cluster_membership,
    load_cassette,
    resolve_labels,
    save_cassette,
    seed_embeddings,
    separation_margin,
)
from slopo.analysis.models import Cluster, UnitRecord
from slopo.schema import create_schema


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    create_schema(connection)
    yield connection
    connection.close()


def _unit(
    unit_id: int, body_hash: str, name: str = "f", path: str = "a.py"
) -> UnitRecord:
    return UnitRecord(
        unit_id=unit_id,
        file_path=path,
        name=name,
        start_line=1,
        end_line=2,
        body="body",
        body_hash=body_hash,
    )


# --- cluster_membership ---


def test_cluster_membership_plain_cluster():
    clusters = [Cluster([1, 2], 0.9, 0.95)]
    assert cluster_membership(clusters, {}) == {1: 0, 2: 0}


def test_cluster_membership_folds_exact_duplicates_into_primarys_cluster():
    # The trap: unit 3 was folded out of unit_ids into duplicates[1] by
    # fold_exact_duplicates, but it must still count as belonging to cluster 0.
    clusters = [Cluster([1, 2], 0.9, 0.95)]
    duplicates = {1: [_unit(3, "a")]}
    assert cluster_membership(clusters, duplicates) == {1: 0, 2: 0, 3: 0}


def test_cluster_membership_unit_in_no_cluster_is_absent():
    clusters = [Cluster([1], 0.9, 0.95)]
    membership = cluster_membership(clusters, {})
    assert 99 not in membership


def test_cluster_membership_two_clusters_keep_distinct_indices():
    clusters = [Cluster([1, 2], 0.9, 0.95), Cluster([3, 4], 0.9, 0.95)]
    duplicates = {3: [_unit(5, "a")]}
    membership = cluster_membership(clusters, duplicates)
    assert membership == {1: 0, 2: 0, 3: 1, 4: 1, 5: 1}


# --- resolve_labels ---


def test_resolve_labels_happy_path():
    units = {
        1: _unit(1, "a", name="foo", path="x.py"),
        2: _unit(2, "b", name="bar", path="y.py"),
    }
    pairs = [{"a": "x.py::foo", "b": "y.py::bar"}]
    resolved = resolve_labels(units, pairs)
    assert resolved == {"x.py::foo": 1, "y.py::bar": 2}


def test_resolve_labels_unknown_label_raises_naming_it():
    units = {1: _unit(1, "a", name="foo", path="x.py")}
    pairs = [{"a": "x.py::foo", "b": "x.py::missing"}]
    with pytest.raises(LabelError, match="x.py::missing"):
        resolve_labels(units, pairs)


def test_resolve_labels_ambiguous_name_raises():
    units = {
        1: _unit(1, "a", name="foo", path="x.py"),
        2: _unit(2, "b", name="foo", path="x.py"),
    }
    pairs = [{"a": "x.py::foo", "b": "x.py::foo"}]
    with pytest.raises(LabelError, match="x.py::foo"):
        resolve_labels(units, pairs)


# --- separation_margin ---


def test_separation_margin_normal_case():
    assert separation_margin([0.95, 0.98], [0.80, 0.85]) == pytest.approx(0.10)


def test_separation_margin_negative_when_sets_overlap():
    assert separation_margin([0.80, 0.90], [0.85, 0.95]) == pytest.approx(-0.15)


def test_separation_margin_none_on_empty_side():
    assert separation_margin([], [0.9]) is None
    assert separation_margin([0.9], []) is None
    assert separation_margin([], []) is None


# --- cassette round-trip ---


def test_cassette_round_trip_preserves_vectors_at_float32_precision(tmp_path):
    vectors = {
        "h1": [0.1, 0.2, 0.3] * (DIMENSIONS // 3) + [0.0] * (DIMENSIONS % 3),
        "h2": [-1.0, 1.0, 0.5] * (DIMENSIONS // 3) + [0.0] * (DIMENSIONS % 3),
    }
    path = tmp_path / "cassette.json"

    save_cassette(path, vectors)
    cassette = load_cassette(path)

    for body_hash, original in vectors.items():
        expected = np.asarray(original, dtype=np.float32)
        np.testing.assert_array_equal(cassette.vectors[body_hash], expected)


def test_cassette_dimensions_mismatch_rejected(tmp_path):
    path = tmp_path / "cassette.json"
    save_cassette(path, {"h1": [0.0] * DIMENSIONS})

    raw = path.read_text(encoding="utf-8")
    raw = raw.replace(f'"dimensions": {DIMENSIONS}', '"dimensions": 1')
    path.write_text(raw, encoding="utf-8")

    with pytest.raises(CassetteError):
        load_cassette(path)


def test_cassette_missing_file_rejected(tmp_path):
    with pytest.raises(CassetteError):
        load_cassette(tmp_path / "absent.json")


# --- seed_embeddings ---


def test_seed_embeddings_raises_when_body_hash_missing_from_cassette(conn):
    conn.execute("INSERT INTO files (id, path, mtime) VALUES (1, 'a.py', 0.0)")
    conn.execute(
        "INSERT INTO code_units"
        " (id, file_id, name, body, start_line, end_line, body_node_count, body_hash)"
        " VALUES (1, 1, 'foo', 'def foo(): pass', 1, 1, 20, 'missing-hash')"
    )
    conn.commit()

    cassette = Cassette(
        model="m",
        dimensions=DIMENSIONS,
        thresholds={},
        vectors={"other-hash": np.zeros(3)},
    )

    with pytest.raises(MissingEmbeddingsError, match="missing-hash"):
        seed_embeddings(conn, cassette)

    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0
