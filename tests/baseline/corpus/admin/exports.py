def export_rows_to_csv(rows, headers):
    lines = [",".join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines)


def export_audit_log(entries):
    formatted = []
    for entry in entries:
        actor = entry.get("actor", "unknown")
        action = entry.get("action", "unknown")
        timestamp = entry.get("timestamp", "")
        formatted.append(f"{timestamp} {actor} {action}")
    return "\n".join(formatted)
