from datetime import datetime
from pathlib import Path

from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.brief import build_agent_brief_markdown
from slopo.analysis.report.markdown import (
    build_cluster_markdown,
    build_index_markdown,
)
from slopo.analysis.report.naming import (
    AGENT_BRIEF_FILENAME,
    CLUSTER_FILE_GLOB,
    CLUSTER_FILE_RE,
    RECOMMENDATIONS_FILENAME,
    cluster_filename,
)
from slopo.analysis.report.recommendations import build_recommendations_markdown
from slopo.analysis.triage import build_evidence

_OWNED_FILES = ("index.md", RECOMMENDATIONS_FILENAME, AGENT_BRIEF_FILENAME)


def write_report(
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    output_dir: Path,
    duplicates: dict[int, list[UnitRecord]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _clean_report_dir(output_dir)

    total = len(clusters)
    (output_dir / "index.md").write_text(
        build_index_markdown(clusters, units, duplicates, datetime.now()),
        encoding="utf-8",
    )
    for i, cluster in enumerate(clusters, 1):
        filename = cluster_filename(i, total)
        (output_dir / filename).write_text(
            build_cluster_markdown(i, cluster, units, duplicates), encoding="utf-8"
        )

    evidence = build_evidence(clusters, units, duplicates)
    (output_dir / RECOMMENDATIONS_FILENAME).write_text(
        build_recommendations_markdown(evidence, clusters, units, duplicates),
        encoding="utf-8",
    )
    (output_dir / AGENT_BRIEF_FILENAME).write_text(
        build_agent_brief_markdown(evidence),
        encoding="utf-8",
    )


def _clean_report_dir(output_dir: Path) -> None:
    for name in _OWNED_FILES:
        path = output_dir / name
        if path.is_file():
            path.unlink()
    for path in output_dir.glob(CLUSTER_FILE_GLOB):
        if CLUSTER_FILE_RE.fullmatch(path.name):
            path.unlink()
