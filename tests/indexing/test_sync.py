import os
import sqlite3
from pathlib import Path

import pytest

from slopo.indexing.parsing import base
from slopo.indexing.parsing.base import hash_body
from slopo.indexing.sync import SyncStats, sync_index

# Two methods, so each file yields two code units.
_JAVA = """\
class Calculator {
    int increment(int a) {
        return a + 1;
    }

    int decrement(int a) {
        return a - 1;
    }
}
"""


def _indexed_files(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT path FROM files").fetchall()
    return {row[0] for row in rows}


def _unit_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0]


def test_indexes_new_files_on_first_run(tmp_path: Path, conn: sqlite3.Connection):
    (tmp_path / "Calculator.java").write_text(_JAVA)
    (tmp_path / "Greeter.java").write_text(_JAVA)

    result = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )

    assert result == SyncStats(
        indexed_files=2, skipped_files=0, indexed_units=4, removed_files=0
    )
    assert _indexed_files(conn) == {"Calculator.java", "Greeter.java"}
    assert _unit_count(conn) == 4


def test_skips_unchanged_file_on_reindex(tmp_path: Path, conn: sqlite3.Connection):
    (tmp_path / "Calculator.java").write_text(_JAVA)

    result_first = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )
    assert result_first == SyncStats(
        indexed_files=1, skipped_files=0, indexed_units=2, removed_files=0
    )

    result_second = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )

    assert result_second == SyncStats(
        indexed_files=0, skipped_files=1, indexed_units=0, removed_files=0
    )
    assert _indexed_files(conn) == {"Calculator.java"}
    assert _unit_count(conn) == 2


def test_update_a_file_with_a_newer_mtime_on_reindex(
    tmp_path: Path, conn: sqlite3.Connection
):
    path = tmp_path / "Calculator.java"
    path.write_text(_JAVA)

    result_first = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )
    assert result_first == SyncStats(
        indexed_files=1, skipped_files=0, indexed_units=2, removed_files=0
    )

    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 10))
    result_second = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )

    assert result_second == SyncStats(
        indexed_files=1, skipped_files=0, indexed_units=2, removed_files=0
    )
    assert _indexed_files(conn) == {"Calculator.java"}
    assert _unit_count(conn) == 2


def test_removes_units_when_a_file_is_deleted(tmp_path: Path, conn: sqlite3.Connection):
    (tmp_path / "Calculator.java").write_text(_JAVA)
    gone = tmp_path / "Greeter.java"
    gone.write_text(_JAVA)

    result_first = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )
    assert result_first == SyncStats(
        indexed_files=2, skipped_files=0, indexed_units=4, removed_files=0
    )

    gone.unlink()
    result_second = sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )

    assert result_second == SyncStats(
        indexed_files=0, skipped_files=1, indexed_units=0, removed_files=1
    )
    assert _indexed_files(conn) == {"Calculator.java"}
    assert _unit_count(conn) == 2


def test_raw_representation_stores_embed_body_identical_to_body(
    tmp_path: Path, conn: sqlite3.Connection
):
    (tmp_path / "Calculator.java").write_text(_JAVA)

    sync_index(
        conn, tmp_path, body_node_count_threshold=0, exclude=[], representation="raw"
    )

    rows = conn.execute(
        "SELECT body, embed_body, body_hash, embed_hash FROM code_units"
    ).fetchall()
    assert rows
    for body, embed_body, body_hash, embed_hash in rows:
        assert embed_body == body
        assert embed_hash == body_hash


def test_normalized_representation_stores_normalizer_output(
    tmp_path: Path, conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        base, "normalize", lambda source, node, language, level: "NORMALIZED"
    )
    (tmp_path / "Calculator.java").write_text(_JAVA)

    sync_index(
        conn,
        tmp_path,
        body_node_count_threshold=0,
        exclude=[],
        representation="rename_locals",
    )

    rows = conn.execute("SELECT embed_body, embed_hash FROM code_units").fetchall()
    assert rows
    for embed_body, embed_hash in rows:
        assert embed_body == "NORMALIZED"
        assert embed_hash == hash_body("NORMALIZED")
