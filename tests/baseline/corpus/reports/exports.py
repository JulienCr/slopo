def export_rows_to_csv(rows, headers):
    lines = [",".join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines)


def export_rows_to_json(rows, fields):
    import json

    records = []
    for row in rows:
        record = {field: row.get(field) for field in fields}
        records.append(record)
    return json.dumps(records)


def paginate_records(records, page_size, page_number):
    start = page_number * page_size
    end = start + page_size
    page_items = records[start:end]
    has_more = end < len(records)
    return {"items": page_items, "has_more": has_more}


def summarize_report_rows(rows, numeric_field):
    total = 0
    count = 0
    for row in rows:
        value = row.get(numeric_field)
        if value is None:
            continue
        total += value
        count += 1
    average = total / count if count else 0
    return {"total": total, "count": count, "average": round(average, 2)}
