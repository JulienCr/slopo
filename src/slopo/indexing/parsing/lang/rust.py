import tree_sitter_rust
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_rust.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "rust"

_COMMENT_TYPES = {"line_comment", "block_comment"}

_UNIT_TYPES = {"function_item", "function_signature_item", "closure_expression"}


def parse(source: bytes, representation: str) -> list[CodeUnit]:
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    _collect_units(tree.root_node, source, units, representation)
    return units


def _collect_units(
    node: Node, source: bytes, units: list[CodeUnit], representation: str
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
                language=_LANGUAGE_NAME,
                representation=representation,
                removal_spans=removal_spans,
            )
        )
    for child in node.children:
        _collect_units(child, source, units, representation)


def _unit_name(node: Node) -> str:
    # Functions and trait method signatures carry their own name. Closures are
    # anonymous, so the name comes from what they are bound to (one passed as a
    # call argument has no name and stays <unknown>).
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type == "closure_expression":
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "let_declaration":  # let f = |x| ...
        return parent.child_by_field_name("pattern")
    if parent.type == "assignment_expression":  # self.cb = |x| ...
        left = parent.child_by_field_name("left")
        if left is not None and left.type == "field_expression":
            return left.child_by_field_name("field")
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
