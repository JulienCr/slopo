from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.triage import ClusterEvidence


def split_by_verdict(
    evidence: list[ClusterEvidence],
) -> tuple[list[ClusterEvidence], list[ClusterEvidence]]:
    attention = [e for e in evidence if e.verdict != "likely-artifact"]
    artifacts = [e for e in evidence if e.verdict == "likely-artifact"]
    return attention, artifacts


def build_recommendations_markdown(
    evidence: list[ClusterEvidence],
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    attention, artifacts = split_by_verdict(evidence)

    parts = [_intro(len(evidence), len(attention), len(artifacts))]
    for e in attention:
        parts.append(_section(e, clusters[e.number - 1], units, duplicates))
    if artifacts:
        parts.append(_artifact_summary(artifacts, clusters, units, duplicates))
    return "\n\n".join(parts) + "\n"


def _intro(total: int, attention: int, artifacts: int) -> str:
    return (
        f"{total} clusters, {attention} worth a look, {artifacts} folded into "
        "the indexing-artifact list at the end.\n\n"
        "These are candidates, ranked by a mechanical score built from size, copy "
        "count, distance between files, and whether the code has already drifted. "
        "Whether two similar pieces of code should actually be merged is a "
        "judgment this document does not make."
    )


def _section(
    evidence: ClusterEvidence,
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    locations = _locations(cluster, units, duplicates)
    heading = f"## Cluster {evidence.number} ({evidence.verdict})\n"
    body: list[str] = [heading]
    if evidence.drift:
        body.append(
            f"These copies have already diverged:\n\n```diff\n{evidence.drift}\n```\n"
        )
    body.append(_evidence_line(evidence, locations))
    body.append(f"Reasons: {'; '.join(evidence.reasons)}.\n")
    title, issue_body = _draft_issue(evidence, locations)
    body.append(f"**Draft issue: {title}**\n\n{issue_body}")
    return "\n".join(body)


def _evidence_line(evidence: ClusterEvidence, locations: list[str]) -> str:
    names = " / ".join(evidence.names)
    same = "same name" if evidence.same_name else "different names"
    copies = "exact copies" if evidence.all_exact else "diverged copies"
    return (
        f"{evidence.lines} lines, {evidence.members} members, "
        f"{evidence.files} files, {evidence.max_path_hops} directories apart, "
        f"{same} ({names}), {copies}.\n\n"
        + "\n".join(f"- `{location}`" for location in locations)
        + "\n"
    )


def _draft_issue(evidence: ClusterEvidence, locations: list[str]) -> tuple[str, str]:
    name = evidence.names[0] if len(evidence.names) == 1 else "/".join(evidence.names)
    if evidence.drift:
        title = f"Reconcile drifted duplicate: {name}"
    else:
        title = f"Deduplicate {name} ({evidence.files} files)"
    lines = [
        f"`{name}` appears in {evidence.members} places across {evidence.files} files:",
        "",
        *(f"- `{location}`" for location in locations),
        "",
    ]
    if evidence.drift:
        lines += [
            "The copies have already diverged. Diff between the two closest "
            "non-identical members:",
            "",
            f"```diff\n{evidence.drift}\n```",
            "",
        ]
    lines.append(f"Verdict: {evidence.verdict} ({'; '.join(evidence.reasons)}).")
    return title, "\n".join(lines)


def _artifact_summary(
    artifacts: list[ClusterEvidence],
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    lines = [
        "## Likely indexing artifacts",
        "",
        "Marked likely-artifact and not detailed above: probably the indexer "
        "splitting one unit into several rather than real duplication.",
        "",
    ]
    for e in artifacts:
        cluster = clusters[e.number - 1]
        locations = _locations(cluster, units, duplicates)
        lines.append(
            f"- Cluster {e.number}: {', '.join(locations)} ({'; '.join(e.reasons)})"
        )
    return "\n".join(lines)


def _locations(
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> list[str]:
    records = [units[uid] for uid in cluster.unit_ids]
    for uid in cluster.unit_ids:
        records.extend(duplicates.get(uid, []))
    records.sort(key=lambda record: record.file_path)
    return [
        f"{record.file_path}:{record.start_line}-{record.end_line}"
        for record in records
    ]
