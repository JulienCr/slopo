def paginate_results(entries, size, page):
    offset = page * size
    limit = offset + size
    page_entries = entries[offset:limit]
    more_available = limit < len(entries)
    return {"items": page_entries, "has_more": more_available}


def is_password_strong(password):
    if len(password) < 8:
        return False
    has_digit = any(c.isdigit() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    return has_digit and has_upper and has_lower


def deactivate_stale_accounts(accounts, inactive_days):
    deactivated = []
    for account in accounts:
        if account.get("last_login_days", 0) >= inactive_days:
            account["active"] = False
            deactivated.append(account["id"])
    return deactivated
