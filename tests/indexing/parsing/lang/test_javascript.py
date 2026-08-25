from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.javascript import parse

FIXTURES = Path(__file__).parent / "fixtures" / "javascript"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.js").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.js").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.js").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.js").read_bytes(), "raw")


def test_extracts_functions_arrows_and_methods(example):
    assert [u.name for u in example] == [
        "add",
        "greet",
        "fetchUser",
        "reset",
        "constructor",
        "increment",
    ]


def test_function_declaration_body_exact(example):
    add = next(u for u in example if u.name == "add")
    assert add.body == "function add(a, b) {\n  return a + b;\n}"


def test_arrow_function_named_from_binding(example):
    greet = next(u for u in example if u.name == "greet")
    assert greet.body == "(name) => {\n  return `Hello, ${name}!`;\n}"


def test_object_method_named_from_key(example):
    reset = next(u for u in example if u.name == "reset")
    assert reset.body == "reset() {\n    this.value = 0;\n  }"


def test_line_numbers_are_one_based_and_correct(example):
    add = next(u for u in example if u.name == "add")
    assert add.start_line == 1
    assert add.end_line == 3


def test_arrow_nested_in_function_is_extracted(nested):
    assert [u.name for u in nested] == ["makeAdder", "apply"]


def test_nested_arrow_body_exact(nested):
    apply = next(u for u in nested if u.name == "apply")
    assert apply.body == "(value) => {\n    return value + amount;\n  }"


def test_body_node_count_counts_expression_for_concise_arrow(body_sizes):
    square = next(u for u in body_sizes if u.name == "square")
    assert square.body_node_count == 3


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    noop = next(u for u in body_sizes if u.name == "noop")
    assert noop.body_node_count == 1


def test_body_node_count_for_larger_body(body_sizes):
    load_all = next(u for u in body_sizes if u.name == "loadAll")
    assert load_all.body_node_count == 43


def test_strips_line_block_and_doc_comments_from_body(comments):
    assert comments[0].body == (
        "function withComments(a, b) {\n"
        "  \n"
        "  const sum = a + b; \n"
        "  \n"
        '  const url = "https://not-a-comment";\n'
        "  return sum;\n"
        "}"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash
