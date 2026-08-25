"""Rename profile for Python, matching the grammar in `tree_sitter_python`."""

from __future__ import annotations

from tree_sitter import Node

from slopo.indexing.normalize.engine import LanguageProfile

# Python's `attribute` node types the object and the property the same way
# ("identifier" for both), unlike TypeScript's `member_expression` which
# gives the property its own "property_identifier" node type. So the
# attribute/keyword-argument name position has to be excluded by hand here.
_BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "getattr",
        "hasattr",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "object",
        "print",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "sorted",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "zip",
        "Exception",
        "IndexError",
        "KeyError",
        "StopIteration",
        "TypeError",
        "ValueError",
    }
)


def _is_kept_position(node: Node) -> bool:
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "attribute" and parent.child_by_field_name("attribute") == node:
        return True
    if parent.type == "keyword_argument" and parent.child_by_field_name("name") == node:
        return True
    return False


def _contains(ancestor: Node, node: Node) -> bool:
    return ancestor.start_byte <= node.start_byte and node.end_byte <= ancestor.end_byte


_PARAM_NAME_FIELD_TYPES = frozenset({"default_parameter", "typed_default_parameter"})
_PARAM_TYPE_FIELD_TYPES = frozenset(
    {"typed_parameter", "list_splat_pattern", "dictionary_splat_pattern"}
)
_ASSIGNMENT_PATTERN_TYPES = frozenset({"pattern_list", "tuple_pattern", "list_pattern"})


def _is_parameter_binding(node: Node) -> bool:
    parent = node.parent
    if parent is None:
        return False
    if parent.type == "parameters":
        return True
    if parent.type in _PARAM_TYPE_FIELD_TYPES:
        return parent.child_by_field_name("type") != node
    if parent.type in _PARAM_NAME_FIELD_TYPES:
        return parent.child_by_field_name("name") == node
    return False


def _is_assignment_target(node: Node) -> bool:
    n = node
    parent = n.parent
    while parent is not None and parent.type in _ASSIGNMENT_PATTERN_TYPES:
        n = parent
        parent = n.parent
    if parent is None or parent.type not in {"assignment", "augmented_assignment"}:
        return False
    left = parent.child_by_field_name("left")
    return left is not None and _contains(left, n)


def _is_binding_position(node: Node) -> bool:
    return _is_parameter_binding(node) or _is_assignment_target(node)


PROFILE = LanguageProfile(
    identifier_types=frozenset({"identifier"}),
    number_types=frozenset({"integer", "float"}),
    string_types=frozenset({"string"}),
    builtins=_BUILTINS,
    import_ancestor_types=frozenset({"import_statement", "import_from_statement"}),
    is_kept_position=_is_kept_position,
    is_binding_position=_is_binding_position,
)
