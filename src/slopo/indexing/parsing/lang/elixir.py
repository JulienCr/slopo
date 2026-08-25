import tree_sitter_elixir
from tree_sitter import Language, Node, Parser

from slopo.indexing.parsing.base import CodeUnit, build_code_unit

_LANGUAGE = Language(tree_sitter_elixir.language())
_PARSER = Parser(_LANGUAGE)

_LANGUAGE_NAME = "elixir"

_COMMENT_TYPES = {"comment"}

# Elixir has no dedicated function-declaration node: `def`/`defp` are ordinary
# macro calls, so a named function is a `call` whose target identifier is one of
# these. Anonymous functions (`fn ... end`) have their own node type.
_DEFINERS = {"def", "defp"}


def parse(source: bytes, representation: str) -> list[CodeUnit]:
    tree = _PARSER.parse(source)
    units: list[CodeUnit] = []
    _collect_units(tree.root_node, source, units, representation)
    return units


def _collect_units(
    node: Node, source: bytes, units: list[CodeUnit], representation: str
) -> None:
    if _is_unit(node):
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


def _is_unit(node: Node) -> bool:
    return node.type == "anonymous_function" or _definer(node) is not None


def _definer(node: Node) -> str | None:
    # A `def`/`defp` call has the definer identifier as its first child.
    if node.type != "call" or not node.children:
        return None
    head = node.children[0]
    if head.type != "identifier" or head.text is None:
        return None
    name = head.text.decode()
    return name if name in _DEFINERS else None


def _unit_name(node: Node) -> str:
    # Named functions carry their name inside the definer call's arguments.
    # Anonymous functions are anonymous, so the name comes from what they are
    # bound to (one passed as a call argument has no name and stays <unknown>).
    if node.type == "anonymous_function":
        binding = _binding_name_node(node)
        return binding.text.decode() if (binding and binding.text) else "<unknown>"
    head = _signature_node(node)
    if head is None:
        return "<unknown>"
    if head.type == "call":  # def add(a, b) do ... — name is the call target
        head = head.children[0] if head.children else head
    return (
        head.text.decode() if (head.type == "identifier" and head.text) else "<unknown>"
    )


def _signature_node(node: Node) -> Node | None:
    # The first argument of the definer call, unwrapping a `when` guard.
    args = next((c for c in node.children if c.type == "arguments"), None)
    if args is None or not args.named_children:
        return None
    head = args.named_children[0]
    if head.type == "binary_operator":  # def foo(x) when guard -> take the left
        head = head.children[0] if head.children else head
    return head


def _binding_name_node(node: Node) -> Node | None:
    parent = node.parent
    if parent is None:
        return None
    if parent.type == "binary_operator":  # add = fn ... end
        operator = parent.children[1] if len(parent.children) > 1 else None
        target = parent.children[0] if parent.children else None
        if operator is not None and operator.type == "=" and target is not None:
            return target if target.type == "identifier" else None
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
    return sum(_count_named_nodes(body) for body in _body_nodes(unit))


def _body_nodes(unit: Node) -> list[Node]:
    if unit.type == "anonymous_function":
        # One `stab_clause` per clause; each holds a `body` node (exposed under
        # the `right` field, so match by type rather than field name).
        return [
            body
            for clause in unit.children
            if clause.type == "stab_clause"
            for body in clause.children
            if body.type == "body"
        ]
    # Named function: either a `do ... end` block or a `do:` keyword body.
    do_block = next((c for c in unit.children if c.type == "do_block"), None)
    if do_block is not None:
        return [do_block]
    keyword_body = _keyword_do_body(unit)
    return [keyword_body] if keyword_body is not None else []


def _keyword_do_body(unit: Node) -> Node | None:
    args = next((c for c in unit.children if c.type == "arguments"), None)
    if args is None:
        return None
    keywords = next((c for c in args.named_children if c.type == "keywords"), None)
    if keywords is None:
        return None
    for pair in keywords.named_children:
        key = pair.child_by_field_name("key")
        if (
            key is not None
            and key.text is not None
            and key.text.decode().strip() == "do:"
        ):
            return pair.child_by_field_name("value")
    return None


def _count_named_nodes(node: Node) -> int:
    count = 1 if node.is_named else 0
    for child in node.children:
        count += _count_named_nodes(child)
    return count
