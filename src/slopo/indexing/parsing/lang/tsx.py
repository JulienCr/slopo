import tree_sitter_typescript
from tree_sitter import Language

from slopo.indexing.parsing.lang._js_family import make_parser

_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
_LANGUAGE_NAME = "tsx"

parse = make_parser(_LANGUAGE, _LANGUAGE_NAME)
