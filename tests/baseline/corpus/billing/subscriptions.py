def calculate_prorated_charge(monthly_rate, days_used, days_in_month):
    if days_in_month <= 0:
        raise ValueError("invalid days_in_month")
    if days_used < 0:
        raise ValueError("invalid days_used")
    daily_rate = monthly_rate / days_in_month
    charge = daily_rate * days_used
    return round(charge, 2)


def calculate_refund_amount(paid_amount, days_used, total_days):
    if total_days <= 0:
        raise ValueError("invalid total_days")
    unused_ratio = (total_days - days_used) / total_days
    if unused_ratio < 0:
        unused_ratio = 0
    refund = paid_amount * unused_ratio
    return round(refund, 2)
