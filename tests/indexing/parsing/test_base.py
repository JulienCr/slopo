import pytest
import tree_sitter_python
from tree_sitter import Language, Parser

from slopo.indexing.parsing import base
from slopo.indexing.parsing.base import build_code_unit, hash_body


def test_identical_code_hashes_equal():
    assert hash_body("int sum = a + b;") == hash_body("int sum = a + b;")


def test_whitespace_differences_hash_equal():
    assert hash_body("int sum = a + b;") == hash_body("int  sum =\n\ta +  b;")


def test_minimal_code_difference_hashes_differently():
    assert hash_body("int sum = a + b;") != hash_body("int sum = a - b;")


_LANGUAGE = Language(tree_sitter_python.language())
_PARSER = Parser(_LANGUAGE)


def _function_node(source: str):
    tree = _PARSER.parse(source.encode())
    return tree.root_node.named_children[0]


# --- build_code_unit ---


def test_raw_level_keeps_embed_body_and_embed_hash_identical_to_body(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        base, "normalize", lambda source, node, language, level, removal_spans: level
    )
    node = _function_node("def foo(a): return a")

    unit = build_code_unit(
        name="foo",
        node=node,
        source=b"def foo(a): return a",
        body="def foo(a): return a",
        body_node_count=3,
        language="python",
        representation="raw",
    )

    assert unit.embed_body == "raw"
    assert unit.embed_hash == hash_body("raw")


def test_normalize_output_flows_into_embed_body_and_embed_hash(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        base,
        "normalize",
        lambda source, node, language, level, removal_spans: "NORMALIZED",
    )
    node = _function_node("def foo(a): return a")

    unit = build_code_unit(
        name="foo",
        node=node,
        source=b"def foo(a): return a",
        body="def foo(a): return a",
        body_node_count=3,
        language="python",
        representation="rename_locals",
    )

    assert unit.body == "def foo(a): return a"
    assert unit.embed_body == "NORMALIZED"
    assert unit.embed_hash == hash_body("NORMALIZED")
    assert unit.body_hash == hash_body("def foo(a): return a")


def test_normalize_receives_the_language_and_level_it_was_called_with(
    monkeypatch: pytest.MonkeyPatch,
):
    seen = {}

    def fake_normalize(source, node, language, level, removal_spans):
        seen["source"] = source
        seen["language"] = language
        seen["level"] = level
        return "x"

    monkeypatch.setattr(base, "normalize", fake_normalize)
    node = _function_node("def foo(a): return a")

    build_code_unit(
        name="foo",
        node=node,
        source=b"def foo(a): return a",
        body="def foo(a): return a",
        body_node_count=3,
        language="python",
        representation="rename_all",
    )

    assert seen == {
        "source": b"def foo(a): return a",
        "language": "python",
        "level": "rename_all",
    }
