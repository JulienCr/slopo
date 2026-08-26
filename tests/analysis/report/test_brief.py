from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.report.brief import build_agent_brief_markdown
from slopo.analysis.triage import ClusterEvidence

_UNITS = {
    1: UnitRecord(
        1, "src/a/verify.py", "verifyIdClip", 10, 20, "def verifyIdClip(): ...", "h1"
    ),
    2: UnitRecord(
        2, "src/b/verify.py", "verifyClipId", 12, 22, "def verifyClipId(): ...", "h2"
    ),
}
_CLUSTERS = [Cluster([1, 2], 0.80, 0.90)]

_EVIDENCE = ClusterEvidence(
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
    verdict="needs-judgment",
    reasons=("names differ but shapes match",),
)


def test_preamble_instructs_reading_the_real_files():
    text = build_agent_brief_markdown([_EVIDENCE], _CLUSTERS, _UNITS, {})

    assert "Open the real files" in text
    assert "not the scanner's" in text


def test_preamble_covers_the_three_verdicts():
    text = build_agent_brief_markdown([_EVIDENCE], _CLUSTERS, _UNITS, {})

    assert "`likely-real`" in text
    assert "`likely-artifact`" in text
    assert "`needs-judgment`" in text


def test_preamble_states_the_divergence_lesson_with_the_worked_case():
    text = build_agent_brief_markdown([_EVIDENCE], _CLUSTERS, _UNITS, {})

    assert "verifyIdClip" in text
    assert "verifyClipId" in text
    assert "diverged" in text


def test_output_format_and_ruling_out_are_specified():
    text = build_agent_brief_markdown([_EVIDENCE], _CLUSTERS, _UNITS, {})

    assert "Recommended action:" in text
    assert "Ruling a cluster out is as valuable as confirming one" in text


def test_cluster_entry_has_locations_and_drift():
    text = build_agent_brief_markdown([_EVIDENCE], _CLUSTERS, _UNITS, {})

    assert "### Cluster 1 (needs-judgment)" in text
    assert "src/a/verify.py:10-20" in text
    assert "src/b/verify.py:12-22" in text
    assert "```diff\n- x\n+ y\n\n```" in text
