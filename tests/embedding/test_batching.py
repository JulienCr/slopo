import pytest

from slopo.embedding.batching import trim_to_char_limit
from slopo.embedding.models import UnembeddedUnit


def _units(*bodies: str) -> list[UnembeddedUnit]:
    return [
        UnembeddedUnit(embed_hash=str(i), embed_body=body)
        for i, body in enumerate(bodies)
    ]


def test_empty_input():
    assert trim_to_char_limit([], 100) == []


def test_all_units_fit():
    units = _units("abc", "def")
    assert trim_to_char_limit(units, 100) == units


def test_trims_at_char_limit():
    units = _units("aaa", "bbb", "ccc")
    assert trim_to_char_limit(units, 6) == units[:2]


def test_single_unit_exceeds_limit():
    units = _units("abcdef")
    with pytest.raises(ValueError):
        trim_to_char_limit(units, 3)


def test_exact_limit():
    units = _units("aaa", "bbb")
    assert trim_to_char_limit(units, 6) == units
