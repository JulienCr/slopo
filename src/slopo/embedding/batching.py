from slopo.embedding.models import UnembeddedUnit


def trim_to_char_limit(
    units: list[UnembeddedUnit], max_chars: int
) -> list[UnembeddedUnit]:
    result: list[UnembeddedUnit] = []
    chars = 0
    for unit in units:
        unit_chars = len(unit.embed_body)
        if unit_chars > max_chars:
            raise ValueError(
                f"Unit body ({unit_chars} chars) exceeds max_chars ({max_chars})"
            )
        if chars + unit_chars > max_chars:
            break
        result.append(unit)
        chars += unit_chars
    return result
