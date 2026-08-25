"""Generic byte-span rename engine shared by all language normalizers.

A `LanguageProfile` marks which node types are renamable identifiers,
literals, always-kept builtins, and syntactically-kept positions (e.g. an
attribute's property side). The engine walks the unit's subtree once and
splices replacements into the original source bytes.

Renaming is by spelling, not scope: there is no binding analysis beyond
`is_binding_position`'s narrow parameter/assignment-target check (see
doc/representation-experiment.md and issue #2's non-goals).
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
    is_binding_position: Callable[[Node], bool]


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


def render(
    source: bytes,
    node: Node,
    profile: LanguageProfile,
    level: str,
    removal_spans: frozenset[tuple[int, int]] = frozenset(),
) -> str:
    name_node = unit_name_node(node)
    replacements: dict[int, tuple[int, str]] = {}
    var_numbers: dict[str, str] = {}
    bound_names = _collect_bound_names(node, source, profile)

    def visit(n: Node, inside_import: bool) -> None:
        # A comment or docstring span is spliced out entirely, before any
        # rename/literal handling, so its text never reaches the embedding.
        if (n.start_byte, n.end_byte) in removal_spans:
            replacements[n.start_byte] = (n.end_byte, "")
            return

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
            if profile.is_kept_position(n):
                return
            text = text_of(source, n)
            # A name bound anywhere in the function (a parameter, an assignment
            # target) shadows the builtin of the same spelling everywhere it is
            # used here, so every occurrence renames the same way as any other.
            if text in profile.builtins and text not in bound_names:
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


def _collect_bound_names(
    node: Node, source: bytes, profile: LanguageProfile
) -> frozenset[str]:
    names: set[str] = set()

    def walk(n: Node) -> None:
        if n.type in profile.identifier_types and profile.is_binding_position(n):
            names.add(text_of(source, n))
        for child in n.children:
            walk(child)

    walk(node)
    return frozenset(names)


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


def strip_removed(
    source: bytes, node: Node, removal_spans: frozenset[tuple[int, int]]
) -> str:
    """Splice `node`'s span with `removal_spans` cut out, nothing else changed."""
    replacements = {start: (end, "") for start, end in removal_spans}
    return _splice(source, node, replacements)
