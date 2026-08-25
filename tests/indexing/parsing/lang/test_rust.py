from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.rust import parse

FIXTURES = Path(__file__).parent / "fixtures" / "rust"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.rs").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.rs").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.rs").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.rs").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.rs").read_bytes(), "raw")


@pytest.fixture
def closures() -> list[CodeUnit]:
    return parse((FIXTURES / "Closures.rs").read_bytes(), "raw")


def test_extracts_methods_and_free_functions(example):
    assert [u.name for u in example if u.name != "<unknown>"] == [
        "greet",
        "classify",
        "normalize",
        "sum_evens",
    ]


def test_inherent_method_body_exact(example):
    greet = next(u for u in example if u.name == "greet")
    assert greet.body == (
        "pub fn greet(&self, name: &str) -> String {\n"
        '        format!("{}, {}!", self.prefix, name)\n'
        "    }"
    )


def test_match_function_body_exact(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.body == (
        "pub fn classify(n: i32) -> &'static str {\n"
        "        match n {\n"
        '            i32::MIN..=-1 => "negative",\n'
        '            0 => "zero",\n'
        '            _ => "positive",\n'
        "        }\n"
        "    }"
    )


def test_line_numbers_are_one_based_and_correct(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.start_line == 10
    assert classify.end_line == 16


def test_method_inside_module_is_extracted(nested):
    assert [u.name for u in nested] == ["area"]


def test_local_function_in_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body if u.name != "<unknown>"] == [
        "outer_function",
        "increment",
    ]


def test_local_function_emitted_alongside_enclosing_function(nested_in_body):
    increment = next(u for u in nested_in_body if u.name == "increment")
    assert increment.body == "fn increment(n: i32) -> i32 {\n        n + 1\n    }"


def test_body_node_count_is_zero_for_signature_without_body(body_sizes):
    external = next(u for u in body_sizes if u.name == "external_function")
    assert external.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "empty_body")
    assert empty.body_node_count == 1


def test_body_node_count_for_function_with_logic(body_sizes):
    with_logic = next(u for u in body_sizes if u.name == "with_logic")
    assert with_logic.body_node_count == 29


def test_strips_line_block_and_doc_comments_from_body(comments):
    with_comments = next(u for u in comments if u.name == "with_comments")
    assert with_comments.body == (
        "pub fn with_comments(a: i32, b: i32) -> i32 {\n"
        "    \n"
        "    let sum = a + b; \n"
        '    let url = "http://not-a-comment";\n'
        "    let _ = url;\n"
        "    sum\n"
        "}"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    with_comments = next(u for u in comments if u.name == "with_comments")
    assert with_comments.embed_body == with_comments.body
    assert with_comments.embed_hash == with_comments.body_hash


def test_closure_bound_to_variable_takes_binding_name(closures):
    doubler = next(u for u in closures if u.name == "doubler")
    assert doubler.body == "|x: i32| x * 2"


def test_closure_assigned_to_struct_field_takes_field_name(closures):
    on_complete = next(u for u in closures if u.name == "on_complete")
    assert on_complete.body == '|| {\n        println!("done");\n    }'


def test_callback_closure_without_binding_is_unknown(closures):
    unknown_bodies = {u.body for u in closures if u.name == "<unknown>"}
    assert (
        "|v| {\n            let scaled = doubler(*v);\n            scaled + 1\n        }"
        in unknown_bodies
    )
