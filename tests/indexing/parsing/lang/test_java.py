from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.java import parse

FIXTURES = Path(__file__).parent / "fixtures" / "java"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.java").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.java").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.java").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.java").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.java").read_bytes(), "raw")


@pytest.fixture
def lambdas() -> list[CodeUnit]:
    return parse((FIXTURES / "Lambdas.java").read_bytes(), "raw")


def test_extracts_all_methods(example):
    assert [u.name for u in example] == ["add", "greet", "normalize", "repeat"]


def test_body_exact(example):
    add = next(u for u in example if u.name == "add")
    assert (
        add.body
        == "public static int add(int a, int b) {\n        return a + b;\n    }"
    )


def test_line_numbers_are_one_based_and_correct(example):
    add = next(u for u in example if u.name == "add")
    assert add.start_line == 3
    assert add.end_line == 5


def test_methods_in_nested_class_are_extracted(nested):
    assert [u.name for u in nested] == ["outerMethod", "innerMethod"]


def test_nested_method_body_exact(nested):
    inner = next(u for u in nested if u.name == "innerMethod")
    assert (
        inner.body
        == 'public void innerMethod() {\n            System.out.println("inner");\n        }'
    )


def test_method_in_anonymous_class_in_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == ["makeTask", "run"]


def test_anonymous_class_method_emitted_alongside_enclosing_method(nested_in_body):
    run = next(u for u in nested_in_body if u.name == "run")
    assert (
        run.body
        == "public void run() {\n                System.out.println(label);\n            }"
    )


def test_body_node_count_is_zero_for_abstract_method(body_sizes):
    abstract = next(u for u in body_sizes if u.name == "abstractMethod")
    assert abstract.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "emptyBody")
    assert empty.body_node_count == 1


def test_body_node_count_for_single_return_statement(example):
    add = next(u for u in example if u.name == "add")
    assert add.body_node_count == 5


def test_body_node_count_ignores_annotations_and_counts_method_logic(body_sizes):
    annotated = next(u for u in body_sizes if u.name == "annotatedWithLogic")
    assert annotated.body_node_count == 36


def test_strips_line_and_block_comments_from_body(comments):
    assert comments[0].body == (
        "public int withComments(int a, int b) {\n"
        "        \n"
        "        int sum = a + b; \n"
        "        \n"
        '        String url = "http://not-a-comment";\n'
        "        return sum;\n"
        "    }"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash


def test_lambda_bound_to_variable_takes_binding_name(lambdas):
    doubler = next(u for u in lambdas if u.name == "doubler")
    assert doubler.body == "x -> x * 2"


def test_lambda_bound_to_member_takes_member_name(lambdas):
    on_complete = next(u for u in lambdas if u.name == "onComplete")
    assert on_complete.body == (
        '() -> {\n            System.out.println("done");\n        }'
    )


def test_callback_lambda_without_binding_is_unknown(lambdas):
    callbacks = [u for u in lambdas if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {
        "v -> v > 0",
        "v -> {\n"
        "                    int scaled = doubler.apply(v);\n"
        "                    return scaled + 1;\n"
        "                }",
    }


def test_nested_lambda_emitted_alongside_enclosing_method(lambdas):
    block_bodied_lambda = (
        "v -> {\n"
        "                    int scaled = doubler.apply(v);\n"
        "                    return scaled + 1;\n"
        "                }"
    )
    assert "transform" in {u.name for u in lambdas}
    assert block_bodied_lambda in {u.body for u in lambdas}
