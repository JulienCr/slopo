def compute_upgrade_credit(plan_rate, elapsed_days, cycle_days):
    if cycle_days <= 0:
        raise ValueError("invalid cycle_days")
    if elapsed_days < 0:
        raise ValueError("invalid elapsed_days")
    per_day_rate = plan_rate / cycle_days
    credit = per_day_rate * elapsed_days
    return round(credit, 2)
