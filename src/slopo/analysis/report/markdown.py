from datetime import datetime
from pathlib import Path

from slopo.analysis.ignore import cluster_hash
from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.naming import cluster_filename

_LANG_MAP = {
    ".cjs": "javascript",
    ".cs": "csharp",
    ".ex": "elixir",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "jsx",
    ".kt": "kotlin",
    ".mjs": "javascript",
    ".php": "php",
    ".py": "python",
    ".rs": "rust",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def build_index_markdown(
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
    generated_at: datetime,
) -> str:
    total = len(clusters)
    headers = ["Cluster", "Hash", "Score", "Code units", "Unique files"]
    rows: list[list[str]] = []
    for i, cluster in enumerate(clusters, 1):
        link = f"[Cluster {i}]({cluster_filename(i, total)})"
        records = [units[uid] for uid in cluster.unit_ids]
        for uid in cluster.unit_ids:
            records.extend(duplicates.get(uid, []))
        unit_count = len(records)
        unique_files = len({record.file_path for record in records})
        rows.append(
            [
                link,
                cluster_hash(cluster, units),
                _similarity_range(cluster),
                str(unit_count),
                str(unique_files),
            ]
        )
    timestamp = generated_at.strftime("%Y-%m-%d %H:%M:%S")
    return f"Generated {timestamp}\n\n{_format_table(headers, rows)}"


def build_cluster_markdown(
    number: int,
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    lines: list[str] = [
        f"## ({number}) score {_similarity_range(cluster)}\n",
        f"Hash: `{cluster_hash(cluster, units)}`\n",
    ]
    for unit_id in cluster.unit_ids:
        lines.append("---\n")
        unit = units[unit_id]
        lang = _lang_tag(unit.file_path)
        records = [unit, *duplicates.get(unit_id, [])]
        for record in sorted(records, key=lambda r: r.file_path):
            lines.append(
                f"- `{record.file_path}` lines {record.start_line}-{record.end_line}"
            )
        lines.append(f"\n```{lang}\n{unit.body}\n```\n")
    return "\n".join(lines)


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [
        max(len(headers[col]), *(len(row[col]) for row in rows))
        if rows
        else len(headers[col])
        for col in range(len(headers))
    ]

    def render(cells: list[str]) -> str:
        padded = [cells[col].ljust(widths[col]) for col in range(len(cells))]
        return "| " + " | ".join(padded) + " |"

    separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    lines = [render(headers), separator]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines) + "\n"


def _similarity_range(cluster: Cluster) -> str:
    if cluster.min_similarity == cluster.max_similarity:
        return f"{cluster.min_similarity:.2f}"
    return f"{cluster.min_similarity:.2f}-{cluster.max_similarity:.2f}"


def _lang_tag(file_path: str) -> str:
    return _LANG_MAP.get(Path(file_path).suffix, "")
