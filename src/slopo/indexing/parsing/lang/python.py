import tree_sitter_python
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_python.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "python"

_COMMENT_TYPES = {"comment"}


def parse(source: bytes, representation: str) -> list[CodeUnit]:
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    _collect_units(tree.root_node, source, units, representation)
    return units


def _collect_units(
    node: Node, source: bytes, units: list[CodeUnit], representation: str
) -> None:
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        name = (
            name_node.text.decode() if (name_node and name_node.text) else "<unknown>"
        )
        body, removal_spans = _body_without_comments(node, source)
        units.append(
            build_code_unit(
                name=name,
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


def _body_without_comments(
    function: Node, source: bytes
) -> tuple[str, frozenset[tuple[int, int]]]:
    comment_spans: list[tuple[int, int]] = []
    _collect_comment_spans(function, comment_spans)

    pieces: list[bytes] = []
    cursor = function.start_byte
    for start, end in sorted(comment_spans):
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor : function.end_byte])
    return b"".join(pieces).decode(), frozenset(comment_spans)


def _collect_comment_spans(node: Node, spans: list[tuple[int, int]]) -> None:
    if node.type in _COMMENT_TYPES or _is_docstring(node):
        spans.append((node.start_byte, node.end_byte))
        return
    for child in node.children:
        _collect_comment_spans(child, spans)


def _count_body_nodes(function_definition: Node) -> int:
    body = function_definition.child_by_field_name("body")
    if body is None:
        return 0
    return _count_named_nodes(body)


def _count_named_nodes(node: Node) -> int:
    if _is_docstring(node):
        return 0
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count


def _is_docstring(node: Node) -> bool:
    # A docstring is a bare string as the first statement of a module, class, or
    # function body. It carries no behavior, so it is stripped like a comment.
    if node.type != "expression_statement":
        return False
    if [c.type for c in node.named_children] != ["string"]:
        return False
    parent = node.parent
    return (
        parent is not None
        and parent.type in {"module", "block"}
        and (node == parent.named_children[0])
    )
