from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.tsx import parse

FIXTURES = Path(__file__).parent / "fixtures" / "tsx"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.tsx").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.tsx").read_bytes(), "raw")


def test_extracts_function_arrow_and_method_components(example):
    assert [u.name for u in example] == ["Greeting", "Counter", "double", "render"]


def test_function_component_body_exact(example):
    greeting = next(u for u in example if u.name == "Greeting")
    assert greeting.body == (
        "function Greeting(props: { name: string }): JSX.Element {\n"
        "  return <div>Hello, {props.name}!</div>;\n"
        "}"
    )


def test_arrow_component_named_from_binding(example):
    counter = next(u for u in example if u.name == "Counter")
    assert counter.body == "(): JSX.Element => {\n  return <span>0</span>;\n}"


def test_line_numbers_are_one_based_and_correct(example):
    greeting = next(u for u in example if u.name == "Greeting")
    assert greeting.start_line == 1
    assert greeting.end_line == 3


def test_plain_helper_function_and_class_method_are_extracted(example):
    double = next(u for u in example if u.name == "double")
    assert double.body_node_count == 5
    render = next(u for u in example if u.name == "render")
    assert render.body_node_count == 8


def test_strips_line_block_and_doc_comments_from_body(comments):
    assert comments[0].body == (
        "function Banner(name: string): JSX.Element {\n"
        "  \n"
        "  const label = `Hi, ${name}`; \n"
        '  const docsUrl = "https://example.com/* not a comment */";\n'
        "  return <span>{label}</span>;\n"
        "}"
    )


def test_raw_embed_body_is_exactly_body_when_source_has_comments(comments):
    unit = comments[0]
    assert unit.embed_body == unit.body
    assert unit.embed_hash == unit.body_hash
