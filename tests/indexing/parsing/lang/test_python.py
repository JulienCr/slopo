from pathlib import Path

import pytest

from slopo.indexing.parsing.base import CodeUnit
from slopo.indexing.parsing.lang.python import parse

FIXTURES = Path(__file__).parent / "fixtures" / "python"


@pytest.fixture
def example() -> list[CodeUnit]:
    return parse((FIXTURES / "Example.py").read_bytes(), "raw")


@pytest.fixture
def nested() -> list[CodeUnit]:
    return parse((FIXTURES / "Nested.py").read_bytes(), "raw")


@pytest.fixture
def body_sizes() -> list[CodeUnit]:
    return parse((FIXTURES / "BodySizes.py").read_bytes(), "raw")


@pytest.fixture
def comments() -> list[CodeUnit]:
    return parse((FIXTURES / "Comments.py").read_bytes(), "raw")


def test_extracts_module_functions_and_methods(example):
    assert [u.name for u in example] == [
        "greet",
        "classify",
        "sum_evens",
        "__init__",
        "increment",
    ]


def test_fstring_function_body_exact(example):
    greet = next(u for u in example if u.name == "greet")
    assert greet.body == 'def greet(name):\n    return f"{prefix}, {name}!"'


def test_branching_function_body_exact(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.body == (
        "def classify(n):\n"
        "    if n < 0:\n"
        '        return "negative"\n'
        "    elif n == 0:\n"
        '        return "zero"\n'
        "    else:\n"
        '        return "positive"'
    )


def test_method_body_keeps_class_indentation(example):
    increment = next(u for u in example if u.name == "increment")
    assert increment.body == (
        "def increment(self, by=1):\n"
        "        self.value += by\n"
        "        return self.value"
    )


def test_line_numbers_are_one_based_and_correct(example):
    classify = next(u for u in example if u.name == "classify")
    assert classify.start_line == 8
    assert classify.end_line == 14


def test_nested_function_is_extracted(nested):
    assert [u.name for u in nested] == ["make_adder", "add"]


def test_nested_function_body_exact(nested):
    add = next(u for u in nested if u.name == "add")
    assert add.body == "def add(x):\n        return base + x"


def test_body_node_count_for_pass_body(body_sizes):
    empty = next(u for u in body_sizes if u.name == "empty_body")
    assert empty.body_node_count == 2


def test_body_node_count_for_ellipsis_stub(body_sizes):
    stub = next(u for u in body_sizes if u.name == "stub")
    assert stub.body_node_count == 3


def test_body_node_count_ignores_decorator_and_counts_function_logic(body_sizes):
    fibonacci = next(u for u in body_sizes if u.name == "fibonacci")
    assert fibonacci.body_node_count == 38


def test_strips_line_comments_and_docstrings_but_keeps_string_assignments(comments):
    assert comments[0].body == (
        "def with_comments(a, b):\n"
        "    \n"
        "    \n"
        "    total = a + b  \n"
        '    url = "http://example.com/#section"\n'
        "    return total"
    )


def test_docstring_is_excluded_from_body_node_count(comments):
    assert comments[0].body_node_count == 18
