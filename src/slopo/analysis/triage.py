import difflib
import itertools
from dataclasses import dataclass

from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.rerank import path_hops

# Base value: a tenth of a point per duplicated line, so a 100-line theft
# is worth 10 points before any modifier below is applied.
_SIZE_WEIGHT = 0.1
# Each copy beyond the first adds its own upkeep cost, independent of size.
_COPY_WEIGHT = 1.5
# Each directory hop between the farthest pair raises drift risk on its own.
_DISTANCE_WEIGHT = 0.3
# Ceiling multiplier for a drifted pair at (near) full textual similarity;
# scaled down toward 1.0 as the pair's ratio nears the floor below.
_DRIFT_MULTIPLIER = 2.0
# Textual similarity of the closest drifted pair, distinct from the cosine
# similarity that formed the cluster (two scripts can sit at 0.85 in
# embedding space while barely half the same text); below it, no boost.
_DRIFT_SIMILARITY_FLOOR = 0.80
# Differing names defeat grep entirely; a flat bonus reflects a distinct risk.
_NAME_MISMATCH_BONUS = 4.0
# A pair adjacent or nested in one file usually reflects an indexer split.
_ADJACENCY_PENALTY = 0.25
# Blocks this short (getters, short guards) recur by coincidence, no signal.
_TRIVIAL_BLOCK_LINES = 8
# Scale further down when the duplicated block is trivially small.
_TRIVIAL_BLOCK_PENALTY = 0.25
# Above this size a duplicate is too large to be coincidental (likely-real).
_SUBSTANTIAL_BLOCK_LINES = 30
# A one-line gap still reads as one logical block split by the indexer.
_ADJACENT_MAX_GAP_LINES = 1
# A diff this long stops helping a reader who won't finish reading it.
_DRIFT_MAX_LINES = 40


@dataclass(frozen=True)
class ClusterEvidence:
    number: int
    lines: int
    members: int
    files: int
    all_exact: bool
    names: tuple[str, ...]
    same_name: bool
    max_path_hops: int
    adjacent_in_file: bool
    drift: str | None
    score_min: float
    score_max: float
    value: float
    verdict: str
    reasons: tuple[str, ...]
    # Defaulted and last: added after report/** fixtures were already written
    # with keyword construction, so this keeps them constructible unchanged.
    drift_ratio: float | None = None
    all_adjacent_in_file: bool = False


def build_evidence(
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> list[ClusterEvidence]:
    """Ranked by value, highest first."""
    evidence = [
        _evaluate(number, cluster, units, duplicates)
        for number, cluster in enumerate(clusters, 1)
    ]
    return sorted(evidence, key=lambda e: e.value, reverse=True)


def _members(
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> list[UnitRecord]:
    members: list[UnitRecord] = []
    for unit_id in cluster.unit_ids:
        members.append(units[unit_id])
        members.extend(duplicates.get(unit_id, []))
    return members


def _same_file_gap(a: UnitRecord, b: UnitRecord) -> int:
    if a.end_line < b.start_line:
        return b.start_line - a.end_line - 1
    if b.end_line < a.start_line:
        return a.start_line - b.end_line - 1
    return 0  # overlapping or nested


def _adjacent_in_file(members: list[UnitRecord]) -> bool:
    return any(
        a.file_path == b.file_path and _same_file_gap(a, b) <= _ADJACENT_MAX_GAP_LINES
        for a, b in itertools.combinations(members, 2)
    )


def _all_adjacent_in_file(members: list[UnitRecord]) -> bool:
    # A nested function is indexed both on its own and inside its parent, so
    # one logical block can enter a cluster as several adjacent members; that
    # is noise about those members, not evidence the whole cluster is noise.
    return all(
        a.file_path == b.file_path and _same_file_gap(a, b) <= _ADJACENT_MAX_GAP_LINES
        for a, b in itertools.combinations(members, 2)
    )


def _max_path_hops(members: list[UnitRecord]) -> int:
    if len(members) < 2:
        return 0
    return max(
        path_hops(a.file_path, b.file_path)
        for a, b in itertools.combinations(members, 2)
    )


def _closest_drifted_pair(
    members: list[UnitRecord],
) -> tuple[UnitRecord, UnitRecord, float] | None:
    best: tuple[UnitRecord, UnitRecord, float] | None = None
    best_ratio = -1.0
    for a, b in itertools.combinations(members, 2):
        if a.body_hash == b.body_hash:
            continue
        ratio = difflib.SequenceMatcher(a=a.body, b=b.body).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = (a, b, ratio)
    return best


def _drift_multiplier(ratio: float | None) -> float:
    if ratio is None or ratio < _DRIFT_SIMILARITY_FLOOR:
        return 1.0
    span = 1.0 - _DRIFT_SIMILARITY_FLOOR
    fraction = (ratio - _DRIFT_SIMILARITY_FLOOR) / span
    return 1.0 + fraction * (_DRIFT_MULTIPLIER - 1.0)


def _build_drift(a: UnitRecord, b: UnitRecord) -> str:
    diff = list(
        difflib.unified_diff(
            a.body.splitlines(keepends=True),
            b.body.splitlines(keepends=True),
            fromfile=f"{a.file_path}:{a.start_line}-{a.end_line}",
            tofile=f"{b.file_path}:{b.start_line}-{b.end_line}",
        )
    )
    if len(diff) > _DRIFT_MAX_LINES:
        cut = len(diff) - _DRIFT_MAX_LINES
        diff = diff[:_DRIFT_MAX_LINES]
        diff.append(f"... {cut} more lines truncated\n")
    return "".join(diff)


def _score(
    lines: int,
    member_count: int,
    max_hops: int,
    drift_ratio: float | None,
    same_name: bool,
    all_adjacent_in_file: bool,
) -> tuple[float, tuple[str, ...]]:
    reasons: list[str] = [
        f"{lines}-line block duplicated across {member_count} copies",
    ]
    value = (
        _SIZE_WEIGHT * lines
        + _COPY_WEIGHT * (member_count - 1)
        + _DISTANCE_WEIGHT * max_hops
    )
    if max_hops > 0:
        reasons.append(f"copies span {max_hops} directory hop(s)")
    if drift_ratio is not None:
        multiplier = _drift_multiplier(drift_ratio)
        if multiplier > 1.0:
            value *= multiplier
            reasons.append(
                f"drift: {drift_ratio:.0%} textually identical, still reads as the same code"
            )
        else:
            reasons.append(
                f"diverged pair only {drift_ratio:.0%} alike: related, not duplicated, no drift boost"
            )
    if not same_name:
        value += _NAME_MISMATCH_BONUS
        reasons.append("names differ across copies, invisible to grep")
    if all_adjacent_in_file:
        value *= _ADJACENCY_PENALTY
        reasons.append(
            "every member sits adjacent/nested in one file: likely indexer split"
        )
    if lines <= _TRIVIAL_BLOCK_LINES:
        value *= _TRIVIAL_BLOCK_PENALTY
        reasons.append(
            f"block is at or below the {_TRIVIAL_BLOCK_LINES}-line trivial threshold"
        )
    return round(value, 2), tuple(reasons)


def _verdict(
    lines: int,
    files: int,
    same_name: bool,
    drift_ratio: float | None,
    all_adjacent_in_file: bool,
) -> str:
    if all_adjacent_in_file or lines <= _TRIVIAL_BLOCK_LINES:
        return "likely-artifact"
    drifted_enough = drift_ratio is not None and drift_ratio >= _DRIFT_SIMILARITY_FLOOR
    if (
        files >= 2
        and lines >= _SUBSTANTIAL_BLOCK_LINES
        and (drifted_enough or not same_name)
    ):
        return "likely-real"
    return "needs-judgment"


def _evaluate(
    number: int,
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> ClusterEvidence:
    members = _members(cluster, units, duplicates)
    lines = max(m.end_line - m.start_line + 1 for m in members)
    files = len({m.file_path for m in members})
    names = tuple(sorted({m.name for m in members}))
    same_name = len(names) <= 1
    all_exact = len({m.body_hash for m in members}) <= 1
    adjacent = _adjacent_in_file(members)
    all_adjacent = _all_adjacent_in_file(members)
    max_hops = _max_path_hops(members)

    drift = None
    drift_ratio = None
    if not all_exact:
        pair = _closest_drifted_pair(members)
        if pair is not None:
            a, b, drift_ratio = pair
            drift = _build_drift(a, b)

    value, reasons = _score(
        lines, len(members), max_hops, drift_ratio, same_name, all_adjacent
    )
    verdict = _verdict(lines, files, same_name, drift_ratio, all_adjacent)

    return ClusterEvidence(
        number=number,
        lines=lines,
        members=len(members),
        files=files,
        all_exact=all_exact,
        names=names,
        same_name=same_name,
        max_path_hops=max_hops,
        adjacent_in_file=adjacent,
        all_adjacent_in_file=all_adjacent,
        drift=drift,
        drift_ratio=drift_ratio,
        score_min=cluster.min_similarity,
        score_max=cluster.max_similarity,
        value=value,
        verdict=verdict,
        reasons=reasons,
    )
