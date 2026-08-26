from datetime import datetime
from pathlib import Path

from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.filesystem import write_report
from slopo.analysis.report.markdown import build_cluster_markdown, build_index_markdown

_UNITS = {
    1: UnitRecord(1, "src/A.java", "foo", 10, 20, "int foo() {}", "hashA"),
    2: UnitRecord(2, "src/B.java", "bar", 5, 15, "int bar() {}", "hashB"),
}
_CLUSTERS = [Cluster([1, 2], 0.95, 0.97)]


def test_creates_output_directory_including_missing_parents(tmp_path: Path):
    output_dir = tmp_path / "nested" / "slopo-report"

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    assert (output_dir / "index.md").is_file()
    assert (output_dir / "cluster-1.md").is_file()


def test_writes_into_an_existing_directory(tmp_path: Path):
    output_dir = tmp_path / "report"
    output_dir.mkdir()

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    assert (output_dir / "index.md").is_file()
    assert (output_dir / "cluster-1.md").is_file()


def test_leaves_files_not_owned_by_the_tool(tmp_path: Path):
    output_dir = tmp_path / "report"
    output_dir.mkdir()
    (output_dir / "README.md").write_text("keep me")
    (output_dir / "cluster-notes.md").write_text("keep me")
    (output_dir / "cluster-1.txt").write_text("keep me")

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    assert (output_dir / "README.md").read_text() == "keep me"
    assert (output_dir / "cluster-notes.md").read_text() == "keep me"
    assert (output_dir / "cluster-1.txt").read_text() == "keep me"


def test_removes_stale_cluster_files_from_a_larger_previous_run(tmp_path: Path):
    output_dir = tmp_path / "report"

    many = [Cluster([1, 2], 0.95, 0.97) for _ in range(12)]
    write_report(many, _UNITS, output_dir, {})
    assert (output_dir / "cluster-01.md").is_file()
    assert (output_dir / "cluster-12.md").is_file()

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    assert (output_dir / "cluster-1.md").is_file()
    assert not (output_dir / "cluster-01.md").exists()
    assert not (output_dir / "cluster-12.md").exists()


def test_writes_recommendations_and_agent_brief(tmp_path: Path):
    output_dir = tmp_path / "report"

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    assert (output_dir / "recommendations.md").is_file()
    assert (output_dir / "agent-brief.md").is_file()


def test_index_and_cluster_files_stay_byte_identical_to_the_markdown_builders(
    tmp_path: Path,
):
    output_dir = tmp_path / "report"

    write_report(_CLUSTERS, _UNITS, output_dir, {})

    actual_index = (output_dir / "index.md").read_text(encoding="utf-8")
    timestamp_line = actual_index.splitlines()[0]
    generated_at = datetime.strptime(timestamp_line, "Generated %Y-%m-%d %H:%M:%S")
    expected_index = build_index_markdown(_CLUSTERS, _UNITS, {}, generated_at)
    assert actual_index == expected_index

    actual_cluster = (output_dir / "cluster-1.md").read_text(encoding="utf-8")
    expected_cluster = build_cluster_markdown(1, _CLUSTERS[0], _UNITS, {})
    assert actual_cluster == expected_cluster


def test_a_stale_recommendations_file_does_not_survive_a_smaller_rerun(
    tmp_path: Path,
):
    output_dir = tmp_path / "report"
    many = [Cluster([1, 2], 0.95, 0.97) for _ in range(3)]

    write_report(many, _UNITS, output_dir, {})
    large_recommendations = (output_dir / "recommendations.md").read_text(
        encoding="utf-8"
    )

    write_report(_CLUSTERS, _UNITS, output_dir, {})
    rerun_recommendations = (output_dir / "recommendations.md").read_text(
        encoding="utf-8"
    )

    assert "3 clusters" in large_recommendations
    assert "1 clusters" in rerun_recommendations
