def validate_email(address):
    if "@" not in address:
        return False
    local_part, _, domain = address.partition("@")
    if not local_part or not domain:
        return False
    if "." not in domain:
        return False
    return True


def validate_phone(number):
    digits = "".join(c for c in number if c.isdigit())
    if len(digits) < 10 or len(digits) > 15:
        return False
    if number.strip().startswith("+"):
        return len(digits) >= 11
    return True


def is_username_valid(username):
    if len(username) < 3 or len(username) > 20:
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_")
    return all(c in allowed for c in username.lower())


def validate_batch(items):
    valid_items = []
    for item in items:
        if item.get("id") is None:
            continue
        if item.get("value", 0) < 0:
            continue
        valid_items.append(item)
    return valid_items
