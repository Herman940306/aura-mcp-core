"""
Aura IA Debate Engine

Multi-model debate system with ELO rankings.
Models compete on reasoning tasks, code challenges, and analysis.
"""

from .elo import (
    calculate_elo_change,
    expected_score,
    update_ratings,
    ELO_K_FACTOR,
    INITIAL_ELO,
)
from .topics import (
    DEBATE_TOPICS,
    get_random_topic,
    get_topic_for_context,
    get_all_topics_for_category,
    TopicCategory,
)
from .engine import (
    DebateEngine,
    DebateResult,
    DebateRound,
    get_debate_engine,
)
from .prompts import (
    DEBATE_SYSTEM_PROMPTS,
    get_debater_prompt,
    get_judge_prompt,
    format_debate_transcript,
)
from .storage import get_pool, insert_debate, upsert_model_ranking

__all__ = [
    # ELO
    "calculate_elo_change",
    "expected_score",
    "update_ratings",
    "ELO_K_FACTOR",
    "INITIAL_ELO",
    # Topics
    "DEBATE_TOPICS",
    "get_random_topic",
    "get_topic_for_context",
    "get_all_topics_for_category",
    "TopicCategory",
    # Engine
    "DebateEngine",
    "DebateResult",
    "DebateRound",
    "get_debate_engine",
    "get_pool",
    "insert_debate",
    "upsert_model_ranking",
    # Prompts
    "DEBATE_SYSTEM_PROMPTS",
    "get_debater_prompt",
    "get_judge_prompt",
    "format_debate_transcript",
]
