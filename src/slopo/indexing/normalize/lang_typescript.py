"""Rename profile shared by TypeScript, TSX and JavaScript.

Verified against `tree_sitter_typescript.language_typescript()`,
`tree_sitter_typescript.language_tsx()` and `tree_sitter_javascript.language()`:
all three grammars give a property/method name its own "property_identifier"
node type (member access, object literal keys, method definitions), distinct
from the "identifier" type used for variable references and bindings. That
split does the attribute-position exclusion for free, so unlike Python there
is no parent/field check needed here.
"""

from __future__ import annotations

from tree_sitter import Node

from slopo.indexing.normalize.engine import LanguageProfile

_BUILTINS = frozenset(
    {
        "Array",
        "Boolean",
        "console",
        "Date",
        "Error",
        "Infinity",
        "isFinite",
        "isNaN",
        "JSON",
        "Map",
        "Math",
        "NaN",
        "Number",
        "Object",
        "parseFloat",
        "parseInt",
        "Promise",
        "RangeError",
        "Reflect",
        "RegExp",
        "Set",
        "String",
        "Symbol",
        "TypeError",
    }
)


def _is_kept_position(node: Node) -> bool:
    del node
    return False


def _contains(ancestor: Node, node: Node) -> bool:
    return ancestor.start_byte <= node.start_byte and node.end_byte <= ancestor.end_byte


_BINDING_WRAPPER_TYPES = frozenset(
    {"object_pattern", "array_pattern", "pair_pattern", "rest_pattern"}
)


def _is_binding_position(node: Node) -> bool:
    # Climb through destructuring wrappers to the node that actually names the
    # binding: a parameter, a `let`/`const` declarator, or an assignment target.
    n = node
    parent = n.parent
    while parent is not None:
        if parent.type == "object_assignment_pattern":
            return parent.child_by_field_name("left") == n
        if parent.type not in _BINDING_WRAPPER_TYPES:
            break
        n = parent
        parent = n.parent

    if parent is None:
        return False
    if parent.type == "formal_parameters":
        return True
    if parent.type in {"required_parameter", "optional_parameter"}:
        value = parent.child_by_field_name("value")
        return value is None or not _contains(value, n)
    if parent.type == "variable_declarator":
        name = parent.child_by_field_name("name")
        return name is not None and _contains(name, n)
    if parent.type in {"assignment_expression", "augmented_assignment_expression"}:
        left = parent.child_by_field_name("left")
        return left is not None and _contains(left, n)
    return False


PROFILE = LanguageProfile(
    identifier_types=frozenset(
        {
            "identifier",
            "shorthand_property_identifier",
            "shorthand_property_identifier_pattern",
        }
    ),
    number_types=frozenset({"number"}),
    string_types=frozenset({"string"}),
    builtins=_BUILTINS,
    import_ancestor_types=frozenset({"import_statement"}),
    is_kept_position=_is_kept_position,
    is_binding_position=_is_binding_position,
)
