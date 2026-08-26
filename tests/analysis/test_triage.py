import difflib

import pytest

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
    assert evidence.drift_ratio is None


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
    assert evidence.drift_ratio is not None
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
    assert evidence.all_adjacent_in_file is True


def test_adjacent_in_file_false_when_far_apart_in_same_file():
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=10, body_hash="x"),
        2: _unit(2, file_path="src/a.py", start=500, end=520, body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.adjacent_in_file is False
    assert evidence.all_adjacent_in_file is False


def test_all_adjacent_in_file_false_when_one_pair_is_cross_file():
    # A and B sit adjacent in one file (indexer noise); C is a genuine
    # cross-file duplicate of A. A single real cross-file pair must stop
    # the whole cluster from reading as an indexer-split artifact.
    body_a = "\n".join(f"shared_line_{i}" for i in range(50))
    body_b = "\n".join(f"other_local_line_{i}" for i in range(50))
    body_c = body_a + "\n# tweak"
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=50, body=body_a, body_hash="a"),
        2: _unit(
            2, file_path="src/a.py", start=51, end=100, body=body_b, body_hash="b"
        ),
        3: _unit(
            3, file_path="src/other.py", start=1, end=50, body=body_c, body_hash="c"
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2, 3])], units, {}))

    assert evidence.adjacent_in_file is True
    assert evidence.all_adjacent_in_file is False
    assert evidence.verdict != "likely-artifact"
    assert not any("indexer split" in reason for reason in evidence.reasons)

    # No adjacency penalty applied: value matches the unpenalised formula.
    base = (
        triage._SIZE_WEIGHT * evidence.lines
        + triage._COPY_WEIGHT * (evidence.members - 1)
        + triage._DISTANCE_WEIGHT * evidence.max_path_hops
    ) * triage._drift_multiplier(evidence.drift_ratio)
    if not evidence.same_name:
        base += triage._NAME_MISMATCH_BONUS
    assert evidence.value == round(base, 2)


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
    assert evidence.all_adjacent_in_file is True
    assert evidence.verdict == "likely-artifact"

    # Every pair is adjacent in one file: the penalty still applies.
    base = (
        triage._SIZE_WEIGHT * evidence.lines
        + triage._COPY_WEIGHT * (evidence.members - 1)
        + triage._DISTANCE_WEIGHT * evidence.max_path_hops
    ) * triage._drift_multiplier(evidence.drift_ratio)
    if not evidence.same_name:
        base += triage._NAME_MISMATCH_BONUS
    assert evidence.value == round(base * triage._ADJACENCY_PENALTY, 2)


def test_verdict_likely_artifact_when_block_too_small():
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=3, body="x", body_hash="x"),
        2: _unit(2, file_path="src/b.py", start=1, end=3, body="y", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    # Trivial-block route is independent of adjacency: these members are not
    # even in the same file.
    assert evidence.all_adjacent_in_file is False
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


def test_ranking_prefers_high_similarity_small_diff_over_low_similarity_big_diff():
    # BIG: a 50-line block, two copies, same directory, but the bodies share
    # almost no text (this is a regression case: under a multiplier that
    # fires on drift *presence* alone, this cluster would outrank SMALL below).
    body_big_a = "\n".join(
        f"function_body_line_{i}_alpha_beta_gamma" for i in range(50)
    )
    body_big_b = "\n".join(
        f"totally_other_code_segment_{i}_zeta_eta" for i in range(50)
    )
    units_big = {
        1: _unit(
            1, file_path="src/a.py", start=1, end=50, body=body_big_a, body_hash="a"
        ),
        2: _unit(
            2, file_path="src/b.py", start=1, end=50, body=body_big_b, body_hash="b"
        ),
    }
    # SMALL: a 20-line block, two copies, 4 directory hops apart, near-identical
    # (one changed line) -- the launchWorker shape: small, distant, barely drifted.
    lines = [f"line_{i}_stable_content" for i in range(20)]
    lines_changed = list(lines)
    lines_changed[5] = "line_5_stable_content  # different comment"
    body_small_a = "\n".join(lines)
    body_small_b = "\n".join(lines_changed)
    units_small = {
        3: _unit(
            3, file_path="p/q/a.py", start=1, end=20, body=body_small_a, body_hash="c"
        ),
        4: _unit(
            4, file_path="r/s/b.py", start=1, end=20, body=body_small_b, body_hash="d"
        ),
    }
    units = {**units_big, **units_small}
    clusters = [_cluster([1, 2]), _cluster([3, 4])]

    evidence = build_evidence(clusters, units, {})

    assert [e.number for e in evidence] == [2, 1]
    big = next(e for e in evidence if e.number == 1)
    small = next(e for e in evidence if e.number == 2)
    assert small.value > big.value
    assert big.drift_ratio is not None
    assert big.drift_ratio < triage._DRIFT_SIMILARITY_FLOOR
    assert small.drift_ratio is not None
    assert small.drift_ratio >= triage._DRIFT_SIMILARITY_FLOOR


# --- drift below the similarity floor gets no boost ---


def test_below_drift_floor_gets_no_boost_and_withholds_likely_real():
    # Two 40-line blocks, cross-file, that would satisfy the size and
    # cross-file conditions for likely-real, but share almost no text.
    body_a = "\n".join(f"alpha_segment_{i}_unique_content" for i in range(40))
    body_b = "\n".join(f"beta_segment_{i}_different_stuff" for i in range(40))
    units = {
        1: _unit(1, file_path="src/a.py", start=1, end=40, body=body_a, body_hash="a"),
        2: _unit(
            2, file_path="other/b.py", start=1, end=40, body=body_b, body_hash="b"
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))

    assert evidence.drift is not None
    assert evidence.drift_ratio is not None
    assert evidence.drift_ratio < triage._DRIFT_SIMILARITY_FLOOR
    assert evidence.verdict == "needs-judgment"
    # No multiplier applied: value is exactly the unboosted base (size + copy + distance).
    expected_base = (
        triage._SIZE_WEIGHT * evidence.lines
        + triage._COPY_WEIGHT * (evidence.members - 1)
        + triage._DISTANCE_WEIGHT * evidence.max_path_hops
    )
    assert evidence.value == round(expected_base, 2)


# --- relational evidence ignores adjacency noise (nested closures) ---


def test_drift_and_names_ignore_a_nested_within_file_member():
    # A is a 30-line function; B is A's own nested closure, indexed a second
    # time and spanning nearly all of A's body (so its raw textual overlap
    # with A is very high, ~0.95); C is a genuine, more modest cross-file
    # duplicate of A (~0.26 similar). Under the pre-fix code, which searched
    # every pair for the single closest one, (A, B) would win on raw ratio
    # even though B is A's own inner closure, not an independent copy -- the
    # diff would compare A against itself and "names" would include B's
    # anonymous name, exactly the launchWorker/analysis.ts bug this pins.
    words = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "eta",
        "theta",
        "iota",
        "kappa",
        "lambda",
        "mu",
        "nu",
        "xi",
        "omicron",
        "pi",
        "rho",
        "sigma",
        "tau",
        "upsilon",
        "phi",
        "chi",
        "psi",
        "omega",
        "north",
        "south",
        "east",
        "west",
        "up",
        "down",
    ]
    lines_a = [
        f"const {words[i]}_{i} = compute({words[(i + 1) % 30]}, {i})" for i in range(30)
    ]
    body_a = "\n".join(lines_a)
    body_b = "\n".join(lines_a[3:30])  # A's own nested closure, minus a wrapper
    lines_c = list(lines_a)
    for i in range(0, 30, 3):
        lines_c[i] = (
            f"const {words[i]}_{i} = computeVariant({words[(i + 2) % 30]}, {i}, extra)"
        )
    body_c = "\n".join(lines_c)

    units = {
        1: _unit(
            1,
            file_path="src/worker.ts",
            name="worker",
            start=1,
            end=30,
            body=body_a,
            body_hash="a",
        ),
        2: _unit(
            2,
            file_path="src/worker.ts",
            name="<unknown>",
            start=4,
            end=30,
            body=body_b,
            body_hash="b",
        ),
        3: _unit(
            3,
            file_path="other/worker.ts",
            name="worker",
            start=1,
            end=30,
            body=body_c,
            body_hash="c",
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2, 3])], units, {}))

    assert evidence.nested_members == 1
    assert evidence.all_adjacent_in_file is False

    # The diff must come from the cross-file pair (unit 1, unit 3), not from
    # unit 1 against its own nested closure (unit 2).
    assert "src/worker.ts:1-30" in evidence.drift
    assert "other/worker.ts:1-30" in evidence.drift
    assert "src/worker.ts:4-30" not in evidence.drift

    expected_ratio = difflib.SequenceMatcher(a=body_a, b=body_c).ratio()
    assert evidence.drift_ratio == pytest.approx(expected_ratio)

    # The nested closure's name must not poison the name comparison.
    assert evidence.names == ("worker",)
    assert evidence.same_name is True


def test_all_pairs_adjacent_falls_back_to_the_full_set_for_relational_evidence():
    # Only two members, both in one file, one nested in the other: the only
    # available pair is adjacent, so evidence must still be computed from it
    # rather than coming up empty.
    body_a = "\n".join(f"line_{i}_alpha_beta" for i in range(40))
    body_b = "\n".join(f"line_{i}_alpha_beta" for i in range(5, 35))
    units = {
        1: _unit(
            1,
            file_path="src/worker.ts",
            name="worker",
            start=1,
            end=40,
            body=body_a,
            body_hash="a",
        ),
        2: _unit(
            2,
            file_path="src/worker.ts",
            name="<unknown>",
            start=6,
            end=35,
            body=body_b,
            body_hash="b",
        ),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))

    assert evidence.all_adjacent_in_file is True
    assert evidence.nested_members == 1
    # Falls back to the only pair there is, rather than reporting no drift.
    assert evidence.drift is not None
    assert "src/worker.ts:1-40" in evidence.drift
    assert "src/worker.ts:6-35" in evidence.drift
    # Names fall back to the full set too: the distinction stops mattering
    # once the whole cluster is already artifact-shaped.
    assert evidence.names == ("<unknown>", "worker")
    assert evidence.same_name is False


def test_nested_members_zero_when_nothing_is_adjacent():
    units = {
        1: _unit(1, file_path="src/a.py", body_hash="x"),
        2: _unit(2, file_path="src/b.py", body_hash="y"),
    }
    evidence = _only(build_evidence([_cluster([1, 2])], units, {}))
    assert evidence.nested_members == 0
