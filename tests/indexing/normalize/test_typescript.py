from slopo.indexing.normalize import normalize
from tests.indexing.normalize.helpers import javascript_function, typescript_function

SOURCE = b"""function add(a: number, b: number): number {
  return a + b;
}

const scale = (value: number, factor: number) => value * factor;

class Box {
  area(width: number, height: number): number {
    return width * height;
  }
}

function greet({ name, greeting }: { name: string; greeting: string }) {
  return greeting + ", " + name;
}
"""


def test_function_declaration_renames_signature_and_body():
    node = typescript_function(SOURCE, 0)
    assert normalize(SOURCE, node, "typescript", "rename_all") == (
        "function f(v1: number, v2: number): number {\n  return v1 + v2;\n}"
    )


def test_arrow_function_assigned_to_const_has_no_own_name_to_keep():
    node = typescript_function(SOURCE, 1)
    assert normalize(SOURCE, node, "typescript", "rename_all") == (
        "(v1: number, v2: number) => v1 * v2"
    )


def test_method_definition_own_name_becomes_f():
    node = typescript_function(SOURCE, 2)
    assert normalize(SOURCE, node, "typescript", "rename_all") == (
        "f(v1: number, v2: number): number {\n    return v1 * v2;\n  }"
    )


def test_destructured_parameter_renames_bindings_by_first_appearance():
    node = typescript_function(SOURCE, 3)
    assert normalize(SOURCE, node, "typescript", "rename_all") == (
        "function f({ v1, v2 }: { name: string; greeting: string }) {\n"
        '  return v2 + ", " + v1;\n'
        "}"
    )


def test_member_expression_keeps_the_property_and_renames_the_object():
    source = b"function totalPrice(item) {\n  return item.price * item.quantity;\n}\n"
    node = typescript_function(source)
    assert normalize(source, node, "typescript", "rename_all") == (
        "function f(v1) {\n  return v1.price * v1.quantity;\n}"
    )


def test_builtins_are_not_collapsed_into_the_same_shape():
    math_source = b"function a(values) {\n  return Math.round(values);\n}\n"
    console_source = b"function b(values) {\n  return console.log(values);\n}\n"

    math_out = normalize(
        math_source, typescript_function(math_source), "typescript", "rename_all"
    )
    console_out = normalize(
        console_source,
        typescript_function(console_source),
        "typescript",
        "rename_all",
    )

    assert math_out != console_out
    assert math_out == "function f(v1) {\n  return Math.round(v1);\n}"
    assert console_out == "function f(v1) {\n  return console.log(v1);\n}"


def test_javascript_is_registered_to_the_same_profile_as_typescript():
    source = b"function add(a, b) {\n  return a + b;\n}\n"
    node = javascript_function(source)
    assert normalize(source, node, "javascript", "rename_all") == (
        "function f(v1, v2) {\n  return v1 + v2;\n}"
    )


def test_parameter_named_like_a_builtin_is_renamed_consistently():
    source = (
        b"function f(console, Math) {\n  console = Math + 1;\n  return console;\n}\n"
    )
    node = typescript_function(source)
    assert normalize(source, node, "typescript", "rename_all") == (
        "function f(v1, v2) {\n  v1 = v2 + 1;\n  return v1;\n}"
    )


def test_destructured_parameter_and_let_declaration_named_like_a_builtin():
    source = (
        b"function f({console}) {\n"
        b"  let Math = console;\n"
        b"  Math += 1;\n"
        b"  return Math;\n"
        b"}\n"
    )
    node = typescript_function(source)
    assert normalize(source, node, "typescript", "rename_all") == (
        "function f({v1}) {\n  let v2 = v1;\n  v2 += 1;\n  return v2;\n}"
    )


def test_two_functions_differing_only_by_a_builtin_named_local_canonicalize_alike():
    console_source = (
        b"function compute(values) {\n  console = values;\n  return console;\n}\n"
    )
    total_source = (
        b"function compute(values) {\n  total = values;\n  return total;\n}\n"
    )
    console_out = normalize(
        console_source, typescript_function(console_source), "typescript", "rename_all"
    )
    total_out = normalize(
        total_source, typescript_function(total_source), "typescript", "rename_all"
    )
    assert console_out == total_out
