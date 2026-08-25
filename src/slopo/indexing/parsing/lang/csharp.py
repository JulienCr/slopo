import tree_sitter_c_sharp
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_c_sharp.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "csharp"

_COMMENT_TYPES = {"comment"}

_UNIT_TYPES = {
    "method_declaration",
    "constructor_declaration",
    "local_function_statement",
    "lambda_expression",
    "anonymous_method_expression",
}

_ANONYMOUS_TYPES = {"lambda_expression", "anonymous_method_expression"}


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
    # Methods, constructors and local functions carry their own name. Lambdas and
    # anonymous methods are anonymous, so the name comes from what they are bound
    # to (a callback passed as a call argument has no name and stays <unknown>).
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type in _ANONYMOUS_TYPES:
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "variable_declarator":  # Func<int> f = () => ...
        return parent.child_by_field_name("name")
    if parent.type == "assignment_expression":  # this.f = () => ...
        left = parent.child_by_field_name("left")
        if left is not None and left.type == "member_access_expression":
            return left.child_by_field_name("name")
        return left
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
    body = _body_node(unit)
    if body is None:
        return 0
    return _count_named_nodes(body)


def _body_node(unit: Node) -> Node | None:
    # Most units expose their body via the "body" field, which resolves to a
    # block, an arrow_expression_clause, or an expression. anonymous_method_expression
    # has no such field, so its block is found by scanning children.
    body = unit.child_by_field_name("body")
    if body is not None:
        return body
    return next((c for c in unit.children if c.type == "block"), None)


def _count_named_nodes(node: Node) -> int:
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count
