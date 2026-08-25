# Development

Fork-specific developer documentation. `README.md` stays close to upstream.

## Prerequisites

Install `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`uv` also provides the Python toolchain, so a system Python older than the required 3.12 is not a problem.

Install dependencies:

```bash
uv sync --all-extras --dev
```

## Running the embedding model locally with Ollama

The model used for local development is `unclemusclez/jina-embeddings-v2-base-code`:

```bash
ollama pull unclemusclez/jina-embeddings-v2-base-code
```

Its native output size is 768, which is what `embedding_dimensions` should be set to.

### Ollama on the same machine

Nothing to configure. Slopo talks to the default `http://localhost:11434`.

### Ollama on a Windows host, Slopo running in WSL

This is the setup that was actually validated.

Find the Windows host's address from WSL, the default gateway:

```bash
ip route show default | awk '{print $3}'
```

On the machine this was validated on, that address was `172.27.144.1`. It changes when WSL restarts, which is the reason the configuration approach below matters.

Verify reachability before anything else:

```bash
curl -s http://<gateway-ip>:11434/api/tags
```

This should list the pulled model. If it does not answer, Ollama on the Windows side is likely bound to localhost only; it needs `OLLAMA_HOST=0.0.0.0`.

There are two ways to point LiteLLM at this non-default host:

- `embedding_params.api_base` in the config file, the way upstream's README documents (see its "All configurable parameters" section).
- `OLLAMA_API_BASE` in a `.env` file at the repo root. Slopo calls `load_dotenv()` at startup (`src/slopo/cli.py`), so it is picked up automatically.

Prefer the `.env` variable in the WSL case: the gateway address changes across restarts, and `.env` is gitignored, so a machine-specific address never reaches a commit. Both were verified to work.

## Running Slopo on a project

A minimal config, for example `slopo.conf.yaml` at the repo root:

```yaml
source_dir: src
embedding_model: ollama/unclemusclez/jina-embeddings-v2-base-code
embedding_dimensions: 768
```

`slopo.conf.yaml`, `slopo.db`, `slopo-report/` and `.env` are all already gitignored.

```bash
uv run slopo index
uv run slopo embed
uv run slopo analyze
```

As an idea of scale, running this over Slopo's own `src/` directory finds 184 code units across 46 files, embeds 139 distinct bodies in 16 seconds, and reports 8 clusters.

`uv run slopo show-config` validates a config and prints every configurable parameter. `uv run slopo --help` lists all commands.

## The quality baseline

A change to the detection logic (parsing, similarity, reranking, clustering) needs to be judged against a number, not an impression. That is what the baseline under `tests/baseline/` is for.

### What it is

A small labeled corpus under `tests/baseline/corpus/` (10 Python files, 54 functions), with `tests/baseline/expectations.yaml` naming pairs that must land in the same cluster (exact copies, renamed variants, near-duplicates) and pairs that must not (code that is similar in shape but genuinely different).

### Why the embeddings are recorded

`tests/baseline/embeddings/<model>.json` holds vectors recorded once from the model. The baseline replays them by pre-filling the `embeddings` table, keyed by body hash, so the check is deterministic, needs no model, and runs in CI in well under a second as part of `uv run pytest`.

### The snapshot

`tests/baseline/snapshot.json` records current behavior: per labeled pair, the cosine similarity, the score after reranking, and whether the pair ended up in the same cluster, plus recall, false-positive count, and the separation margin (the lowest similarity among expected duplicates minus the highest among expected distinct pairs). The separation margin is the most useful single number when tuning: it moves even when no pair flips its verdict.

### What the first recording showed

At the default thresholds (`similarity_threshold: 0.92`, `rerank_threshold: 0.94`) this model detects
3 of the 6 labeled duplicate pairs: the two exact copies, and the near-duplicate pair scoring 0.944.
The two renamed variants (0.758 and 0.800) and one near-duplicate (0.875) fall below the 0.92 gate
that forms candidate pairs, so reranking never sees them. There are no false positives; the highest
scoring distinct pair reaches 0.787.

The separation margin is therefore negative, -0.029: the lowest similarity among expected duplicates
sits below the highest among expected distinct pairs. Cosine similarity alone does not separate the
two sets on this corpus with this model.

Read that as a property of the pair (model, thresholds), not of the corpus. The thresholds are
defaults shared by every model, while upstream's README recommends a different, code-specialised API
model for the best results; this local model's similarity scale is measurably lower. Whether to
retune is a detection-quality question, deliberately left out of this document. The reason to record
the numbers is that any later change now has something to beat.

Slopo can embed a normalized form of the code instead of its raw text, set with the
`representation` option. What each option measured against this baseline is recorded in
[representation-experiment.md](representation-experiment.md); the short version is that `raw`
remains the default.

### Re-recording

```bash
uv run python -m tests.baseline.record
```

This is the only step that needs a model. It is required whenever the text being embedded changes: a change to parsing or to how a code unit's body is built changes the body hashes, and the recorded vectors no longer match. The baseline fails loudly in that case rather than silently scoring the wrong thing.

### Accepting a change

```bash
SLOPO_BASELINE_UPDATE=1 uv run pytest tests/baseline
```

This rewrites the snapshot. The resulting `git diff` is the deliverable: it is what shows whether a change improved detection or quietly degraded it, and it should be read pair by pair, not accepted wholesale.
