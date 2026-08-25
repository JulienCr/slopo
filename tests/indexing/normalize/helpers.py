"""Standalone tree-sitter helpers for normalize tests.

Deliberately independent of `slopo.indexing.parsing`, which is owned by
another agent and under concurrent modification: these tests must keep
working regardless of how that package's `parse()` signature evolves.
"""

from __future__ import annotations

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

_PYTHON_PARSER = Parser(Language(tree_sitter_python.language()))
_TYPESCRIPT_PARSER = Parser(Language(tree_sitter_typescript.language_typescript()))
_JAVASCRIPT_PARSER = Parser(Language(tree_sitter_javascript.language()))

_PYTHON_UNIT_TYPES = frozenset({"function_definition"})
_JS_LIKE_UNIT_TYPES = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "method_definition",
        "arrow_function",
        "function_expression",
    }
)


def _first_matching(node: Node, types: frozenset[str], index: int) -> Node:
    matches: list[Node] = []

    def walk(n: Node) -> None:
        if n.type in types:
            matches.append(n)
        for child in n.children:
            walk(child)

    walk(node)
    return matches[index]


def python_function(source: bytes, index: int = 0) -> Node:
    tree = _PYTHON_PARSER.parse(source)
    return _first_matching(tree.root_node, _PYTHON_UNIT_TYPES, index)


def typescript_function(source: bytes, index: int = 0) -> Node:
    tree = _TYPESCRIPT_PARSER.parse(source)
    return _first_matching(tree.root_node, _JS_LIKE_UNIT_TYPES, index)


def javascript_function(source: bytes, index: int = 0) -> Node:
    tree = _JAVASCRIPT_PARSER.parse(source)
    return _first_matching(tree.root_node, _JS_LIKE_UNIT_TYPES, index)
