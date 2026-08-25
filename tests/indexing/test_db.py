import sqlite3

import pytest

from slopo import db
from slopo.indexing.db import (
    delete_file_units,
    delete_files,
    insert_file_units,
    prune_orphan_embeddings,
)
from slopo.indexing.parsing.base import CodeUnit


def _insert_file(conn: sqlite3.Connection) -> int:
    conn.execute("INSERT INTO files (path, mtime) VALUES ('Calculator.java', 0)")
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _unit(
    name: str,
    body: str,
    start_line: int,
    end_line: int,
    body_node_count: int,
    body_hash: str,
    embed_body: str | None = None,
    embed_hash: str | None = None,
) -> CodeUnit:
    return CodeUnit(
        name=name,
        body=body,
        start_line=start_line,
        end_line=end_line,
        body_node_count=body_node_count,
        body_hash=body_hash,
        embed_body=embed_body if embed_body is not None else body,
        embed_hash=embed_hash if embed_hash is not None else body_hash,
    )


def test_inserts_unit_fields_into_matching_columns(conn: sqlite3.Connection):
    file_id = _insert_file(conn)
    unit = _unit(
        "increment",
        "int increment(int a) { return a + 1; }",
        2,
        4,
        7,
        "abc123",
        embed_body="INCREMENT(int a) { return a + 1; }",
        embed_hash="norm123",
    )

    insert_file_units(conn, file_id, [unit])

    row = conn.execute(
        "SELECT file_id, name, body, start_line, end_line, body_node_count,"
        " body_hash, embed_body, embed_hash"
        " FROM code_units"
    ).fetchone()
    assert row == (
        file_id,
        "increment",
        "int increment(int a) { return a + 1; }",
        2,
        4,
        7,
        "abc123",
        "INCREMENT(int a) { return a + 1; }",
        "norm123",
    )


def test_inserts_all_units_with_sequential_ids(conn: sqlite3.Connection):
    file_id = _insert_file(conn)
    units = [
        _unit("increment", "body1", 1, 2, 3, "hash1"),
        _unit("decrement", "body2", 4, 5, 6, "hash2"),
    ]

    insert_file_units(conn, file_id, units)

    rows = conn.execute("SELECT id, name FROM code_units ORDER BY id").fetchall()
    assert rows == [(1, "increment"), (2, "decrement")]


def test_deletes_file_and_its_units(conn: sqlite3.Connection):
    file_id = _insert_file(conn)
    insert_file_units(conn, file_id, [_unit("dup", "body", 1, 2, 3, "hash")])

    delete_files(conn, [file_id])

    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0] == 0


def test_deletes_files_spanning_multiple_chunks(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(db, "_MAX_SQL_VARIABLES", 2)
    file_ids = []
    for i in range(5):
        conn.execute("INSERT INTO files (path, mtime) VALUES (?, 0)", (f"F{i}.java",))
        file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        insert_file_units(conn, file_id, [_unit("a", "body", 1, 2, 3, f"h{i}")])
        file_ids.append(file_id)

    delete_files(conn, file_ids)

    assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0] == 0


def test_deletes_units_of_modified_file(conn: sqlite3.Connection):
    file_id = _insert_file(conn)
    insert_file_units(conn, file_id, [_unit("dup", "body", 1, 2, 3, "hash")])

    delete_file_units(conn, file_id)

    assert conn.execute("SELECT COUNT(*) FROM code_units").fetchone()[0] == 0


def test_prune_removes_embeddings_with_no_remaining_units(conn: sqlite3.Connection):
    conn.execute(
        "INSERT INTO embeddings (embed_hash, embedding) VALUES ('gone', X'0000803f')"
    )

    prune_orphan_embeddings(conn)

    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 0


def test_prune_keeps_embedding_while_a_unit_shares_its_hash(conn: sqlite3.Connection):
    file_id = _insert_file(conn)
    insert_file_units(conn, file_id, [_unit("a", "body", 1, 2, 3, "shared")])
    conn.execute(
        "INSERT INTO embeddings (embed_hash, embedding) VALUES ('shared', X'0000803f')"
    )

    prune_orphan_embeddings(conn)

    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1


def test_prune_keys_on_embed_hash_not_body_hash(conn: sqlite3.Connection):
    # Two units share embed_hash but not body_hash (normalization folded distinct
    # bodies together); pruning must key on embed_hash, the embedding cache's key.
    file_id = _insert_file(conn)
    insert_file_units(
        conn,
        file_id,
        [
            _unit(
                "a", "body-a", 1, 2, 3, "raw-a", embed_body="NORM", embed_hash="shared"
            )
        ],
    )
    conn.execute(
        "INSERT INTO embeddings (embed_hash, embedding) VALUES ('shared', X'0000803f')"
    )

    prune_orphan_embeddings(conn)

    assert conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0] == 1
