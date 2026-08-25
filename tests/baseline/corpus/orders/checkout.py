def compute_order_total(items, tax_rate):
    subtotal = 0
    for item in items:
        subtotal += item["price"] * item["qty"]
    tax = subtotal * tax_rate
    grand_total = subtotal + tax
    return round(grand_total, 2)


def apply_coupon_discount(amount, coupon_percent):
    if coupon_percent < 0 or coupon_percent > 100:
        raise ValueError("invalid coupon percent")
    if amount <= 0:
        raise ValueError("amount must be positive")
    discount = amount * (coupon_percent / 100)
    final_amount = amount - discount
    return round(final_amount, 2)


def calculate_shipping_cost(weight, distance):
    if weight <= 0:
        raise ValueError("invalid weight")
    base_rate = 5.0
    cost = base_rate + (weight * 0.5) + (distance * 0.1)
    return round(cost, 2)


def merge_cart_items(existing_items, new_items):
    merged = dict(existing_items)
    for sku, quantity in new_items.items():
        if sku in merged:
            merged[sku] += quantity
        else:
            merged[sku] = quantity
    return merged
