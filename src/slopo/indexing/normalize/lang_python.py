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


PROFILE = LanguageProfile(
    identifier_types=frozenset({"identifier"}),
    number_types=frozenset({"integer", "float"}),
    string_types=frozenset({"string"}),
    builtins=_BUILTINS,
    import_ancestor_types=frozenset({"import_statement", "import_from_statement"}),
    is_kept_position=_is_kept_position,
)
