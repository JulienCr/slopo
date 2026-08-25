import hashlib
from dataclasses import dataclass
from typing import Callable

from tree_sitter import Node

from slopo.indexing.normalize import normalize


@dataclass
class CodeUnit:
    name: str
    body: str
    start_line: int
    end_line: int
    body_node_count: int
    body_hash: str
    embed_body: str
    embed_hash: str


CodeParser = Callable[[bytes, str], list[CodeUnit]]


def hash_body(body: str) -> str:
    normalized = " ".join(body.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_code_unit(
    name: str,
    node: Node,
    source: bytes,
    body: str,
    body_node_count: int,
    language: str,
    representation: str,
) -> CodeUnit:
    embed_body = normalize(source, node, language, representation)
    return CodeUnit(
        name=name,
        body=body,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        body_node_count=body_node_count,
        body_hash=hash_body(body),
        embed_body=embed_body,
        embed_hash=hash_body(embed_body),
    )
