def format_currency(amount, currency="USD"):
    """Format a numeric amount as a two-decimal currency string."""
    # round to the nearest cent before splitting into dollars and cents
    cents = round(amount * 100)
    dollars = cents // 100
    remainder = cents % 100
    if remainder < 10:
        return f"{dollars}.0{remainder} {currency}"  # pad single-digit cents
    return f"{dollars}.{remainder} {currency}"


def truncate_with_ellipsis(text, max_length):
    """Shorten text to max_length, adding an ellipsis if it was cut."""
    if len(text) <= max_length:
        return text
    # leave room for the three-character ellipsis suffix
    cutoff = max_length - 3
    if cutoff < 0:
        cutoff = 0
    return text[:cutoff] + "..."
