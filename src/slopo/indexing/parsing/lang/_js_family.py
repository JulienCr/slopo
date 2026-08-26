"""Shared parsing logic for the JavaScript/TypeScript family of grammars.

`typescript.py`, `javascript.py` and `tsx.py` differ only in which
tree-sitter grammar they load and the language name they report; the unit
extraction below (which node types are units, how a unit is named, comment
stripping, body-node counting) is identical across all three.
"""

from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeParser, CodeUnit, build_code_unit

_COMMENT_TYPES = {"comment"}

_UNIT_TYPES = {
    "function_declaration",
    "generator_function_declaration",
    "method_definition",
    "arrow_function",
    "function_expression",
}


def make_parser(language: Language, language_name: str) -> CodeParser:
    parser = Parser(language)

    def parse(source: bytes, representation: str) -> list[CodeUnit]:
        tree = parser.parse(source)
        units: list[CodeUnit] = []
        _collect_units(tree.root_node, source, units, representation, language_name)
        return units

    return parse


def _collect_units(
    node: Node,
    source: bytes,
    units: list[CodeUnit],
    representation: str,
    language_name: str,
) -> None:
    if node.type in _UNIT_TYPES:
        body, removal_spans = _body_without_comments(node, source)
        units.append(
            build_code_unit(
                name=_unit_name(node),
                node=node,
                source=source,
                body=body,
                body_node_count=_count_body_nodes(node),
                language=language_name,
                representation=representation,
                removal_spans=removal_spans,
            )
        )
    for child in node.children:
        _collect_units(child, source, units, representation, language_name)


def _unit_name(node: Node) -> str:
    # Declarations and methods carry their own name. Arrow and function
    # expressions are anonymous, so the name comes from what they are bound to.
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type in {"arrow_function", "function_expression"}:
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "variable_declarator":  # const f = () => ...
        return parent.child_by_field_name("name")
    if parent.type == "pair":  # { f: () => ... }
        return parent.child_by_field_name("key")
    if parent.type == "assignment_expression":  # x.f = () => ...
        left = parent.child_by_field_name("left")
        if left is not None and left.type == "member_expression":
            return left.child_by_field_name("property")
        return left
    return None


def _body_without_comments(
    unit: Node, source: bytes
) -> tuple[str, frozenset[tuple[int, int]]]:
    comment_spans: list[tuple[int, int]] = []
    _collect_comment_spans(unit, comment_spans)

    pieces: list[bytes] = []
    cursor = unit.start_byte
    for start, end in sorted(comment_spans):
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor : unit.end_byte])
    return b"".join(pieces).decode(), frozenset(comment_spans)


def _collect_comment_spans(node: Node, spans: list[tuple[int, int]]) -> None:
    if node.type in _COMMENT_TYPES:
        spans.append((node.start_byte, node.end_byte))
        return
    for child in node.children:
        _collect_comment_spans(child, spans)


def _count_body_nodes(unit: Node) -> int:
    body = unit.child_by_field_name("body")
    if body is None:
        return 0
    return _count_named_nodes(body)


def _count_named_nodes(node: Node) -> int:
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count
