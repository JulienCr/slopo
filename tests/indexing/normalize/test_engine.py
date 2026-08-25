import pytest

from slopo.indexing.normalize import LEVELS, normalize
from tests.indexing.normalize.helpers import python_function, typescript_function

SOURCE = b"def add(a, b):\n    return a + b\n"


def test_raw_returns_source_text_unchanged():
    node = python_function(SOURCE)
    assert (
        normalize(SOURCE, node, "python", "raw") == "def add(a, b):\n    return a + b"
    )


def test_unsupported_language_returns_text_unchanged():
    node = typescript_function(b"function add(a, b) {\n  return a + b;\n}\n")
    text = normalize(
        b"function add(a, b) {\n  return a + b;\n}\n", node, "rust", "rename_all"
    )
    assert text == "function add(a, b) {\n  return a + b;\n}"


def test_unknown_level_raises_value_error():
    node = python_function(SOURCE)
    with pytest.raises(ValueError):
        normalize(SOURCE, node, "python", "bogus_level")


def test_unknown_level_raises_even_for_unsupported_language():
    node = python_function(SOURCE)
    with pytest.raises(ValueError):
        normalize(SOURCE, node, "rust", "bogus_level")


def test_levels_tuple_matches_the_interface_contract():
    assert LEVELS == ("raw", "rename_locals", "rename_all", "rename_all_literals")


def test_levels_are_cumulative():
    source = b'def scale(value):\n    return value * 2 + "!"\n'
    node = python_function(source)

    locals_only = normalize(source, node, "python", "rename_locals")
    all_names = normalize(source, node, "python", "rename_all")
    all_literals = normalize(source, node, "python", "rename_all_literals")

    assert locals_only == 'def scale(v1):\n    return v1 * 2 + "!"'
    assert all_names == 'def f(v1):\n    return v1 * 2 + "!"'
    assert all_literals == 'def f(v1):\n    return v1 * 0 + ""'
