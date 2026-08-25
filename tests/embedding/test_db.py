import sqlite3

import numpy as np

from slopo.embedding.db import (
    count_unembedded_units,
    load_embeddings,
    load_next_batch,
    save_embeddings,
)
from slopo.embedding.models import EmbeddedUnit

_UNIT_COLUMNS = (
    "id, file_id, name, body, start_line, end_line, body_node_count, body_hash,"
    " embed_body, embed_hash"
)

# --- count_unembedded_units ---


def test_count_unembedded_units_ignores_embedded_hashes(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'b', 'b', 1, 2, 3, 'hashB', 'b', 'hashB');
        INSERT INTO embeddings (embed_hash, embedding) VALUES ('hashB', X'0000803f');
    """)

    assert count_unembedded_units(conn) == 1


def test_count_unembedded_units_counts_each_hash_once(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
    """)

    assert count_unembedded_units(conn) == 1


def test_count_unembedded_units_keys_on_embed_hash_not_body_hash(
    conn: sqlite3.Connection,
):
    # Different raw bodies, same embed_hash: normalization folded them together,
    # so the embedding cache must see one hash to embed, not two.
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'body-a', 1, 2, 3, 'raw-a', 'NORM', 'shared');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'b', 'body-b', 1, 2, 3, 'raw-b', 'NORM', 'shared');
    """)

    assert count_unembedded_units(conn) == 1


# --- load_next_batch ---


def test_load_next_batch_skips_already_embedded_hashes(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'b', 'b', 1, 2, 3, 'hashB', 'b', 'hashB');
        INSERT INTO embeddings (embed_hash, embedding) VALUES ('hashA', X'0000803f');
    """)

    batch = load_next_batch(conn, max_items=10, max_chars=10_000)

    assert [u.embed_hash for u in batch] == ["hashB"]


def test_load_next_batch_emits_each_hash_once(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
    """)

    batch = load_next_batch(conn, max_items=10, max_chars=10_000)

    assert [u.embed_hash for u in batch] == ["hashA"]


def test_load_next_batch_sends_embed_body_not_raw_body(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'raw text', 1, 2, 3, 'hashA', 'NORMALIZED', 'ehash');
    """)

    batch = load_next_batch(conn, max_items=10, max_chars=10_000)

    assert [(u.embed_hash, u.embed_body) for u in batch] == [("ehash", "NORMALIZED")]


def test_load_next_batch_dedupes_two_units_sharing_embed_hash_with_different_bodies(
    conn: sqlite3.Connection,
):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'body-a', 1, 2, 3, 'raw-a', 'NORM', 'shared');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'b', 'body-b', 1, 2, 3, 'raw-b', 'NORM', 'shared');
    """)

    batch = load_next_batch(conn, max_items=10, max_chars=10_000)

    assert [u.embed_hash for u in batch] == ["shared"]


# --- load_embeddings ---


def test_load_embeddings_for_all_embedded_units(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (2, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (3, 1, 'b', 'b', 1, 2, 3, 'hashB', 'b', 'hashB');
        INSERT INTO embeddings (embed_hash, embedding) VALUES ('hashA', X'0000803f');
    """)

    assert sorted(load_embeddings(conn)) == [1, 2]


def test_load_embeddings_joins_on_embed_hash_not_body_hash(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'body-a', 1, 2, 3, 'raw-a', 'NORM', 'shared');
        INSERT INTO embeddings (embed_hash, embedding) VALUES ('shared', X'0000803f');
    """)

    assert sorted(load_embeddings(conn)) == [1]


# --- save_embeddings ---


def test_save_then_load_embeddings_round_trips_the_vector(conn: sqlite3.Connection):
    conn.executescript(f"""
        INSERT INTO files (id, path, mtime) VALUES (1, 'File.java', 0);
        INSERT INTO code_units ({_UNIT_COLUMNS})
            VALUES (1, 1, 'a', 'a', 1, 2, 3, 'hashA', 'a', 'hashA');
    """)

    save_embeddings(conn, [EmbeddedUnit(embed_hash="hashA", vector=[1.0, 2.0, 3.0])])

    loaded = load_embeddings(conn)
    assert np.array_equal(loaded[1], np.array([1.0, 2.0, 3.0], dtype=np.float32))
