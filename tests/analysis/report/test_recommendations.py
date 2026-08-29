from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.recommendations import build_recommendations_markdown
from slopo.analysis.triage import ClusterEvidence

_UNITS = {
    1: UnitRecord(
        1, "src/a/verify.py", "verifyIdClip", 10, 20, "def verifyIdClip(): ...", "h1"
    ),
    2: UnitRecord(
        2, "src/b/verify.py", "verifyClipId", 12, 22, "def verifyClipId(): ...", "h2"
    ),
    3: UnitRecord(3, "src/c/helper.py", "helper", 1, 5, "def helper(): pass", "h3"),
    4: UnitRecord(4, "src/c/helper.py", "helper2", 7, 11, "def helper2(): pass", "h4"),
}
_CLUSTERS = [
    Cluster([1, 2], 0.80, 0.90),
    Cluster([3, 4], 0.99, 0.99),
]

_DRIFTED = ClusterEvidence(
    number=1,
    lines=10,
    members=2,
    files=2,
    all_exact=False,
    names=("verifyClipId", "verifyIdClip"),
    same_name=False,
    max_path_hops=2,
    adjacent_in_file=False,
    drift="- x\n+ y\n",
    score_min=0.80,
    score_max=0.90,
    value=9.0,
    verdict="likely-real",
    reasons=("large body", "names differ but shapes match"),
)

_ARTIFACT = ClusterEvidence(
    number=2,
    lines=4,
    members=2,
    files=1,
    all_exact=True,
    names=("helper", "helper2"),
    same_name=False,
    max_path_hops=0,
    adjacent_in_file=True,
    drift=None,
    score_min=0.99,
    score_max=0.99,
    value=1.0,
    verdict="likely-artifact",
    reasons=("adjacent in the same file",),
)


def test_intro_reports_totals():
    text = build_recommendations_markdown([_DRIFTED, _ARTIFACT], _CLUSTERS, _UNITS, {})

    assert "2 clusters, 1 worth a look, 1 folded" in text


def test_drift_is_rendered_ahead_of_the_evidence_line():
    text = build_recommendations_markdown([_DRIFTED], _CLUSTERS, _UNITS, {})

    drift_pos = text.index("already diverged")
    evidence_pos = text.index("10 lines, 2 members")
    assert drift_pos < evidence_pos
    assert "- x\n+ y" in text


def test_section_includes_locations_and_draft_issue():
    text = build_recommendations_markdown([_DRIFTED], _CLUSTERS, _UNITS, {})

    assert "src/a/verify.py:10-20" in text
    assert "src/b/verify.py:12-22" in text
    assert "**Draft issue: Reconcile drifted duplicate:" in text
    assert "Verdict: likely-real" in text


def test_artifacts_are_collapsed_into_a_single_list():
    text = build_recommendations_markdown([_DRIFTED, _ARTIFACT], _CLUSTERS, _UNITS, {})

    assert "## Likely indexing artifacts" in text
    assert "Cluster 2: src/c/helper.py:1-5, src/c/helper.py:7-11" in text
    # only one heading for the artifact cluster, not a full section
    assert "## Cluster 2" not in text


def test_duplicates_are_folded_into_locations():
    dup = UnitRecord(
        5, "src/d/verify.py", "verifyIdClip", 1, 9, "def verifyIdClip(): ...", "h1"
    )

    text = build_recommendations_markdown([_DRIFTED], _CLUSTERS, _UNITS, {1: [dup]})

    assert "src/d/verify.py:1-9" in text
