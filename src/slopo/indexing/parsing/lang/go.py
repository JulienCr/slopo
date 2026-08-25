import tree_sitter_go
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_go.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "go"

_COMMENT_TYPES = {"comment"}

_UNIT_TYPES = {"function_declaration", "method_declaration", "func_literal"}


def parse(source: bytes, representation: str) -> list[CodeUnit]:
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    _collect_units(tree.root_node, source, units, representation)
    return units


def _collect_units(
    node: Node, source: bytes, units: list[CodeUnit], representation: str
) -> None:
    if node.type in _UNIT_TYPES:
        body = _body_without_comments(node, source)
        units.append(
            build_code_unit(
                name=_unit_name(node),
                node=node,
                source=source,
                body=body,
                body_node_count=_count_body_nodes(node),
                language=_LANGUAGE_NAME,
                representation=representation,
            )
        )
    for child in node.children:
        _collect_units(child, source, units, representation)


def _unit_name(node: Node) -> str:
    # Functions and methods carry their own name. Function literals are anonymous,
    # so the name comes from what they are bound to (one passed as a call argument
    # has no name and stays <unknown>).
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type == "func_literal":
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent  # the func_literal sits in an expression_list
    if parent is None or parent.type != "expression_list":
        return None
    binding = parent.parent
    if binding is None:
        return None
    if binding.type == "var_spec":  # var f = func() { ... }
        return binding.child_by_field_name("name")
    if binding.type in ("short_var_declaration", "assignment_statement"):
        # f := func() { ... } / w.onComplete = func() { ... }; the target is the
        # first child, an expression_list holding the identifier or selector.
        left = binding.children[0] if binding.children else None
        target = left.children[0] if (left and left.children) else None
        return _target_name_node(target) if target else None
    return None


def _target_name_node(node: Node) -> Node | None:
    # A plain binding (f) names the identifier; a member binding (w.onComplete) is
    # a selector whose field carries the name.
    if node.type == "selector_expression":
        return node.child_by_field_name("field")
    if node.type == "identifier":
        return node
    return None


def _body_without_comments(unit: Node, source: bytes) -> str:
    comment_spans: list[tuple[int, int]] = []
    _collect_comment_spans(unit, comment_spans)

    pieces: list[bytes] = []
    cursor = unit.start_byte
    for start, end in sorted(comment_spans):
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor : unit.end_byte])
    return b"".join(pieces).decode()


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
