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


def is_valid_postal_code(code):
    cleaned = code.strip().upper()
    if len(cleaned) < 5 or len(cleaned) > 7:
        return False
    has_digit = any(c.isdigit() for c in cleaned)
    has_letter = any(c.isalpha() for c in cleaned)
    return has_digit or has_letter


def is_valid_zip_code(code):
    cleaned = code.strip().upper()
    if len(cleaned) < 5 or len(cleaned) > 10:
        return False
    has_digit = any(c.isdigit() for c in cleaned)
    has_dash = "-" in cleaned
    return has_digit or has_dash


def is_valid_credit_card_number(number):
    digits = [c for c in number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse_digits = digits[::-1]
    for index, digit_char in enumerate(reverse_digits):
        digit = int(digit_char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0
