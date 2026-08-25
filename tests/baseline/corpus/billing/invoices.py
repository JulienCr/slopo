def calculate_invoice_total(lines, rate):
    running_total = 0
    for line in lines:
        running_total += line["amount"] * line["count"]
    tax_amount = running_total * rate
    invoice_total = running_total + tax_amount
    return round(invoice_total, 2)


def calculate_tax_amount(amount, rate):
    if amount < 0:
        raise ValueError("invalid amount")
    if rate < 0 or rate > 1:
        raise ValueError("invalid rate")
    tax = amount * rate
    return round(tax, 2)


def format_invoice_number(prefix, sequence):
    padded = str(sequence).zfill(6)
    if not prefix.isalpha():
        raise ValueError("prefix must be alphabetic")
    return f"{prefix.upper()}-{padded}"


def build_invoice_line_description(product_name, quantity, unit_price):
    parts = [product_name]
    if quantity > 1:
        parts.append(f"x{quantity}")
    total = quantity * unit_price
    parts.append(f"@ {unit_price:.2f}")
    parts.append(f"= {total:.2f}")
    description = " ".join(parts)
    if len(description) > 80:
        description = description[:77] + "..."
    return description


def compute_invoice_due_date(issue_year, issue_month, issue_day, terms_days):
    import datetime

    issue_date = datetime.date(issue_year, issue_month, issue_day)
    due_date = issue_date + datetime.timedelta(days=terms_days)
    weekday = due_date.weekday()
    if weekday == 5:
        due_date = due_date + datetime.timedelta(days=2)
    elif weekday == 6:
        due_date = due_date + datetime.timedelta(days=1)
    return due_date


def compute_late_fee(balance_due, days_overdue, daily_rate=0.001):
    if days_overdue <= 0:
        return 0.0
    if balance_due <= 0:
        return 0.0
    fee = balance_due * daily_rate * days_overdue
    max_fee = balance_due * 0.25
    if fee > max_fee:
        fee = max_fee
    return round(fee, 2)


def is_invoice_overdue(due_year, due_month, due_day, today_year, today_month, today_day):
    import datetime

    due_date = datetime.date(due_year, due_month, due_day)
    today = datetime.date(today_year, today_month, today_day)
    if today <= due_date:
        return False
    delta = today - due_date
    return delta.days > 0


def summarize_invoice_batch(invoices):
    total_paid = 0
    total_outstanding = 0
    overdue_count = 0
    for invoice in invoices:
        if invoice.get("paid"):
            total_paid += invoice.get("amount", 0)
        else:
            total_outstanding += invoice.get("amount", 0)
            if invoice.get("overdue"):
                overdue_count += 1
    return {
        "paid": round(total_paid, 2),
        "outstanding": round(total_outstanding, 2),
        "overdue_count": overdue_count,
    }


def validate_invoice_line_items(lines):
    errors = []
    for index, line in enumerate(lines):
        if line.get("amount", 0) < 0:
            errors.append(f"line {index}: negative amount")
        if line.get("count", 0) <= 0:
            errors.append(f"line {index}: invalid count")
        description = line.get("description", "")
        if not description.strip():
            errors.append(f"line {index}: missing description")
    return errors


def merge_invoice_adjustments(base_lines, adjustments):
    merged = list(base_lines)
    for adjustment in adjustments:
        target_id = adjustment.get("line_id")
        matched = False
        for line in merged:
            if line.get("id") == target_id:
                line["amount"] = line.get("amount", 0) + adjustment.get("delta", 0)
                matched = True
                break
        if not matched:
            merged.append(
                {
                    "id": target_id,
                    "amount": adjustment.get("delta", 0),
                    "count": 1,
                    "description": adjustment.get("reason", "adjustment"),
                }
            )
    return merged


def compute_invoice_discount_tiers(subtotal):
    tiers = [
        (1000, 0.10),
        (500, 0.05),
        (100, 0.02),
    ]
    for threshold, rate in tiers:
        if subtotal >= threshold:
            return round(subtotal * rate, 2)
    return 0.0


def group_invoices_by_customer(invoices):
    grouped = {}
    for invoice in invoices:
        customer_id = invoice.get("customer_id")
        if customer_id not in grouped:
            grouped[customer_id] = []
        grouped[customer_id].append(invoice)
    for customer_id in grouped:
        grouped[customer_id].sort(key=lambda inv: inv.get("issue_date", ""))
    return grouped


def compute_invoice_running_balance(invoices, payments):
    balance = 0
    for invoice in invoices:
        balance += invoice.get("amount", 0)
    for payment in payments:
        balance -= payment.get("amount", 0)
    if balance < 0:
        balance = 0
    return round(balance, 2)


def redact_invoice_notes(notes, blocked_words):
    words = notes.split()
    redacted = []
    for word in words:
        cleaned = word.strip(".,!?").lower()
        if cleaned in blocked_words:
            redacted.append("*" * len(word))
        else:
            redacted.append(word)
    return " ".join(redacted)


def compute_invoice_totals_by_currency(invoices):
    totals = {}
    for invoice in invoices:
        currency = invoice.get("currency", "USD")
        amount = invoice.get("amount", 0)
        if currency not in totals:
            totals[currency] = 0
        totals[currency] += amount
    for currency in totals:
        totals[currency] = round(totals[currency], 2)
    return totals


def apply_invoice_rounding_policy(amount, policy="nearest_cent"):
    if policy == "nearest_cent":
        return round(amount, 2)
    if policy == "nearest_dollar":
        return round(amount)
    if policy == "round_up_cent":
        cents = amount * 100
        rounded_cents = -(-cents // 1)
        return rounded_cents / 100
    raise ValueError(f"unknown rounding policy: {policy}")


def compute_invoice_aging_buckets(invoices, today_days):
    buckets = {"current": 0, "30": 0, "60": 0, "90": 0}
    for invoice in invoices:
        if invoice.get("paid"):
            continue
        due_days = invoice.get("due_in_days", 0)
        age = today_days - due_days
        amount = invoice.get("amount", 0)
        if age <= 0:
            buckets["current"] += amount
        elif age <= 30:
            buckets["30"] += amount
        elif age <= 60:
            buckets["60"] += amount
        else:
            buckets["90"] += amount
    for key in buckets:
        buckets[key] = round(buckets[key], 2)
    return buckets


def compute_invoice_credit_note_total(credit_notes):
    total = 0
    for note in credit_notes:
        if note.get("voided"):
            continue
        total += note.get("amount", 0)
    return round(total, 2)


def normalize_invoice_reference(reference):
    cleaned = reference.strip().upper()
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace("_", "-")
    if not cleaned.startswith("INV-"):
        cleaned = f"INV-{cleaned}"
    return cleaned


def compute_invoice_payment_plan(total_amount, installments):
    if installments <= 0:
        raise ValueError("installments must be positive")
    base_installment = total_amount / installments
    plan = []
    remaining = total_amount
    for index in range(installments):
        if index == installments - 1:
            amount = round(remaining, 2)
        else:
            amount = round(base_installment, 2)
            remaining -= amount
        plan.append(amount)
    return plan


def dedupe_invoice_attachments(attachments):
    seen_hashes = set()
    unique = []
    for attachment in attachments:
        file_hash = attachment.get("hash")
        if file_hash in seen_hashes:
            continue
        seen_hashes.add(file_hash)
        unique.append(attachment)
    return unique


def compute_invoice_exchange_conversion(amount, source_currency, target_rates):
    if source_currency not in target_rates:
        raise ValueError(f"missing rate for {source_currency}")
    rate = target_rates[source_currency]
    converted = amount * rate
    return round(converted, 2)


def format_receipt_number(prefix, sequence):
    padded = str(sequence).zfill(6)
    if not prefix.isalnum():
        raise ValueError("prefix must be alphanumeric")
    return f"{prefix.lower()}-{padded}"
