from dataclasses import replace
from pathlib import Path

import pytest

from slopo import db
from slopo.config import Config
from slopo.db import ConfigurationMismatchError, chunked, create_db, open_db


def test_yields_nothing_for_empty_input():
    assert list(chunked([])) == []


def test_yields_single_chunk_when_input_fits(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "_MAX_SQL_VARIABLES", 3)

    assert list(chunked([1, 2])) == [[1, 2]]


def test_splits_input_across_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db, "_MAX_SQL_VARIABLES", 2)

    assert list(chunked([1, 2, 3, 4, 5])) == [[1, 2], [3, 4], [5]]


def test_exact_multiple_leaves_no_trailing_empty_chunk(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(db, "_MAX_SQL_VARIABLES", 2)

    assert list(chunked([1, 2, 3, 4])) == [[1, 2], [3, 4]]


# --- create_db / open_db metadata checks ---


def _config(tmp_path: Path, **overrides) -> Config:
    cfg = Config(
        source_dir=tmp_path,
        source_dir_exclude=[],
        db_file=tmp_path / "slopo.db",
        report_dir=tmp_path / "slopo-report",
        ignore_file=tmp_path / "slopo.ignore.txt",
        embedding_model="openai/text-embedding-3-small",
        embedding_dimensions=3,
        embedding_api_key=None,
        embedding_params={},
        embedding_batch_size=100,
        embedding_batch_chars=100_000,
        embedding_request_delay=0,
        similarity_threshold=0.92,
        rerank_threshold=0.94,
        body_node_count_threshold=10,
        representation="raw",
        embedding_input_prefix=None,
    )
    return replace(cfg, **overrides)


def test_database_created_with_one_representation_refuses_another(tmp_path: Path):
    cfg = _config(tmp_path, representation="raw")
    create_db(cfg).close()

    other = _config(tmp_path, representation="rename_locals")
    with pytest.raises(ConfigurationMismatchError) as exc:
        open_db(other).close()

    assert exc.value.field == "representation"
    assert exc.value.stored == "raw"
    assert exc.value.current == "rename_locals"


def test_database_reopens_fine_with_the_same_representation(tmp_path: Path):
    cfg = _config(tmp_path, representation="rename_all")
    create_db(cfg).close()

    conn = open_db(cfg)
    conn.close()


def test_database_created_with_one_prefix_refuses_another(tmp_path: Path):
    cfg = _config(tmp_path, embedding_input_prefix="Find equivalent code:\n")
    create_db(cfg).close()

    other = _config(tmp_path, embedding_input_prefix="Find similar code:\n")
    with pytest.raises(ConfigurationMismatchError) as exc:
        open_db(other).close()

    assert exc.value.field == "embedding_input_prefix"
    assert exc.value.stored == "Find equivalent code:\n"
    assert exc.value.current == "Find similar code:\n"


def test_database_created_without_prefix_reopens_fine_without_one(tmp_path: Path):
    cfg = _config(tmp_path, embedding_input_prefix=None)
    create_db(cfg).close()

    conn = open_db(cfg)
    conn.close()
