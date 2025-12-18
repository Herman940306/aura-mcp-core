"""Query expansion service for improved retrieval coverage.

Wave 6 Phase 3: Expand queries with synonyms or generate multiple query variants.
"""

import logging
import os

try:
    import nltk
    from nltk.corpus import wordnet
except ImportError:
    nltk = None  # type: ignore
    wordnet = None  # type: ignore

logger = logging.getLogger(__name__)


class QueryExpander:
    """Expand queries to improve retrieval coverage.

    Supports two strategies:
    1. Synonym expansion: Replace words with synonyms from WordNet
    2. Multi-query: Generate multiple query variants using templates

    Usage:
        expander = QueryExpander(strategy="synonyms")
        variants = expander.expand("machine learning")
        # Returns: ["machine learning", "machine acquisition", "auto learning", ...]
    """

    def __init__(
        self,
        strategy: str = "synonyms",
        max_variants: int = 5,
    ):
        """Initialize query expander.

        Args:
            strategy: Expansion strategy ('synonyms' or 'multi_query')
            max_variants: Maximum number of query variants to generate
        """
        self.strategy = strategy
        self.max_variants = max_variants

        # Initialize WordNet if using synonyms
        if strategy == "synonyms":
            if nltk is None:
                raise RuntimeError(
                    "NLTK not installed. Install with: pip install nltk"
                )
            try:
                wordnet.synsets("test")  # Check if data is available
            except LookupError:
                logger.info("Downloading NLTK WordNet data...")
                nltk.download("wordnet", quiet=True)
                nltk.download("omw-1.4", quiet=True)  # Multi-lingual WordNet

        logger.info(
            f"QueryExpander initialized: strategy={strategy}, "
            f"max_variants={max_variants}"
        )

    def expand(self, query: str) -> list[str]:
        """Expand query into multiple variants.

        Args:
            query: Original query string

        Returns:
            List of query variants (original query always included first)
        """
        if self.strategy == "synonyms":
            return self.expand_synonyms(query)
        elif self.strategy == "multi_query":
            return self.expand_multi_query(query)
        else:
            logger.warning(
                f"Unknown strategy: {self.strategy}, returning original"
            )
            return [query]

    def expand_synonyms(self, query: str) -> list[str]:
        """Expand query by replacing words with synonyms.

        Args:
            query: Original query string

        Returns:
            List of query variants with synonym replacements
        """
        variants: set[str] = {query}  # Always include original
        words = query.lower().split()

        # For each word, find synonyms and create variants
        for i, word in enumerate(words):
            synsets = wordnet.synsets(word)
            if not synsets:
                continue

            # Get top synonyms (limit to 2 per word)
            for synset in synsets[:2]:
                for lemma in synset.lemmas()[
                    :1
                ]:  # Top synonym from each synset
                    synonym = lemma.name().replace("_", " ")
                    if synonym.lower() != word:
                        # Create variant by replacing word with synonym
                        variant_words = words.copy()
                        variant_words[i] = synonym
                        variant = " ".join(variant_words)
                        variants.add(variant)

                        if len(variants) >= self.max_variants:
                            break
                if len(variants) >= self.max_variants:
                    break
            if len(variants) >= self.max_variants:
                break

        return list(variants)[: self.max_variants]

    def expand_multi_query(self, query: str) -> list[str]:
        """Generate multiple query variants using templates.

        Args:
            query: Original query string

        Returns:
            List of query variants based on templates
        """
        templates = [
            "{query}",  # Original
            "what is {query}",
            "information about {query}",
            "{query} explanation",
            "how does {query} work",
            "define {query}",
        ]

        variants = []
        for template in templates[: self.max_variants]:
            variant = template.format(query=query)
            variants.append(variant)

        return variants


def create_query_expander_from_env() -> QueryExpander | None:
    """Factory function to create QueryExpander from environment variables.

    Environment variables:
        QUERY_EXPANSION_ENABLED: Enable expansion (0|1, default: 0)
        EXPANSION_STRATEGY: Strategy to use (synonyms|multi_query, default: synonyms)
        EXPANSION_MAX_VARIANTS: Max variants to generate (default: 5)

    Returns:
        QueryExpander instance if enabled, None otherwise
    """
    enabled = os.getenv("QUERY_EXPANSION_ENABLED", "0") in (
        "1",
        "true",
        "True",
    )
    if not enabled:
        return None

    strategy = os.getenv("EXPANSION_STRATEGY", "synonyms")
    max_variants = int(os.getenv("EXPANSION_MAX_VARIANTS", "5"))

    logger.info(
        f"Creating QueryExpander: strategy={strategy}, max_variants={max_variants}"
    )

    return QueryExpander(strategy=strategy, max_variants=max_variants)
