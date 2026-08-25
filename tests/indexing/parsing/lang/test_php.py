from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.php import parse

FIXTURES = Path(__file__).parent / "fixtures" / "php"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.php").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.php").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.php").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.php").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.php").read_bytes(), "raw")


@pytest.fixture
def closures() -> list[CodeUnit]:
    return parse((FIXTURES / "Closures.php").read_bytes(), "raw")


def test_extracts_all_methods_and_functions(example):
    assert [u.name for u in example] == ["add", "greet", "normalize", "repeat"]


def test_body_exact(example):
    add = next(u for u in example if u.name == "add")
    assert add.body == (
        "public function add(int $a, int $b): int\n"
        "    {\n"
        "        return $a + $b;\n"
        "    }"
    )


def test_line_numbers_are_one_based_and_correct(example):
    add = next(u for u in example if u.name == "add")
    assert add.start_line == 7
    assert add.end_line == 10


def test_method_in_anonymous_class_is_extracted(nested):
    assert [u.name for u in nested] == ["outerMethod", "makeInner", "innerMethod"]


def test_nested_method_body_exact(nested):
    inner = next(u for u in nested if u.name == "innerMethod")
    assert inner.body == (
        "public function innerMethod(): string\n"
        "            {\n"
        '                return "inner";\n'
        "            }"
    )


def test_closure_in_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == ["makeTask", "run"]


def test_closure_emitted_alongside_enclosing_method(nested_in_body):
    closure = next(u for u in nested_in_body if u.name == "run")
    assert closure.body == (
        "function () use ($label) {\n            echo $label;\n        }"
    )


def test_body_node_count_is_zero_for_abstract_method(body_sizes):
    abstract = next(u for u in body_sizes if u.name == "abstractMethod")
    assert abstract.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "emptyBody")
    assert empty.body_node_count == 1


def test_body_node_count_for_single_return_statement(example):
    add = next(u for u in example if u.name == "add")
    assert add.body_node_count == 7


def test_body_node_count_ignores_attributes_and_counts_method_logic(body_sizes):
    annotated = next(u for u in body_sizes if u.name == "annotatedWithLogic")
    assert annotated.body_node_count == 28


def test_strips_every_comment_style_from_body(comments):
    assert comments[0].body == (
        "public function withComments(int $a, int $b): int\n"
        "    {\n"
        "        \n"
        "        $sum = $a + $b; \n"
        "        \n"
        '        $url = "http://not-a-comment";\n'
        "        return $sum;\n"
        "    }"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash


def test_arrow_function_bound_to_variable_takes_binding_name(closures):
    doubler = next(u for u in closures if u.name == "doubler")
    assert doubler.body == "fn(int $x) => $x * 2"


def test_closure_bound_to_member_takes_member_name(closures):
    on_complete = next(u for u in closures if u.name == "onComplete")
    assert on_complete.body == 'function () {\n            echo "done";\n        }'


def test_callback_arrow_function_without_binding_is_unknown(closures):
    callbacks = [u for u in closures if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {"fn(int $v) => $v + 1"}


def test_nested_closure_emitted_alongside_enclosing_method(closures):
    assert "build" in {u.name for u in closures}
    assert "fn(int $x) => $x * 2" in {u.body for u in closures}
