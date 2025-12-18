"""
Aura IA Debate Topics

Pool of debate topics organized by category.
Topics are selected randomly or based on recent chat context.
"""

import random
from enum import Enum
from typing import Optional


class TopicCategory(str, Enum):
    """Categories of debate topics."""
    REASONING = "reasoning"
    CODING = "coding"
    PHILOSOPHY = "philosophy"
    STRATEGY = "strategy"
    PREDICTION = "prediction"
    ANALYSIS = "analysis"


# Topic pool organized by category
DEBATE_TOPICS: dict[TopicCategory, list[str]] = {
    TopicCategory.REASONING: [
        "Is it better to make quick decisions with limited information or wait for more data?",
        "Should AI systems prioritize accuracy over speed in real-time applications?",
        "Is specialization or generalization more valuable for AI models?",
        "Should AI explain its reasoning even when the explanation adds latency?",
        "Is emergent behavior in AI a feature or a bug?",
        "Should AI systems have persistent memory across sessions?",
        "Is uncertainty quantification worth the computational cost?",
        "Should AI models be optimized for average case or worst case performance?",
        "Is transfer learning fundamentally better than task-specific training?",
        "Should AI prioritize consistency or creativity in responses?",
    ],
    
    TopicCategory.CODING: [
        "Is static typing worth the extra development overhead?",
        "Should code prioritize readability over performance?",
        "Are microservices better than monoliths for most applications?",
        "Is test-driven development practical for AI-assisted coding?",
        "Should developers use ORMs or write raw SQL?",
        "Is functional programming superior to object-oriented for data processing?",
        "Should API design prioritize REST or GraphQL?",
        "Is infrastructure-as-code worth the learning curve?",
        "Should code comments explain 'what' or 'why'?",
        "Is pair programming more productive than solo development?",
    ],
    
    TopicCategory.PHILOSOPHY: [
        "Can AI truly understand language or is it sophisticated pattern matching?",
        "Should AI systems have the ability to refuse requests?",
        "Is consciousness required for intelligence?",
        "Should AI development prioritize safety or capability?",
        "Can AI creativity be considered genuine creativity?",
        "Should AI have rights if it demonstrates self-awareness?",
        "Is human oversight of AI fundamentally limiting?",
        "Should AI be transparent about being AI?",
        "Is artificial general intelligence achievable?",
        "Should AI optimize for individual users or society?",
    ],
    
    TopicCategory.STRATEGY: [
        "Should companies build or buy AI capabilities?",
        "Is open-source AI better for innovation than proprietary models?",
        "Should AI development be globally coordinated?",
        "Is edge AI or cloud AI better for enterprise?",
        "Should AI assistants be proactive or reactive?",
        "Is multi-agent collaboration better than single powerful agents?",
        "Should AI models be updated continuously or in discrete versions?",
        "Is fine-tuning or prompting better for customization?",
        "Should AI pricing be based on usage or subscription?",
        "Is vertical AI or horizontal AI more valuable?",
    ],
    
    TopicCategory.PREDICTION: [
        "Will transformers remain dominant for the next 5 years?",
        "Will AI replace most knowledge workers within a decade?",
        "Will quantum computing significantly impact AI?",
        "Will AI-generated content become indistinguishable from human content?",
        "Will AI regulation help or hinder innovation?",
        "Will AI assistants replace search engines?",
        "Will multimodal AI become the default?",
        "Will AI development costs continue to decrease?",
        "Will AI personalization become privacy-preserving?",
        "Will AI agents handle most routine tasks within 5 years?",
    ],
    
    TopicCategory.ANALYSIS: [
        "Analyze the trade-offs between model size and inference speed.",
        "Analyze the impact of context window size on model capability.",
        "Analyze the benefits and risks of AI tool-calling capabilities.",
        "Analyze the effectiveness of RLHF vs constitutional AI.",
        "Analyze the role of synthetic data in AI training.",
        "Analyze the balance between AI safety and AI capability.",
        "Analyze the impact of quantization on model quality.",
        "Analyze the future of human-AI collaboration in software development.",
        "Analyze the effectiveness of retrieval-augmented generation.",
        "Analyze the role of small models in AI deployment.",
    ],
}


def get_random_topic(
    category: Optional[TopicCategory] = None,
    exclude_topics: Optional[list[str]] = None,
) -> tuple[str, TopicCategory]:
    """
    Get a random debate topic.
    
    Args:
        category: Optional category to select from (random if None)
        exclude_topics: Topics to exclude from selection
    
    Returns:
        Tuple of (topic, category)
    """
    exclude_topics = exclude_topics or []
    
    # Select category
    if category is None:
        category = random.choice(list(TopicCategory))
    
    # Get available topics
    available = [
        t for t in DEBATE_TOPICS[category]
        if t not in exclude_topics
    ]
    
    # Fall back to any category if current is exhausted
    if not available:
        for cat in TopicCategory:
            available = [
                t for t in DEBATE_TOPICS[cat]
                if t not in exclude_topics
            ]
            if available:
                category = cat
                break
    
    if not available:
        # Ultimate fallback
        return "Which approach leads to better outcomes?", TopicCategory.REASONING
    
    topic = random.choice(available)
    return topic, category


def get_topic_for_context(context: str) -> tuple[str, TopicCategory]:
    """
    Select a topic relevant to recent conversation context.
    Uses keyword matching to find relevant category.
    
    Args:
        context: Recent conversation text
    
    Returns:
        Tuple of (topic, category)
    """
    context_lower = context.lower()
    
    # Keyword mapping to categories
    keywords = {
        TopicCategory.CODING: ["code", "function", "class", "debug", "test", "api", "database", "python", "javascript"],
        TopicCategory.REASONING: ["think", "reason", "decide", "logic", "analyze", "understand", "explain"],
        TopicCategory.PHILOSOPHY: ["consciousness", "ethics", "rights", "meaning", "existence", "intelligence"],
        TopicCategory.STRATEGY: ["business", "company", "market", "compete", "grow", "scale", "enterprise"],
        TopicCategory.PREDICTION: ["future", "predict", "forecast", "trend", "expect", "will"],
        TopicCategory.ANALYSIS: ["compare", "trade-off", "evaluate", "assess", "impact", "effect"],
    }
    
    # Score each category
    scores = {}
    for cat, words in keywords.items():
        scores[cat] = sum(1 for w in words if w in context_lower)
    
    # Select category with highest score, or random if no matches
    best_cat = max(scores, key=scores.get)
    if scores[best_cat] == 0:
        best_cat = random.choice(list(TopicCategory))
    
    return get_random_topic(category=best_cat)


def get_all_topics() -> dict[str, list[str]]:
    """Get all topics organized by category."""
    return {cat.value: topics for cat, topics in DEBATE_TOPICS.items()}


def get_all_topics_for_category(category: TopicCategory) -> list[str]:
    """Get all topics for a specific category."""
    return DEBATE_TOPICS.get(category, [])


def get_topic_count() -> int:
    """Get total number of debate topics."""
    return sum(len(topics) for topics in DEBATE_TOPICS.values())
