"""Tests for Wave 6 Phase 3: QueryExpander with synonym and multi-query strategies."""

import pytest

# Skip if nltk not available
pytest.importorskip("nltk")

from aura_ia_mcp.services.model_gateway.query_expander import (
    QueryExpander,
    create_query_expander_from_env,
)


def test_query_expander_initialization_synonyms():
    """Test QueryExpander initializes with synonym strategy."""
    expander = QueryExpander(strategy="synonyms", max_variants=5)

    assert expander.strategy == "synonyms"
    assert expander.max_variants == 5


def test_query_expander_initialization_multi_query():
    """Test QueryExpander initializes with multi-query strategy."""
    expander = QueryExpander(strategy="multi_query", max_variants=4)

    assert expander.strategy == "multi_query"
    assert expander.max_variants == 4


def test_expand_synonyms_basic():
    """Test synonym expansion generates variants."""
    expander = QueryExpander(strategy="synonyms", max_variants=5)

    variants = expander.expand("machine learning")

    # Should return list with original query
    assert isinstance(variants, list)
    assert len(variants) >= 1
    assert "machine learning" in variants  # Original always included

    # Should generate some variants (exact count depends on WordNet)
    assert len(variants) <= 5  # Respects max_variants


def test_expand_synonyms_respects_max_variants():
    """Test synonym expansion respects max_variants limit."""
    expander = QueryExpander(strategy="synonyms", max_variants=3)

    variants = expander.expand("computer science")

    assert len(variants) <= 3


def test_expand_multi_query_basic():
    """Test multi-query expansion generates templates."""
    expander = QueryExpander(strategy="multi_query", max_variants=5)

    variants = expander.expand("neural networks")

    # Should return list of variants
    assert isinstance(variants, list)
    assert len(variants) >= 1

    # Original query should be first
    assert variants[0] == "neural networks"

    # Should contain template-based variants
    assert any("what is" in v.lower() for v in variants)


def test_expand_multi_query_templates():
    """Test multi-query generates expected template variants."""
    expander = QueryExpander(strategy="multi_query", max_variants=6)

    variants = expander.expand("python")

    # Check expected templates are present
    assert "python" in variants
    assert "what is python" in variants
    assert "information about python" in variants
    assert "python explanation" in variants


def test_expand_multi_query_respects_max_variants():
    """Test multi-query respects max_variants limit."""
    expander = QueryExpander(strategy="multi_query", max_variants=3)

    variants = expander.expand("test")

    assert len(variants) <= 3


def test_expand_unknown_strategy():
    """Test expansion with unknown strategy returns original."""
    expander = QueryExpander(strategy="unknown", max_variants=5)

    variants = expander.expand("test query")

    # Should return only original query
    assert variants == ["test query"]


def test_expand_synonyms_single_word():
    """Test synonym expansion with single word query."""
    expander = QueryExpander(strategy="synonyms", max_variants=5)

    variants = expander.expand("car")

    # Should include original
    assert "car" in variants

    # Might include synonyms like "automobile", "vehicle"
    # (Exact results depend on WordNet, so we just check structure)
    assert isinstance(variants, list)
    assert len(variants) >= 1


def test_expand_synonyms_no_synonyms_available():
    """Test synonym expansion when no synonyms exist."""
    expander = QueryExpander(strategy="synonyms", max_variants=5)

    # Use a made-up word with no synonyms
    variants = expander.expand("xyzabc123")

    # Should return only original query
    assert len(variants) == 1
    assert variants[0] == "xyzabc123"


def test_create_query_expander_from_env_disabled():
    """Test factory returns None when disabled."""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"QUERY_EXPANSION_ENABLED": "0"}, clear=False):
        expander = create_query_expander_from_env()
        assert expander is None


def test_create_query_expander_from_env_enabled():
    """Test factory creates QueryExpander when enabled."""
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {
            "QUERY_EXPANSION_ENABLED": "1",
            "EXPANSION_STRATEGY": "multi_query",
            "EXPANSION_MAX_VARIANTS": "4",
        },
        clear=False,
    ):
        expander = create_query_expander_from_env()
        assert expander is not None
        assert expander.strategy == "multi_query"
        assert expander.max_variants == 4


def test_create_query_expander_from_env_default_values():
    """Test factory uses default values when not specified."""
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {"QUERY_EXPANSION_ENABLED": "1"},
        clear=False,
    ):
        expander = create_query_expander_from_env()
        assert expander is not None
        assert expander.strategy == "synonyms"  # Default
        assert expander.max_variants == 5  # Default
