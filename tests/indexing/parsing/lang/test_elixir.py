from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.elixir import parse

FIXTURES = Path(__file__).parent / "fixtures" / "elixir"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.ex").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.ex").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.ex").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.ex").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.ex").read_bytes(), "raw")


@pytest.fixture
def closures() -> list[CodeUnit]:
    return parse((FIXTURES / "Closures.ex").read_bytes(), "raw")


def test_extracts_public_and_private_functions(example):
    assert [u.name for u in example] == ["add", "greet", "normalize", "repeat"]


def test_body_exact_for_do_block(example):
    add = next(u for u in example if u.name == "add")
    assert add.body == "def add(a, b) do\n    a + b\n  end"


def test_body_exact_for_keyword_do_form(example):
    repeat = next(u for u in example if u.name == "repeat")
    assert repeat.body == "def repeat(text, count), do: String.duplicate(text, count)"


def test_name_resolved_through_when_guard(example):
    assert any(u.name == "normalize" for u in example)


def test_line_numbers_are_one_based_and_correct(example):
    add = next(u for u in example if u.name == "add")
    assert add.start_line == 4
    assert add.end_line == 6


def test_function_in_nested_module_is_extracted(nested):
    assert [u.name for u in nested] == ["outer_fun", "inner_fun"]


def test_nested_function_body_exact(nested):
    inner = next(u for u in nested if u.name == "inner_fun")
    assert inner.body == "def inner_fun(y) do\n      y + 1\n    end"


def test_anonymous_function_in_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == [
        "make_task",
        "<unknown>",
        "double_all",
        "<unknown>",
    ]


def test_anonymous_function_emitted_alongside_enclosing_function(nested_in_body):
    make_task = next(u for u in nested_in_body if u.name == "make_task")
    closures = [u for u in nested_in_body if u.name == "<unknown>"]
    assert make_task.start_line == 2
    assert "fn ->\n      IO.puts(label)\n    end" in {u.body for u in closures}


def test_body_node_count_counts_only_expression_for_keyword_body(body_sizes):
    constant = next(u for u in body_sizes if u.name == "constant")
    assert constant.body_node_count == 1


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "empty_body")
    assert empty.body_node_count == 1


def test_body_node_count_for_single_expression_do_block(example):
    add = next(u for u in example if u.name == "add")
    assert add.body_node_count == 4


def test_body_node_count_ignores_doc_attribute_and_counts_pipeline(body_sizes):
    total = next(u for u in body_sizes if u.name == "total")
    assert total.body_node_count == 28


def test_strips_line_comment_and_keeps_hash_in_string(comments):
    assert comments[0].body == (
        "def with_comments(a, b) do\n"
        "    \n"
        "    sum = a + b\n"
        '    url = "http://example.com#section"\n'
        "    sum\n"
        "  end"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash


def test_anonymous_function_bound_to_variable_takes_binding_name(closures):
    doubler = next(u for u in closures if u.name == "doubler")
    assert doubler.body == "fn x -> x * 2 end"


def test_callback_anonymous_function_without_binding_is_unknown(closures):
    callbacks = [u for u in closures if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {"fn v -> doubler.(v) + 1 end"}


def test_nested_anonymous_function_emitted_alongside_enclosing_function(closures):
    assert "build" in {u.name for u in closures}
    assert "fn x -> x * 2 end" in {u.body for u in closures}
