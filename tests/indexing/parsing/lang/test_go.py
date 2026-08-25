from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.go import parse

FIXTURES = Path(__file__).parent / "fixtures" / "go"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.go").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.go").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.go").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.go").read_bytes(), "raw")


@pytest.fixture
def closures() -> list[CodeUnit]:
    return parse((FIXTURES / "Closures.go").read_bytes(), "raw")


def test_extracts_methods_and_top_level_functions(example):
    assert [u.name for u in example] == [
        "Greet",
        "Classify",
        "Normalize",
        "SumEvens",
    ]


def test_method_with_receiver_body_exact(example):
    greet = next(u for u in example if u.name == "Greet")
    assert greet.body == (
        "func (g Greeter) Greet(name string) string {\n"
        '\treturn g.prefix + ", " + name + "!"\n'
        "}"
    )


def test_switch_function_body_exact(example):
    classify = next(u for u in example if u.name == "Classify")
    assert classify.body == (
        "func Classify(n int) string {\n"
        "\tswitch {\n"
        "\tcase n < 0:\n"
        '\t\treturn "negative"\n'
        "\tcase n == 0:\n"
        '\t\treturn "zero"\n'
        "\tdefault:\n"
        '\t\treturn "positive"\n'
        "\t}\n"
        "}"
    )


def test_line_numbers_are_one_based_and_correct(example):
    classify = next(u for u in example if u.name == "Classify")
    assert classify.start_line == 13
    assert classify.end_line == 22


def test_closure_in_function_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == ["OuterFunction", "increment"]


def test_closure_emitted_alongside_enclosing_function(nested_in_body):
    increment = next(u for u in nested_in_body if u.name == "increment")
    assert increment.body == "func(n int) int {\n\t\treturn n + 1\n\t}"


def test_body_node_count_is_zero_for_function_without_body(body_sizes):
    external = next(u for u in body_sizes if u.name == "externalFunction")
    assert external.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "emptyBody")
    assert empty.body_node_count == 1


def test_body_node_count_for_function_with_logic(body_sizes):
    with_logic = next(u for u in body_sizes if u.name == "withLogic")
    assert with_logic.body_node_count == 47


def test_strips_line_and_block_comments_from_body(comments):
    assert comments[0].body == (
        "func WithComments(a, b int) int {\n"
        "\t\n"
        "\tsum := a + b \n"
        '\turl := "http://not-a-comment"\n'
        "\t_ = url\n"
        "\treturn sum\n"
        "}"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash


def test_closure_bound_to_variable_takes_binding_name(closures):
    doubler = next(u for u in closures if u.name == "doubler")
    assert doubler.body == "func(x int) int { return x * 2 }"


def test_closure_bound_to_struct_field_takes_field_name(closures):
    on_complete = next(u for u in closures if u.name == "onComplete")
    assert on_complete.body == 'func() {\n\t\tprintln("done")\n\t}'


def test_callback_closure_without_binding_is_unknown(closures):
    callbacks = [u for u in closures if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {
        "func(v int) int {\n\t\tscaled := doubler(v)\n\t\treturn scaled + 1\n\t}",
    }
