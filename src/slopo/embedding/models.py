from typing import NamedTuple


class UnembeddedUnit(NamedTuple):
    embed_hash: str
    embed_body: str


class EmbeddedUnit(NamedTuple):
    embed_hash: str
    vector: list[float]
