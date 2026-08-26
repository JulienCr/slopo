# slopo developer Makefile.
#
# `make` alone prints `help`. `make audit PROJECT=/path/to/project` runs a
# full index/embed/analyze pass against another project without touching it.

SHELL := /bin/bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# uv installs to ~/.local/bin, which a non-interactive shell may not have on PATH.
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: help sync test lint typecheck check record sweep audit

# --- audit defaults -------------------------------------------------------
# Calibrated by measurement against a real 782-unit repository, not guessed.
# See doc/threshold-calibration.md for the numbers behind SIMILARITY, RERANK
# and MIN_NODES, and doc/development.md for the Ollama-on-Windows-host setup.
MODEL ?= ollama/unclemusclez/jina-embeddings-v2-base-code
DIMENSIONS ?= 768
SIMILARITY ?= 0.85
RERANK ?= 0.87
MIN_NODES ?= 25
EMBED_ATTEMPTS ?= 6

# gitignore-style patterns, matched at any depth since none is slash-anchored.
EXCLUDE ?= node_modules .next dist build out coverage .venv venv __pycache__ target vendor .claude *.min.js *.d.ts

# The exclusion a user is most likely to disagree with: override to `EXCLUDE_TESTS=` to keep tests in.
EXCLUDE_TESTS ?= tests/** **/*.test.* **/*.spec.*

# Accept the project path positionally too: `make audit /path/to/project`.
# Guarded so this only fires for the `audit` goal - otherwise a typo like
# `make tets` would silently succeed instead of failing on "no rule".
ifneq (,$(filter audit,$(MAKECMDGOALS)))
  PROJECT ?= $(firstword $(filter-out audit,$(MAKECMDGOALS)))
  $(eval $(filter-out audit,$(MAKECMDGOALS)):;@:)
endif

help:
	@echo "Targets:"
	echo "  audit PROJECT=<path>  Index, embed and analyze another project (also: make audit <path>)"
	echo "  sync                  uv sync --all-extras --dev"
	echo "  test                  uv run pytest"
	echo "  lint                  uv run ruff check . && uv run ruff format --check ."
	echo "  typecheck             uv run mypy src tests"
	echo "  check                 test + lint + typecheck"
	echo "  record                uv run python -m tests.baseline.record (forwards MODEL_KEY, REPRESENTATION)"
	echo "  sweep                 uv run python -m tests.baseline.sweep (forwards MODEL_KEY, REPRESENTATION)"
	echo
	echo "audit variables (default):"
	echo "  MODEL           $(MODEL)"
	echo "  DIMENSIONS      $(DIMENSIONS)"
	echo "  SIMILARITY      $(SIMILARITY)"
	echo "  RERANK          $(RERANK)"
	echo "  MIN_NODES       $(MIN_NODES)"
	echo "  EMBED_ATTEMPTS  $(EMBED_ATTEMPTS)"
	echo "  EXCLUDE         $(EXCLUDE)"
	echo "  EXCLUDE_TESTS   $(EXCLUDE_TESTS)"
	echo
	echo "See doc/threshold-calibration.md for where SIMILARITY/RERANK/MIN_NODES come from."
	echo "record/sweep take a baseline MODEL_KEY (e.g. jina-v2-base-code); that is not audit's MODEL."

sync:
	@uv sync --all-extras --dev

test:
	@uv run pytest

lint:
	@uv run ruff check . && uv run ruff format --check .

typecheck:
	@uv run mypy src tests

check: test lint typecheck

record:
	@uv run python -m tests.baseline.record $(if $(MODEL_KEY),--model $(MODEL_KEY)) $(if $(REPRESENTATION),--representation $(REPRESENTATION))

sweep:
	@uv run python -m tests.baseline.sweep $(if $(MODEL_KEY),--model $(MODEL_KEY)) $(if $(REPRESENTATION),--representation $(REPRESENTATION))

# --- audit ------------------------------------------------------------
# Works in .audit/<basename of PROJECT>/ inside this repo, never inside
# PROJECT itself - PROJECT may not be the user's to write to. slopo.db there
# persists between runs on purpose: re-indexing is incremental.
audit:
	@set -f
	if [ -z "$(PROJECT)" ]; then
	  echo "Usage: make audit PROJECT=/path/to/project   (or: make audit /path/to/project)" >&2
	  exit 1
	fi
	if [ ! -d "$(PROJECT)" ]; then
	  echo "Error: $(PROJECT) is not a directory" >&2
	  exit 1
	fi
	project="$$(cd "$(PROJECT)" && pwd)"
	name="$$(basename "$$project")"
	workspace="$(CURDIR)/.audit/$$name"
	mkdir -p "$$workspace/report"
	config="$$workspace/slopo.conf.yaml"
	if [ -f "$$config" ]; then
	  echo "Reusing existing config at $$config (it may have hand-tuned excludes - not regenerating)."
	else
	  {
	    echo "source_dir: $$project"
	    echo "source_dir_exclude:"
	    for p in $(EXCLUDE) $(EXCLUDE_TESTS); do printf '  - "%s"\n' "$$p"; done
	    echo "db_file: $$workspace/slopo.db"
	    echo "report_dir: $$workspace/report"
	    echo "ignore_file: $$workspace/slopo.ignore.txt"
	    echo "embedding_model: $(MODEL)"
	    echo "embedding_dimensions: $(DIMENSIONS)"
	    echo "similarity_threshold: $(SIMILARITY)"
	    echo "rerank_threshold: $(RERANK)"
	    echo "body_node_count_threshold: $(MIN_NODES)"
	  } > "$$config"
	  echo "Generated config at $$config"
	fi
	uv run slopo --config "$$config" index
	attempt=1
	while true; do
	  if uv run slopo --config "$$config" embed; then
	    break
	  fi
	  if [ "$$attempt" -ge $(EMBED_ATTEMPTS) ]; then
	    echo "embed failed after $$attempt/$(EMBED_ATTEMPTS) attempts; giving up on the last error above. Re-run 'make audit PROJECT=$$project' to resume - indexing already succeeded, and embed is incremental." >&2
	    exit 1
	  fi
	  attempt=$$((attempt + 1))
	  echo "embed attempt failed; retrying ($$attempt/$(EMBED_ATTEMPTS))..." >&2
	done
	uv run slopo --config "$$config" analyze
