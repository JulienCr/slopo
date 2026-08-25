import sqlite3
from typing import Iterator

import numpy as np
import pytest

from tests.baseline.harness import (
    DIMENSIONS,
    REPRESENTATION,
    SNAPSHOT_FILE,
    Cassette,
    CassetteError,
    LabelError,
    MissingEmbeddingsError,
    PairResult,
    build_config,
    cassette_path,
    cluster_membership,
    group_by_language,
    load_cassette,
    max_recall_at_zero_fp,
    pair_language,
    resolve_labels,
    run_baseline,
    save_cassette,
    seed_embeddings,
    separation_margin,
    snapshot_path,
    unit_language,
    zero_fp_threshold_floor,
)
from slopo.analysis.models import Cluster, UnitRecord
from slopo.indexing.normalize import LEVELS
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
        " (id, file_id, name, body, start_line, end_line, body_node_count, body_hash,"
        "  embed_body, embed_hash)"
        " VALUES (1, 1, 'foo', 'def foo(): pass', 1, 1, 20, 'raw-hash',"
        "         'def foo(): pass', 'missing-hash')"
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


# --- zero_fp_threshold_floor / max_recall_at_zero_fp ---


def test_zero_fp_threshold_floor_is_the_max_distinct_similarity():
    assert zero_fp_threshold_floor([0.4, 0.7, 0.6]) == pytest.approx(0.7)


def test_zero_fp_threshold_floor_none_when_no_distinct_pairs():
    assert zero_fp_threshold_floor([]) is None


def test_max_recall_at_zero_fp_clean_split_reaches_full_recall():
    # Every duplicate similarity sits above the highest distinct one.
    duplicates = [0.9, 0.95, 1.0]
    distinct = [0.3, 0.5, 0.6]
    assert max_recall_at_zero_fp(duplicates, distinct) == pytest.approx(1.0)


def test_max_recall_at_zero_fp_overlapping_distributions():
    duplicates = [0.75, 0.8, 0.95, 1.0]
    distinct = [0.6, 0.7, 0.85]
    # Floor is 0.85; only 0.95 and 1.0 clear it: 2 of 4 duplicates.
    assert max_recall_at_zero_fp(duplicates, distinct) == pytest.approx(0.5)


def test_max_recall_at_zero_fp_tie_at_floor_does_not_count():
    # A duplicate sitting exactly on the floor is not "strictly greater".
    duplicates = [0.7, 0.9]
    distinct = [0.5, 0.7]
    assert max_recall_at_zero_fp(duplicates, distinct) == pytest.approx(0.5)


def test_max_recall_at_zero_fp_none_when_no_duplicates():
    assert max_recall_at_zero_fp([], [0.5]) is None


def test_max_recall_at_zero_fp_none_when_no_distinct():
    assert max_recall_at_zero_fp([0.5], []) is None


def test_max_recall_at_zero_fp_none_when_both_empty():
    assert max_recall_at_zero_fp([], []) is None


# --- unit_language / pair_language ---


def test_unit_language_python():
    assert unit_language("billing/invoices.py::calculate_invoice_total") == "python"


def test_unit_language_typescript():
    assert unit_language("src/utils.ts::formatDate") == "typescript"


def test_unit_language_unknown_extension():
    assert unit_language("config/app.toml::load") == "unknown"


def test_pair_language_same_language_is_that_language():
    assert pair_language("a.py::f", "b.py::g") == "python"
    assert pair_language("a.ts::f", "b.ts::g") == "typescript"


def test_pair_language_mixed_languages_is_cross():
    assert pair_language("a.py::f", "b.ts::g") == "cross"


# --- group_by_language ---


def _pair(
    kind: str, a: str, b: str, similarity: float, same_cluster: bool
) -> PairResult:
    return PairResult(
        name="p",
        kind=kind,
        a=a,
        b=b,
        similarity=similarity,
        rerank_score=0.0,
        same_cluster=same_cluster,
    )


def test_group_by_language_python_only():
    pairs = [
        _pair("duplicate", "a.py::f", "b.py::g", 0.95, True),
        _pair("distinct", "a.py::h", "b.py::i", 0.5, False),
    ]
    result = group_by_language(pairs)
    assert result == {
        "python": {
            "duplicates": 1,
            "distinct": 1,
            "recall": 1.0,
            "false_positives": 0,
            "separation_margin": pytest.approx(0.45),
            "max_recall_at_zero_fp": pytest.approx(1.0),
        }
    }


def test_group_by_language_mixed_python_and_typescript_split_separately():
    pairs = [
        _pair("duplicate", "a.py::f", "b.py::g", 0.95, True),
        _pair("duplicate", "a.ts::f", "b.ts::g", 0.6, False),
        _pair("distinct", "a.ts::h", "b.ts::i", 0.7, False),
    ]
    result = group_by_language(pairs)
    assert result["python"]["duplicates"] == 1
    assert result["python"]["distinct"] == 0
    assert result["python"]["separation_margin"] is None
    assert result["typescript"]["duplicates"] == 1
    assert result["typescript"]["distinct"] == 1
    assert result["typescript"]["recall"] == 0.0


def test_group_by_language_cross_language_pair_lands_under_cross():
    pairs = [_pair("duplicate", "a.py::f", "b.ts::g", 0.8, True)]
    result = group_by_language(pairs)
    assert set(result) == {"cross"}
    assert result["cross"]["duplicates"] == 1


def test_group_by_language_unknown_extension_grouped_as_unknown():
    pairs = [_pair("distinct", "a.toml::f", "b.toml::g", 0.4, False)]
    result = group_by_language(pairs)
    assert set(result) == {"unknown"}


def test_group_by_language_omits_languages_with_no_pairs():
    pairs = [_pair("duplicate", "a.py::f", "b.py::g", 0.95, True)]
    result = group_by_language(pairs)
    assert "typescript" not in result
    assert "cross" not in result


def test_group_by_language_keys_are_sorted():
    pairs = [
        _pair("duplicate", "a.ts::f", "b.ts::g", 0.9, True),
        _pair("duplicate", "a.py::f", "b.py::g", 0.9, True),
        _pair("duplicate", "a.py::f", "b.ts::g", 0.9, True),
    ]
    result = group_by_language(pairs)
    assert list(result.keys()) == sorted(result.keys())
    assert list(result.keys()) == ["cross", "python", "typescript"]


# --- build_config representation ---


def test_build_config_defaults_to_representation_constant(tmp_path):
    cfg = build_config(tmp_path / "db.sqlite")
    assert cfg.representation == REPRESENTATION


def test_build_config_honors_explicit_representation(tmp_path):
    cfg = build_config(tmp_path / "db.sqlite", representation="rename_all")
    assert cfg.representation == "rename_all"


def test_run_baseline_rejects_invalid_representation():
    with pytest.raises(ValueError, match="rename_locals"):
        run_baseline(representation="bogus")


# --- cassette_path ---


def test_cassette_path_raw_is_unsuffixed():
    path = cassette_path(model="m", representation="raw")
    assert path.name == "m.json"


def test_cassette_path_other_levels_are_distinct_from_raw_and_each_other():
    paths = {level: cassette_path(model="m", representation=level) for level in LEVELS}
    assert len(set(paths.values())) == len(LEVELS)
    assert paths["raw"].name == "m.json"
    for level in LEVELS:
        if level != "raw":
            assert paths[level].name != paths["raw"].name


# --- snapshot_path ---


def test_snapshot_path_raw_is_snapshot_file():
    assert snapshot_path("raw") == SNAPSHOT_FILE


def test_snapshot_path_other_levels_are_distinct_from_raw_and_each_other():
    paths = {level: snapshot_path(level) for level in LEVELS}
    assert len(set(paths.values())) == len(LEVELS)
    assert paths["raw"] == SNAPSHOT_FILE
    for level in LEVELS:
        if level != "raw":
            assert paths[level] != SNAPSHOT_FILE


def test_snapshot_and_cassette_suffixes_agree():
    for level in LEVELS:
        cassette_suffix = cassette_path(model="m", representation=level).stem[
            len("m") :
        ]
        snapshot_suffix = snapshot_path(level).stem[len("snapshot") :]
        assert cassette_suffix == snapshot_suffix
