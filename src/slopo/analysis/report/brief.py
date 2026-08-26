from slopo.analysis.models import Cluster, UnitRecord
from slopo.analysis.triage import ClusterEvidence

_PREAMBLE = """\
This repository was scanned for duplicated code. The scan found clusters of \
similar code units by embedding similarity; each cluster below is a candidate, \
not a verdict. Whether two similar pieces of code should be merged, left alone, \
or flagged as a real bug depends on what the code actually does, and that \
question is yours to answer, not the scanner's.

Open the real files at the given paths and read them before judging a cluster. \
Do not decide from the excerpts in this document alone: they are truncated to \
one member's body and can hide the difference that matters. A good triage of \
this report came from reading the files; a plausible-looking one came from \
trusting the excerpts.

## The pattern to watch for: copies that have already diverged

A cluster whose `drift` field is non-empty is not a stale duplicate, it is two \
pieces of logic that used to agree and no longer do. That is a live risk: a bug \
fixed in one copy and not the other, a check tightened in one place and left \
loose in its twin. Treat every drifted cluster as higher priority than an \
identical one, regardless of its rank.

The reason this needs saying explicitly: a path-traversal guard duplicated as \
`verifyIdClip` and `verifyClipId` will pass every textual search for one name \
without ever surfacing the other. Near-anagram names, identical logic, and a \
`grep` for one that never finds the other is exactly the shape of the cases \
worth the most attention. Do not rely on naming similarity to find these \
clusters; rely on the drift field.

## The three verdicts

- `likely-real`: mechanical signals point at unintentional duplication worth \
fixing (size, exact or near-exact copies, distance between files, matching \
names). Confirm by reading the files, then act or file an issue.
- `likely-artifact`: signals point at the indexer having split one logical \
unit into several records (adjacent in the same file, trivial size, etc.). \
These usually need no action, but a quick look costs little and catches the \
cases where the signal is wrong.
- `needs-judgment`: the mechanical signals do not settle it. This is the \
verdict where reading the files matters most, and where an agent earns its \
keep over a report that only counts characters.

## What to hand back

For every cluster below, produce one entry in this format:

```
### Cluster N: <one-line verdict in your own words>
Files: <path:start-end, path:start-end, ...>
Verdict: real-duplication | intentional-separation | needs-more-context
Reasoning: <what you found reading the files, in 1-3 sentences>
Recommended action: <merge / extract shared helper / leave separate / file bug / none>
```

Ruling a cluster out is as valuable as confirming one: write the entry either \
way, with your reasoning. A cluster you examined and dismissed, recorded as \
such, is what stops the next audit from re-litigating it from scratch. Silence \
on a cluster reads as "not looked at," not as "fine."

## Clusters
"""


def build_agent_brief_markdown(
    evidence: list[ClusterEvidence],
    clusters: list[Cluster],
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    parts = [_PREAMBLE]
    for e in evidence:
        parts.append(_cluster_entry(e, clusters[e.number - 1], units, duplicates))
    return "\n".join(parts) + "\n"


def _cluster_entry(
    evidence: ClusterEvidence,
    cluster: Cluster,
    units: dict[int, UnitRecord],
    duplicates: dict[int, list[UnitRecord]],
) -> str:
    locations = _locations(cluster, units, duplicates)
    lines = [
        f"### Cluster {evidence.number} ({evidence.verdict})",
        "",
        f"Names: {', '.join(evidence.names)}",
        f"{evidence.lines} lines, {evidence.members} members, "
        f"{evidence.files} files, {evidence.max_path_hops} directories apart, "
        f"{'same name' if evidence.same_name else 'different names'}, "
        f"{'exact copies' if evidence.all_exact else 'diverged copies'}.",
        f"Reasons: {'; '.join(evidence.reasons)}.",
        "",
        *(f"- `{location}`" for location in locations),
    ]
    if evidence.drift:
        lines += [
            "",
            "Diff between the two closest non-identical members:",
            "",
            f"```diff\n{evidence.drift}\n```",
        ]
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
