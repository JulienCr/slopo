from slopo.analysis import triage
from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.triage import ClusterEvidence, build_evidence


def _unit(
    unit_id: int,
    file_path: str = "src/a.py",
    name: str = "f",
    start: int = 1,
    end: int = 10,
    body: str = "body",
    body_hash: str = "hash",
) -> UnitRecord:
    return UnitRecord(
        unit_id=unit_id,
        file_path=file_path,
        name=name,
        start_line=start,
        end_line=end,
        body=body,
        body_hash=body_hash,
    )


def _cluster(
    unit_ids: list[int], min_sim: float = 0.9, max_sim: float = 0.95
) -> Cluster:
    return Cluster(unit_ids=unit_ids, min_similarity=min_sim, max_similarity=max_sim)


def _only(evidence: list[ClusterEvidence]) -> ClusterEvidence:
    assert len(evidence) == 1
    return evidence[0]


# --- empty input ---


def test_empty_input_returns_empty_list():
    assert build_evidence([], {}, {}) == []


# --- membership counting, folded exact duplicates included ---


def test_membership_counts_folded_exact_duplicates():
    units = {
        1: _unit(1, file_path="src/a.py", body_hash="x"),
        2: _unit(2, file_path="src/b.py", body_hash="y"),
    }
    dup = _unit(3, file_path="src/c.py", body_hash="x")
    duplicates = {1: [dup]}
    clusters = [_cluster([1, 2])]

    evidence = _only(build_evidence(clusters, units, duplicates))

    assert evidence.members == 3
    assert evidence.files == 3


# --- all_exact / drift for identical members ---


def test_all_exact_true_and_drift_none_for_byte_identical_members():
    units = {
        1: _unit(1, file_path="src/a.py", body="same body", body_hash="x"),
        2: _unit(2, file_path="src/b.py", body="same body", body_hash="x"),
    }
    clusters = [_cluster([1, 2])]

    evidence = _only(build_evidence(clusters, units, {}))

    assert evidence.all_exact is True
    assert evidence.drift is None


# --- drift produced and labelled for differing members ---


def test_drift_produced_and_labelled_for_differing_members():
    body_a = "def f():\n    return 1\n"
    body_b = "def f():\n    return 2\n"
    units = {
        1: _unit(1, file_path="src/a.py", start=5, end=6, body=body_a, body_hash="x"),
        2: _unit(2, file_path="src/b.py", start=20, end=21, body=body_b, body_hash="y"),
    }
    clusters = [_cluster([1, 2])]

    evidence = _only(build_evidence(clusters, units, {}))

    assert evidence.all_exact is False
    assert evidence.drift is not None
    assert "--- src/a.py:5-6" in evidence.drift
    assert "+++ src/b.py:20-21" in evidence.drift
    assert "-    return 1" in evidence.drift
    assert "+    return 2" in evidence.drift


def test_drift_picks_the_closest_non_identical_pair():
    # unit 2 differs from unit 1 by one character; unit 3 is unrelated text.
    # The diff must be built from the closest pair (1, 2), not (1, 3).
    body_1 = "def f():\n    return 1\n"
    body_2 = "def f():\n    return 2\n"
    body_3 = "class Unrelated:\n    pass\n"
    units = {
        1: _unit(1, file_path="src/a.py", body=body_1, body_hash="x"),
        2: _unit(2, file_path="src/b.py", body=body_2, body_hash="y"),
        3: _unit(3, file_path="src/c.py", body=body_3, body_hash="z"),
    }
    clusters = [_cluster([1, 2, 3])]

    evidence = _only(build_evidence(clusters, units, {}))

    assert "src/a.py" in evidence.drift
    assert "src/b.py" in evidence.drift
    assert "src/c.py" not in evidence.drift


def test_drift_truncated_past_cap():
    lines_a = [f"line {i}\n" for i in range(80)]
    lines_b = [f"line {i} changed\n" for i in range(80)]
    body_a = "".join(lines_a)
    body_b = "".join(lines_b)
    units = {
        1: _unit(1, file_path="src/a.py", body=body_a, body_hash="x", end=80),
        2: _unit(2, file_path="src/b.py", body=body_b, body_hash="y", end=80),
    }
    clusters = [_cluster([1, 2])]

    evidence = _only(build_evidence(clusters, units, {}))

    drift_lines = evidence.drift.splitlines()
    assert len(drift_lines) <= triage._DRIFT_MAX_LINES + 1
    assert "truncated" in drift_lines[-1]


# --- same_name ---


def test_same_name_true_when_all_members_share_name():
    units = {
        1: _unit(1, file_path="src/a.py", name="verify", body_hash="x"),
        2: _unit(2, file_path="src/b.py", name="verify", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.same_name is True
    assert evidence.names == ("verify",)


def test_same_name_false_when_names_differ():
    units = {
        1: _unit(1, file_path="src/a.py", name="verifyIdClip", body_hash="x"),
        2: _unit(2, file_path="src/b.py", name="verifyClipId", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.same_name is False
    assert evidence.names == ("verifyClipId", "verifyIdClip")


# --- max_path_hops ---


def test_max_path_hops_across_directories():
    units = {
        1: _unit(1, file_path="a/b/X.java", body_hash="x"),
        2: _unit(2, file_path="c/d/Y.java", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.max_path_hops == 4


# --- adjacent_in_file ---


def test_adjacent_in_file_true_for_touching_blocks():
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=10, body_hash="x"),
        2: _unit(2, file_path="src/a.py", start=11, end=20, body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.adjacent_in_file is True


def test_adjacent_in_file_false_when_far_apart_in_same_file():
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=10, body_hash="x"),
        2: _unit(2, file_path="src/a.py", start=500, end=520, body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.adjacent_in_file is False


# --- verdict ---


def test_verdict_likely_artifact_when_adjacent_in_file():
    units = {
        1: _unit(
            1, file_path="src/a.py", start=1, end=50, body="a" * 50, body_hash="x"
        ),
        2: _unit(
            2, file_path="src/a.py", start=51, end=100, body="b" * 50, body_hash="y"
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.verdict == "likely-artifact"


def test_verdict_likely_artifact_when_block_too_small():
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=3, body="x", body_hash="x"),
        2: _unit(2, file_path="src/b.py", start=1, end=3, body="y", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.verdict == "likely-artifact"


def test_verdict_likely_real_with_substantial_drifted_cross_file_block():
    body_a = "\n".join(f"line {i}" for i in range(40))
    body_b = body_a + "\nextra"
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=40, body=body_a, body_hash="x"),
        2: _unit(
            2, file_path="other/b.py", start=1, end=41, body=body_b, body_hash="y"
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.verdict == "likely-real"


def test_verdict_likely_real_with_substantial_block_and_differing_names():
    body = "\n".join(f"line {i}" for i in range(40))
    units = {
        1: _unit(
            1,
            file_path="src/a.py",
            name="verifyIdClip",
            start=1,
            end=40,
            body=body,
            body_hash="x",
        ),
        2: _unit(
            2,
            file_path="other/b.py",
            name="verifyClipId",
            start=1,
            end=40,
            body=body,
            body_hash="x",
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.verdict == "likely-real"


def test_verdict_needs_judgment_by_default():
    body = "\n".join(f"line {i}" for i in range(40))
    units = {
        1: _unit(
            1,
            file_path="src/a.py",
            name="handle",
            start=1,
            end=40,
            body=body,
            body_hash="x",
        ),
        2: _unit(
            2,
            file_path="other/b.py",
            name="handle",
            start=1,
            end=40,
            body=body,
            body_hash="x",
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.verdict == "needs-judgment"


# --- ranking: drift and size disagree ---


def test_ranking_prefers_drifted_cluster_over_larger_stable_one():
    # BIG: a 60-line block, two copies, same directory, no drift, same name.
    body_big = "x" * 60
    units_big = {
        1: _unit(
            1, file_path="src/a.py", start=1, end=60, body=body_big, body_hash="x"
        ),
        2: _unit(
            2, file_path="src/b.py", start=1, end=60, body=body_big, body_hash="x"
        ),
    }
    # SMALL_DRIFT: a 20-line block, two copies, 4 directory hops apart, drifted.
    body_small_a = "\n".join(f"line {i}" for i in range(20))
    body_small_b = body_small_a + "\nextra"
    units_small = {
        3: _unit(
            3, file_path="p/q/a.py", start=1, end=20, body=body_small_a, body_hash="y"
        ),
        4: _unit(
            4, file_path="r/s/b.py", start=1, end=21, body=body_small_b, body_hash="z"
        ),
    }
    units = {**units_big, **units_small}
    clusters = [_cluster([1, 2]), _cluster([3, 4])]

    evidence = build_evidence(clusters, units, {})

    assert [e.number for e in evidence] == [2, 1]
    assert evidence[0].value > evidence[1].value
    big = next(e for e in evidence if e.number == 1)
    small_drift = next(e for e in evidence if e.number == 2)
    assert big.drift is None
    assert small_drift.drift is not None
