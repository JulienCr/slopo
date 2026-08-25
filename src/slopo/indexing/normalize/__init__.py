"""Rewrites a function's source into a canonical form for embedding.

`normalize` collapses consistent identifier renaming (and, at the top
level, literal values) so that two functions that differ only by variable
names produce identical or near-identical text. See `engine.py` for the
byte-span substitution mechanics and `lang_*.py` for the per-language rules
on which identifiers are eligible.
"""

from __future__ import annotations

from tree_sitter import Node

from slopo.indexing.normalize import lang_python, lang_typescript
from slopo.indexing.normalize.engine import render, text_of

LEVELS: tuple[str, ...] = ("raw", "rename_locals", "rename_all", "rename_all_literals")

_PROFILES = {
    "python": lang_python.PROFILE,
    "typescript": lang_typescript.PROFILE,
    "javascript": lang_typescript.PROFILE,
}


def normalize(source: bytes, node: Node, language: str, level: str) -> str:
    if level not in LEVELS:
        raise ValueError(f"Unknown normalization level: {level!r}")
    if level == "raw":
        return text_of(source, node)
    profile = _PROFILES.get(language)
    if profile is None:
        return text_of(source, node)
    return render(source, node, profile, level)
