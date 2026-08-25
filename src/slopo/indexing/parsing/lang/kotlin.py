import tree_sitter_kotlin
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_kotlin.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "kotlin"

_COMMENT_TYPES = {"line_comment", "block_comment"}

_UNIT_TYPES = {"function_declaration", "anonymous_function"}


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
    # Function declarations carry their own name. Anonymous functions are
    # anonymous, so the name comes from what they are bound to (one passed as a
    # call argument has no name and stays <unknown>). Bindings are positional in
    # this grammar — there are no name/left fields as in Java or C#.
    name_node = node.child_by_field_name("name")
    if name_node is None and node.type == "anonymous_function":
        name_node = _binding_name_node(node)
    return name_node.text.decode() if (name_node and name_node.text) else "<unknown>"


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "property_declaration":  # val f = fun() { ... }
        declaration = next(
            (c for c in parent.children if c.type == "variable_declaration"), None
        )
        return _last_identifier(declaration) if declaration else None
    if parent.type == "assignment":  # this.f = fun() { ... }
        target = parent.children[0] if parent.children else None
        return _last_identifier(target) if target else None
    return None


def _last_identifier(node: Node) -> Node | None:
    if node.type == "identifier":
        return node
    return next((c for c in reversed(node.children) if c.type == "identifier"), None)


def _body_without_comments(function: Node, source: bytes) -> str:
    comment_spans: list[tuple[int, int]] = []
    _collect_comment_spans(function, comment_spans)

    pieces: list[bytes] = []
    cursor = function.start_byte
    for start, end in sorted(comment_spans):
        pieces.append(source[cursor:start])
        cursor = end
    pieces.append(source[cursor : function.end_byte])
    return b"".join(pieces).decode()


def _collect_comment_spans(node: Node, spans: list[tuple[int, int]]) -> None:
    if node.type in _COMMENT_TYPES:
        spans.append((node.start_byte, node.end_byte))
        return
    for child in node.children:
        _collect_comment_spans(child, spans)


def _count_body_nodes(function_declaration: Node) -> int:
    body = next(
        (c for c in function_declaration.children if c.type == "function_body"), None
    )
    if body is None:
        return 0
    return _count_named_nodes(body)


def _count_named_nodes(node: Node) -> int:
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count
