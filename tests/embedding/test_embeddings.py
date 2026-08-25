from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slopo.config import Config
from slopo.embedding.embeddings import EmbeddingError, embed_units
from slopo.embedding.models import EmbeddedUnit, UnembeddedUnit

_CONFIG = Config(
    source_dir=Path("src"),
    source_dir_exclude=[],
    db_file=Path("slopo.db"),
    report_dir=Path("slopo-report"),
    ignore_file=Path("slopo.ignore.txt"),
    embedding_model="openai/text-embedding-3-small",
    embedding_dimensions=3,
    embedding_api_key="test-key",
    embedding_params={},
    embedding_batch_size=100,
    embedding_batch_chars=10000,
    embedding_request_delay=0,
    similarity_threshold=0.9,
    rerank_threshold=0.93,
    body_node_count_threshold=10,
    representation="raw",
    embedding_input_prefix=None,
)


def _mock_response(vectors: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.data = [{"embedding": v} for v in vectors]
    return response


def test_single_unit_mapped():
    units = [UnembeddedUnit(embed_hash="h7", embed_body="def foo(): pass")]
    with patch(
        "litellm.embedding",
        return_value=_mock_response([[1.0, 2.0, 3.0]]),
    ):
        result = embed_units(units, _CONFIG)

    assert result == [EmbeddedUnit(embed_hash="h7", vector=[1.0, 2.0, 3.0])]


def test_multiple_units_preserve_order():
    units = [
        UnembeddedUnit(embed_hash="h1", embed_body="def foo(): pass"),
        UnembeddedUnit(embed_hash="h2", embed_body="def bar(): pass"),
        UnembeddedUnit(embed_hash="h3", embed_body="def baz(): pass"),
    ]
    with patch(
        "litellm.embedding",
        return_value=_mock_response(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        ),
    ):
        result = embed_units(units, _CONFIG)

    assert result == [
        EmbeddedUnit(embed_hash="h1", vector=[1.0, 0.0, 0.0]),
        EmbeddedUnit(embed_hash="h2", vector=[0.0, 1.0, 0.0]),
        EmbeddedUnit(embed_hash="h3", vector=[0.0, 0.0, 1.0]),
    ]


def test_embedding_params_forwarded_to_litellm():
    units = [UnembeddedUnit(embed_hash="h1", embed_body="def foo(): pass")]
    config = replace(
        _CONFIG,
        embedding_params={"input_type": "search_document", "truncation": False},
    )
    with patch(
        "litellm.embedding",
        return_value=_mock_response([[1.0, 2.0, 3.0]]),
    ) as mock_embedding:
        embed_units(units, config)

    kwargs = mock_embedding.call_args.kwargs
    assert kwargs["input_type"] == "search_document"
    assert kwargs["truncation"] is False


def test_input_prefix_prepended_to_every_input():
    units = [
        UnembeddedUnit(embed_hash="h1", embed_body="def foo(): pass"),
        UnembeddedUnit(embed_hash="h2", embed_body="def bar(): pass"),
    ]
    config = replace(_CONFIG, embedding_input_prefix="Find equivalent code:\n")
    with patch(
        "litellm.embedding",
        return_value=_mock_response([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]),
    ) as mock_embedding:
        result = embed_units(units, config)

    assert mock_embedding.call_args.kwargs["input"] == [
        "Find equivalent code:\ndef foo(): pass",
        "Find equivalent code:\ndef bar(): pass",
    ]
    assert [u.embed_hash for u in result] == ["h1", "h2"]


def test_no_input_prefix_leaves_inputs_unchanged():
    units = [UnembeddedUnit(embed_hash="h1", embed_body="def foo(): pass")]
    with patch(
        "litellm.embedding",
        return_value=_mock_response([[1.0, 2.0, 3.0]]),
    ) as mock_embedding:
        embed_units(units, _CONFIG)

    assert mock_embedding.call_args.kwargs["input"] == ["def foo(): pass"]


def test_vector_size_mismatch_raises():
    units = [UnembeddedUnit(embed_hash="h1", embed_body="def foo(): pass")]
    with patch(
        "litellm.embedding",
        return_value=_mock_response([[1.0, 2.0]]),
    ):
        with pytest.raises(EmbeddingError):
            embed_units(units, _CONFIG)
