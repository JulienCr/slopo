"""Rename profile shared by TypeScript and JavaScript.

Verified against `tree_sitter_typescript.language_typescript()` and
`tree_sitter_javascript.language()`: both grammars give a property/method
name its own "property_identifier" node type (member access, object literal
keys, method definitions), distinct from the "identifier" type used for
variable references and bindings. That split does the attribute-position
exclusion for free, so unlike Python there is no parent/field check needed
here.
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
)
