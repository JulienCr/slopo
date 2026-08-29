import re

from slopo.analysis.report.brief import build_agent_brief_markdown
from slopo.analysis.report.naming import RECOMMENDATIONS_FILENAME
from slopo.analysis.triage import ClusterEvidence

_REAL = ClusterEvidence(
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


def test_preamble_instructs_reading_the_real_files():
    text = build_agent_brief_markdown([_REAL])

    assert "Open the real files" in text
    assert "not the scanner's" in text


def test_preamble_covers_the_three_verdicts():
    text = build_agent_brief_markdown([_REAL])

    assert "`likely-real`" in text
    assert "`likely-artifact`" in text
    assert "`needs-judgment`" in text


def test_preamble_states_the_divergence_lesson_with_the_worked_case():
    text = build_agent_brief_markdown([_REAL])

    assert "verifyIdClip" in text
    assert "verifyClipId" in text
    assert "diverged" in text


def test_output_format_and_ruling_out_are_specified():
    text = build_agent_brief_markdown([_REAL])

    assert "Recommended action:" in text
    assert "Ruling a cluster out is as valuable as confirming one" in text


def test_carries_no_cluster_data():
    text = build_agent_brief_markdown([_REAL, _ARTIFACT])

    assert "```diff" not in text
    assert not re.search(r"[\w./-]+\.\w+:\d+-\d+", text)
    assert not re.search(r"### Cluster \d", text)


def test_names_the_recommendations_file_from_the_shared_constant():
    text = build_agent_brief_markdown([_REAL])

    assert f"`{RECOMMENDATIONS_FILENAME}`" in text


def test_counts_match_the_recommendations_split():
    text = build_agent_brief_markdown([_REAL, _ARTIFACT])

    assert "2 clusters" in text
    assert "1 worth a look" in text
    assert "1 folded into its indexing-artifact list" in text
