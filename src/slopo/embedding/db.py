import sqlite3

import numpy as np

from slopo.embedding.batching import trim_to_char_limit
from slopo.embedding.models import EmbeddedUnit, UnembeddedUnit


def count_unembedded_units(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(DISTINCT embed_hash) FROM code_units
        WHERE embed_hash NOT IN (SELECT embed_hash FROM embeddings)
        """
    ).fetchone()
    return row[0]


def load_next_batch(
    conn: sqlite3.Connection, max_items: int, max_chars: int
) -> list[UnembeddedUnit]:
    rows = conn.execute(
        """
        SELECT embed_hash, MIN(embed_body)
        FROM code_units
        WHERE embed_hash NOT IN (SELECT embed_hash FROM embeddings)
        GROUP BY embed_hash
        LIMIT ?
    """,
        (max_items,),
    ).fetchall()

    units = [UnembeddedUnit(embed_hash=row[0], embed_body=row[1]) for row in rows]
    return trim_to_char_limit(units, max_chars)


def save_embeddings(conn: sqlite3.Connection, embeddings: list[EmbeddedUnit]) -> None:
    conn.executemany(
        "INSERT INTO embeddings (embed_hash, embedding) VALUES (?, ?)",
        [
            (e.embed_hash, np.asarray(e.vector, dtype=np.float32).tobytes())
            for e in embeddings
        ],
    )


def load_embeddings(conn: sqlite3.Connection) -> dict[int, np.ndarray]:
    rows = conn.execute(
        """
        SELECT cu.id, e.embedding
        FROM code_units cu
        JOIN embeddings e ON e.embed_hash = cu.embed_hash
        """
    ).fetchall()
    return {row[0]: np.frombuffer(row[1], dtype=np.float32) for row in rows}
