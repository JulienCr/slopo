from pathlib import Path

from slopo.indexing.normalize import normalize
from tests.indexing.normalize.helpers import python_function

FIXTURES = Path(__file__).parent / "fixtures" / "python"


def test_headline_pair_is_byte_identical_at_rename_all():
    vector_source = (FIXTURES / "vector_length.py").read_bytes()
    segment_source = (FIXTURES / "segment_magnitude.py").read_bytes()

    vector_out = normalize(
        vector_source, python_function(vector_source), "python", "rename_all"
    )
    segment_out = normalize(
        segment_source, python_function(segment_source), "python", "rename_all"
    )

    assert vector_out == segment_out
    assert vector_out == (
        "def f(v1):\n"
        "    v2 = 0\n"
        "    for v3 in v1:\n"
        "        v2 += v3 * v3\n"
        "    v4 = v2**0.5\n"
        "    return round(v4, 4)"
    )


def test_rename_locals_keeps_the_function_name():
    source = (FIXTURES / "vector_length.py").read_bytes()
    node = python_function(source)
    assert normalize(source, node, "python", "rename_locals") == (
        "def compute_vector_length(v1):\n"
        "    v2 = 0\n"
        "    for v3 in v1:\n"
        "        v2 += v3 * v3\n"
        "    v4 = v2**0.5\n"
        "    return round(v4, 4)"
    )


def test_rename_all_literals_zeroes_numbers_on_top_of_rename_all():
    source = (FIXTURES / "vector_length.py").read_bytes()
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all_literals") == (
        "def f(v1):\n"
        "    v2 = 0\n"
        "    for v3 in v1:\n"
        "        v2 += v3 * v3\n"
        "    v4 = v2**0\n"
        "    return round(v4, 0)"
    )


def test_string_literal_becomes_empty_string_at_rename_all_literals():
    source = b'def greet(name):\n    message = "Hello, " + name\n    return message\n'
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all_literals") == (
        'def f(v1):\n    v2 = "" + v1\n    return v2'
    )


def test_attribute_position_keeps_the_property_and_renames_the_object():
    source = b"def total_price(item):\n    return item.price * item.quantity\n"
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all") == (
        "def f(v1):\n    return v1.price * v1.quantity"
    )


def test_builtins_are_not_collapsed_into_the_same_shape():
    round_source = b"def a(values):\n    return round(values, 2)\n"
    sorted_source = b"def b(values):\n    return sorted(values)\n"

    round_out = normalize(
        round_source, python_function(round_source), "python", "rename_all"
    )
    sorted_out = normalize(
        sorted_source, python_function(sorted_source), "python", "rename_all"
    )

    assert round_out != sorted_out
    assert round_out == "def f(v1):\n    return round(v1, 2)"
    assert sorted_out == "def f(v1):\n    return sorted(v1)"


def test_numbering_follows_first_appearance_not_first_use():
    source = b"def f(a, b):\n    return b + a\n"
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all") == (
        "def f(v1, v2):\n    return v2 + v1"
    )


def test_nested_function_does_not_corrupt_numbering_or_spans():
    source = (
        b"def outer(x):\n"
        b"    def inner(y):\n"
        b"        return y + x\n"
        b"    return inner(x) + x\n"
    )
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all") == (
        "def f(v1):\n    def v2(v3):\n        return v3 + v1\n    return v2(v1) + v1"
    )


def test_non_ascii_identifiers_and_strings_keep_spans_aligned():
    source = (
        'def greet(名前):\n    message = "こんにちは、" + 名前\n    return message\n'
    ).encode("utf-8")
    node = python_function(source)

    assert normalize(source, node, "python", "rename_all") == (
        'def f(v1):\n    v2 = "こんにちは、" + v1\n    return v2'
    )
    assert normalize(source, node, "python", "rename_all_literals") == (
        'def f(v1):\n    v2 = "" + v1\n    return v2'
    )


def test_keyword_argument_name_is_kept_but_its_value_is_renamed():
    source = b"def f(x):\n    return foo(x, key=x)\n"
    node = python_function(source)
    assert normalize(source, node, "python", "rename_all") == (
        "def f(v1):\n    return v2(v1, key=v1)"
    )
