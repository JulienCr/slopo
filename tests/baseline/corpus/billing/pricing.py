def apply_discount(price, discount_percent):
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("invalid discount percent")
    discount = price * (discount_percent / 100)
    final_price = price - discount
    return round(final_price, 2)


def compute_bulk_price(unit_price, quantity, bulk_threshold=10):
    if quantity >= bulk_threshold:
        unit_price = unit_price * 0.9
    total = unit_price * quantity
    tax = total * 0.08
    return round(total + tax, 2)


def compute_price_per_unit(total_price, quantity):
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    per_unit = total_price / quantity
    rounded = round(per_unit, 4)
    return rounded
