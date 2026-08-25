"""Generic byte-span rename engine shared by all language normalizers.

A language module supplies a `LanguageProfile` describing which node types
count as renamable identifiers, which are number/string literals, which
identifiers are kept regardless of position (builtins), and a syntactic
predicate for identifiers that are kept because of *where* they sit (for
example the property side of an attribute access). The engine walks the
function's subtree once, decides a replacement (or "keep") for every
relevant leaf, and splices the result out of the original source bytes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tree_sitter import Node


@dataclass(frozen=True)
class LanguageProfile:
    identifier_types: frozenset[str]
    number_types: frozenset[str]
    string_types: frozenset[str]
    builtins: frozenset[str]
    import_ancestor_types: frozenset[str]
    is_kept_position: Callable[[Node], bool]


def unit_name_node(node: Node) -> Node | None:
    """The function/method's own name node, if its signature carries one.

    Anonymous constructs (a TypeScript arrow function bound via `const f =
    ...`) have no "name" field on the function node itself; the binding
    lives on a sibling outside the node we rewrite, so there is nothing to
    special-case here.
    """
    return node.child_by_field_name("name")


def text_of(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def render(source: bytes, node: Node, profile: LanguageProfile, level: str) -> str:
    name_node = unit_name_node(node)
    replacements: dict[int, tuple[int, str]] = {}
    var_numbers: dict[str, str] = {}

    def visit(n: Node, inside_import: bool) -> None:
        inside_import = inside_import or n.type in profile.import_ancestor_types

        # tree-sitter Node wrappers are recreated on each access, so `is`
        # does not identify "the same tree position" the way `==` does.
        if n == name_node:
            if level in ("rename_all", "rename_all_literals"):
                replacements[n.start_byte] = (n.end_byte, "f")
            return

        if n.type in profile.identifier_types:
            if inside_import:
                return
            text = text_of(source, n)
            if text in profile.builtins or profile.is_kept_position(n):
                return
            number = var_numbers.setdefault(text, f"v{len(var_numbers) + 1}")
            replacements[n.start_byte] = (n.end_byte, number)
            return

        if level == "rename_all_literals" and n.type in profile.number_types:
            replacements[n.start_byte] = (n.end_byte, "0")
            return

        if level == "rename_all_literals" and n.type in profile.string_types:
            replacements[n.start_byte] = (n.end_byte, '""')
            return

        for child in n.children:
            visit(child, inside_import)

    visit(node, False)
    return _splice(source, node, replacements)


def _splice(source: bytes, node: Node, replacements: dict[int, tuple[int, str]]) -> str:
    pieces: list[bytes] = []
    cursor = node.start_byte
    for start in sorted(replacements):
        end, text = replacements[start]
        pieces.append(source[cursor:start])
        pieces.append(text.encode("utf-8"))
        cursor = end
    pieces.append(source[cursor : node.end_byte])
    return b"".join(pieces).decode("utf-8")
