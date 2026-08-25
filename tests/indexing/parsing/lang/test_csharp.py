from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.csharp import parse

FIXTURES = Path(__file__).parent / "fixtures" / "csharp"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.cs").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.cs").read_bytes(), "raw")


@pytest.fixture
def nested_in_body() -> list[CodeUnit]:
    return parse((FIXTURES / "NestedInBody.cs").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.cs").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.cs").read_bytes(), "raw")


@pytest.fixture
def lambdas() -> list[CodeUnit]:
    return parse((FIXTURES / "Lambdas.cs").read_bytes(), "raw")


def test_extracts_constructor_and_methods(example):
    assert [u.name for u in example] == ["Rectangle", "Area", "ToString"]


def test_block_body_exact(example):
    area = next(u for u in example if u.name == "Area")
    assert (
        area.body
        == "public double Area()\n    {\n        return _width * _height;\n    }"
    )


def test_expression_bodied_method_body_exact(example):
    to_string = next(u for u in example if u.name == "ToString")
    assert (
        to_string.body
        == 'public override string ToString() => $"Rectangle({_width}x{_height})";'
    )


def test_line_numbers_are_one_based_and_correct(example):
    area = next(u for u in example if u.name == "Area")
    assert area.start_line == 14
    assert area.end_line == 17


def test_methods_in_nested_class_are_extracted(nested):
    assert [u.name for u in nested] == ["Total", "IsValid"]


def test_nested_class_method_body_exact(nested):
    is_valid = next(u for u in nested if u.name == "IsValid")
    assert (
        is_valid.body
        == "public bool IsValid(decimal amount)\n        {\n            return amount >= 0;\n        }"
    )


def test_local_function_in_body_is_extracted(nested_in_body):
    assert [u.name for u in nested_in_body] == ["Indent", "Pad"]


def test_local_function_emitted_alongside_enclosing_method(nested_in_body):
    pad = next(u for u in nested_in_body if u.name == "Pad")
    assert pad.body == "string Pad(string line) => new string(' ', spaces) + line;"


def test_body_node_count_is_zero_for_interface_method(body_sizes):
    area = next(u for u in body_sizes if u.name == "Area")
    assert area.body_node_count == 0


def test_body_node_count_counts_only_block_for_empty_body(body_sizes):
    reset = next(u for u in body_sizes if u.name == "Reset")
    assert reset.body_node_count == 1


def test_body_node_count_for_single_return_statement(body_sizes):
    radius = next(u for u in body_sizes if u.name == "Radius")
    assert radius.body_node_count == 5


def test_body_node_count_ignores_attributes_and_counts_method_logic(body_sizes):
    annotated = next(u for u in body_sizes if u.name == "Diameter")
    assert annotated.body_node_count == 29


def test_strips_line_block_and_doc_comments_from_body(comments):
    assert comments[0].body == (
        "public string BuildPath(string resource, int id)\n"
        "    {\n"
        "        \n"
        '        string path = resource + "/" + id;\n'
        "        \n"
        '        string endpoint = "https://api.example.com // v1";\n'
        '        return endpoint + "/" + path;\n'
        "    }"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash


def test_lambda_bound_to_variable_takes_binding_name(lambdas):
    doubler = next(u for u in lambdas if u.name == "doubler")
    assert doubler.body == "x => x * 2"


def test_anonymous_method_bound_to_member_takes_member_name(lambdas):
    on_error = next(u for u in lambdas if u.name == "OnError")
    assert on_error.body == (
        "delegate(Exception ex)\n"
        "        {\n"
        "            Console.WriteLine(ex.Message);\n"
        "        }"
    )


def test_callback_lambda_without_binding_is_unknown(lambdas):
    callbacks = [u for u in lambdas if u.name == "<unknown>"]
    assert {u.body for u in callbacks} == {
        "v => v > 0",
        "v =>\n"
        "            {\n"
        "                int scaled = doubler(v);\n"
        "                return scaled + 1;\n"
        "            }",
    }


def test_nested_lambda_emitted_alongside_enclosing_method(lambdas):
    bodies = {u.body for u in lambdas}
    block_bodied_lambda = (
        "v =>\n"
        "            {\n"
        "                int scaled = doubler(v);\n"
        "                return scaled + 1;\n"
        "            }"
    )
    assert "Transform" in {u.name for u in lambdas}
    assert block_bodied_lambda in bodies
