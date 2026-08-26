from pathlib import Path

from slopo.indexing.parsing.lang import javascript, tsx, typescript
from slopo.indexing.parsing.registry import get_parser, supported_extensions


def test_supported_extensions_include_js_family_variants():
    assert {".mjs", ".cjs", ".jsx", ".tsx", ".ts", ".js"} <= supported_extensions()


def test_mjs_and_cjs_reuse_the_javascript_parser():
    assert get_parser(Path("file.mjs")) is javascript.parse
    assert get_parser(Path("file.cjs")) is javascript.parse


def test_jsx_reuses_the_javascript_parser():
    assert get_parser(Path("file.jsx")) is javascript.parse


def test_tsx_uses_the_tsx_parser():
    assert get_parser(Path("file.tsx")) is tsx.parse
    assert get_parser(Path("file.tsx")) is not typescript.parse


def test_javascript_parser_handles_jsx_syntax():
    source = b"""
function App() {
  return <div className="a">{value}</div>;
}
"""
    units = javascript.parse(source, "raw")
    assert [u.name for u in units] == ["App"]
