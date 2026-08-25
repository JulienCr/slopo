# Threshold calibration

`similarity_threshold` defaults to 0.92 and `rerank_threshold` to 0.94. Those values come from
upstream's benchmark, run against `jina-code-embeddings-0.5b` through the Jina API at 256
dimensions. **They do not transfer to another model.** A different model puts equivalent code at a
different place on the cosine scale, and a threshold read off one distribution means something else
on another.

Measured end to end — the real pipeline, similarity gate plus rerank plus clustering — over the 20
duplicate and 20 distinct labeled pairs in `tests/baseline/`.

## Measured

| `similarity_threshold` / `rerank_threshold` | jina-embeddings-v2-base-code | jina-code-embeddings-1.5b |
|---|---|---|
| 0.92 / 0.94 (default) | 0.25 recall, 0 FP | 0.20 recall, 0 FP |
| 0.85 / 0.87 | 0.55, 0 FP | 0.50, 0 FP |
| 0.82 / 0.84 | 0.55, 0 FP | 0.60, 0 FP |
| 0.78 / 0.80 | **0.65, 0 FP** | 0.65, 0 FP |
| 0.76 / 0.78 | 0.75, 1 FP | 0.65, 0 FP |
| 0.74 / 0.76 | 0.80, 2 FP | **0.75, 0 FP** |
| 0.72 / 0.74 | 0.85, 2 FP | 0.80, 1 FP |
| 0.70 / 0.72 | 0.85, 2 FP | 0.80, 2 FP |

At the default, both models miss three quarters of the duplicates this corpus labels. That is the
single most consequential number in this document.

## Recommended

```yaml
# jina-embeddings-v2-base-code, 768 dimensions
similarity_threshold: 0.78
rerank_threshold: 0.80
```

```yaml
# jina-code-embeddings-1.5b, 256 dimensions, with the code2code instruction prefix
similarity_threshold: 0.74
rerank_threshold: 0.76
```

The 1.5b model holds zero false positives ten points of threshold lower, which is what makes it the
better of the two: 0.75 recall against 0.65, both clean.

## Consider paying for recall with false positives

Zero false positives is the wrong target for this tool. Slopo produces **clusters to confirm**, not
verdicts — the README says so, and the intended workflow hands them to an agent that discards what
is not real duplication. A false positive costs one cluster read and one line in
`slopo.ignore.txt`. A missed duplicate costs nothing visible, which is exactly why it is worse.

On the table above, `jina-embeddings-v2-base-code` at 0.74 / 0.76 buys fifteen points of recall for
two false positives out of twenty distinct pairs. If reviewing clusters is cheap for you — and with
an agent doing the reading, it is — that trade is worth making.

## Validated on real code, and what it changes

The table above comes from 20 labeled duplicate pairs and 20 labeled distinct pairs. A real
repository holds far more pairs than that, so a false-positive rate that reads as zero over 20
comparisons is not zero over the hundreds of thousands a real codebase produces. The corpus optimum
is therefore a floor on what to expect, not a setting to adopt unexamined.

Measured on a 782-unit TypeScript and Python application, with `jina-embeddings-v2-base-code` and
`body_node_count_threshold: 25`. The last column counts clusters whose largest snippet reaches 15
lines — the ones worth acting on, as opposed to a shared two-line idiom:

| `similarity_threshold` | clusters | units flagged | clusters over 15 lines |
|---|---|---|---|
| 0.92 (default) | 14 | 2.5 % | **3** |
| 0.88 | 33 | 7.9 % | 14 |
| 0.85 | 44 | 12.5 % | **21** |
| 0.82 | 50 | 15.6 % | 26 |
| 0.78 | 62 | 22.1 % | 35 |
| 0.75 | 74 | 27.3 % | 40 |

At the default this codebase yields **three** substantial duplications. Whole shared blocks of
twenty lines and more sit at similarities between 0.80 and 0.90 and are simply invisible.

0.85 surfaces seven times as many for a list of 44 clusters, which one reviewer or one agent can
work through. Below 0.80 the yield keeps rising, but so does the reading: 0.78 adds fourteen more
substantial clusters at the price of doubling the total.

So **0.85 is the better starting point on a real repository**, and the corpus figure of 0.78 is what
to move toward once you trust the output and want the tail. Both beat the default by a wide margin,
which is the finding that matters.

## Recalibrating for another model

The corpus here is small and its pairs are ours, so the numbers above are a starting point, not a
constant of nature. To calibrate for a model or a codebase of your own:

1. Record the baseline for the model: `uv run python -m tests.baseline.record --model <key>`, after
   adding it to `MODELS` in `tests/baseline/harness.py`.
2. Read `zero_fp_threshold_floor` from the resulting snapshot. Any threshold above it produces no
   false positive on this corpus; the first duplicate similarity above it is the ceiling of the
   useful window.
3. Then sweep the real pipeline rather than trusting that figure:
   `uv run python -m tests.baseline.sweep --model <key>`, which replays the committed
   cassette and needs no model. It produced the table above. `max_recall_at_zero_fp` is
   computed on raw cosine similarity and ignores the rerank boost and the transitive clustering
   that follow it, so it does not predict what the pipeline will report. Comparing these two models
   by that metric ranks them the wrong way round: it prefers `v2-base-code` 0.75 to 0.70, while the
   pipeline prefers `jina-code-1.5b` 0.75 to 0.65. Use it to compare representations, where the
   pipeline is held constant, and not to compare models.

Keeping `rerank_threshold` two points above `similarity_threshold` preserves the defaults'
relationship. The rerank score is the similarity multiplied by a distance boost of up to 15 %, so
the second threshold mostly filters clusters whose members sit close together in the codebase.
