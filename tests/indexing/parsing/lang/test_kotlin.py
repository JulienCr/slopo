from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.kotlin import parse

FIXTURES = Path(__file__).parent / "fixtures" / "kotlin"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.kt").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.kt").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.kt").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.kt").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.kt").read_bytes(), "raw")


@pytest.fixture
def lambdas() -> list[CodeUnit]:
    return parse((FIXTURES / "Lambdas.kt").read_bytes(), "raw")


def test_extracts_member_and_top_level_extension_functions(example):
    assert [u.name for u in example] == ["greet", "classify", "normalize", "sumEvens"]


def test_expression_body_function_body_exact(example):
    greet = next(u for u in example if u.name == "greet")
    assert greet.body == 'fun greet(name: String) = "$prefix, $name!"'


def test_when_expression_body_exact(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.body == (
        "fun classify(n: Int): String = when {\n"
        '        n < 0 -> "negative"\n'
        '        n == 0 -> "zero"\n'
        '        else -> "positive"\n'
        "    }"
    )


def test_top_level_extension_function_body_exact(example):
    sum_evens = next(u for u in example if u.name == "sumEvens")
    assert sum_evens.body == (
        "fun List<Int>.sumEvens(): Int =\n    filter { it % 2 == 0 }.sum()"
    )


def test_line_numbers_are_one_based_and_correct(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.start_line == 5
    assert classify.end_line == 9


def test_functions_in_companion_object_are_extracted(nested):
    assert [u.name for u in nested] == ["outerMethod", "innerMethod"]


def test_companion_object_function_body_exact(nested):
    inner = next(u for u in nested if u.name == "innerMethod")
    assert inner.body == 'fun innerMethod() = println("inner")'


def test_local_function_in_function_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == ["outerFunction", "localFunction"]


def test_local_function_emitted_alongside_enclosing_function(nested_in_body):
    local = next(u for u in nested_in_body if u.name == "localFunction")
    assert local.body == "fun localFunction(x: Int): Int {\n        return x + 1\n    }"


def test_body_node_count_is_zero_for_function_without_body(body_sizes):
    abstract = next(u for u in body_sizes if u.name == "abstractMethod")
    assert abstract.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "emptyBody")
    assert empty.body_node_count == 2


def test_body_node_count_for_expression_body(example):
    greet = next(u for u in example if u.name == "greet")
    assert greet.body_node_count == 6


def test_body_node_count_ignores_annotations_and_counts_function_logic(body_sizes):
    annotated = next(u for u in body_sizes if u.name == "annotatedWithLogic")
    assert annotated.body_node_count == 34


def test_strips_line_block_and_kdoc_comments_from_body(comments):
    assert comments[0].body == (
        "fun withComments(a: Int, b: Int): Int {\n"
        "        \n"
        "        val sum = a + b \n"
        "        \n"
        '        val url = "http://not-a-comment"\n'
        "        return sum\n"
        "    }"
    )


def test_anonymous_function_bound_to_variable_takes_binding_name(lambdas):
    doubler = next(u for u in lambdas if u.name == "doubler")
    assert doubler.body == "fun(x: Int): Int { return x * 2 }"


def test_anonymous_function_bound_to_member_takes_member_name(lambdas):
    on_complete = next(u for u in lambdas if u.name == "onComplete")
    assert on_complete.body == 'fun() {\n            println("done")\n        }'


def test_callback_anonymous_function_without_binding_is_unknown(lambdas):
    callbacks = [u for u in lambdas if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {
        "fun(v: Int): Int {\n"
        "                val scaled = doubler(v)\n"
        "                return scaled + 1\n"
        "            }",
    }


def test_lambda_literal_is_not_emitted_as_unit(lambdas):
    enclosing_function = next(unit for unit in lambdas if unit.name == "transform")
    all_emitted_bodies = {unit.body for unit in lambdas}
    assert "{ it > 0 }" in enclosing_function.body
    assert "{ it > 0 }" not in all_emitted_bodies
