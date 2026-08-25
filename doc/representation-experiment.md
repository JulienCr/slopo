# Representation experiment

Slopo embeds a code unit's text and compares vectors. What text gets embedded is the
`representation` setting. This records what each option measured against the labeled baseline in
`tests/baseline/`, so a later change has numbers to beat rather than an impression to argue with.

Measured on 20 duplicate and 20 distinct labeled pairs across Python and TypeScript, with
`jina-embeddings-v2-base-code`. Every recording is committed under `tests/baseline/embeddings/`
and its result under `tests/baseline/snapshot*.json`, so the comparison can be reproduced offline.

## Why this was tried

The raw representation is essentially lexical. Two functions computing the same Euclidean norm,
isomorphic token for token but using different variable names, score **0.4814** — lower than
several pairs the corpus labels as genuinely different. Renamed duplicates are the case the tool
claims to find, and it does not find them.

## What was measured

`recall` and `false_positives` are taken at the pinned 0.92 threshold, and **are not comparable
across representations**: normalizing shifts the whole similarity distribution upward, so a fixed
threshold means something different in each column. They are recorded for context only.

The two figures that carry the comparison are threshold-independent. `zero_fp_floor` is the
highest similarity among distinct pairs; any threshold above it yields no false positive.
`max_recall_at_zero_fp` is the share of duplicate pairs scoring above that floor — the best recall
the representation can reach without a single false positive, whichever threshold is chosen.

| | raw | rename_locals | rename_all | rename_all_literals |
|---|---|---|---|---|
| **max_recall_at_zero_fp** | 0.75 | 0.75 | 0.40 | **0.85** |
| separation_margin | -0.3055 | -0.2706 | -0.1057 | **-0.0921** |
| zero_fp_floor | 0.7869 | 0.8382 | 0.9959 | 0.9904 |
| recall at 0.92 | 0.25 | 0.35 | 0.80 | 0.95 |
| false positives at 0.92 | 0 | 0 | 2 | 5 |
| clusters | 5 | 7 | 16 | 14 |

By language, as `max_recall_at_zero_fp`:

| | raw | rename_locals | rename_all | rename_all_literals |
|---|---|---|---|---|
| python | 0.70 | 0.80 | 0.40 | 0.80 |
| typescript | 1.00 | 0.90 | 1.00 | 0.90 |

## Reading it

**Renaming locals while keeping the function name is not enough.** `rename_locals` leaves the
aggregate unchanged at 0.75. The function's own name carries enough of the lexical signal that
canonicalising the body around it barely moves the ranking.

**Deleting the function name is what unlocks the gain, and what causes the damage.** The floor
jumps from 0.8382 to 0.9959 the moment the name goes. One pair does that on its own:

```python
def compute_circle_area(radius):            def compute_circle_circumference(radius):
    ...                                         ...
    area = pi * radius * radius                 circumference = 2 * pi * radius
    return round(area, 4)                       return round(circumference, 4)
```

These compute different quantities, and the corpus labels them distinct. Their *code* differs by
one arithmetic term; the thing that tells a reader they are not the same is the name. Normalizing
the name away deletes exactly that signal, and the two become 0.9959 similar. This is not a flaw
in the test case. It is the honest limit of name-blind normalization.

**Literal normalization pays for the name.** `rename_all_literals` reaches 0.85, the only variant
that beats raw. Zeroing literals lifts the duplicate pairs more than it lifts the floor.

## What this does not establish

`max_recall_at_zero_fp` is a max-order statistic: a single pathological distinct pair caps it,
and here one pair does so in all three normalized variants. On 20 pairs per side that makes the
headline number fragile — the direction is more trustworthy than the value.

TypeScript also regresses under every normalized variant, 1.00 to 0.90. The TypeScript and Python
slices are not of equal difficulty (the Python distinct pairs were written to be more tempting),
so the per-language split should not yet be read as a statement about the languages.

A 0.10 gain on this corpus, bought with a regression on one language and resting on one binding
outlier, does not justify changing the default. `raw` stays the default.

## What to try next

**A rank-based metric.** Average precision over the labeled pairs uses the whole ranking instead
of the single worst distinct pair, and would not swing on one case.

**`rename_locals` plus literal normalization**, which the current cumulative levels cannot
express. Keeping the function name held the circle pair down to 0.8382, and zeroing literals is
what produced most of the gain — the combination is the obvious candidate and is not yet measured.

**More labeled pairs**, and a TypeScript slice written to the same difficulty as the Python one.
