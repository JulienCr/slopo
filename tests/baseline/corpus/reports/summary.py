def aggregate_daily_totals(records):
    totals = {}
    for record in records:
        day = record.get("day")
        amount = record.get("amount", 0)
        if day not in totals:
            totals[day] = 0
        totals[day] += amount
    for day in totals:
        totals[day] = round(totals[day], 2)
    return totals


def aggregate_weekly_totals(records):
    totals = {}
    for record in records:
        week = record.get("week")
        amount = record.get("amount", 0)
        if week not in totals:
            totals[week] = 0
        totals[week] += amount
    for week in totals:
        totals[week] = round(totals[week], 2)
    return totals


def aggregate_monthly_average(records):
    sums = {}
    counts = {}
    for record in records:
        month = record.get("month")
        amount = record.get("amount", 0)
        sums[month] = sums.get(month, 0) + amount
        counts[month] = counts.get(month, 0) + 1
    averages = {}
    for month in sums:
        averages[month] = round(sums[month] / counts[month], 2)
    return averages
