"""
Aura IA Debate Engine

Orchestrates multi-model debates with:
- 3-round structure (Opening, Rebuttal, Closing)
- Judge evaluation
- ELO rating updates
- Database persistence
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

from .elo import ELO_K_FACTOR, INITIAL_ELO, calculate_elo_change
from .prompts import (
    format_debate_transcript,
    get_debater_prompt,
    get_judge_prompt,
)
from .storage import get_pool, insert_debate, upsert_model_ranking
from .topics import TopicCategory, get_random_topic

try:
    import asyncpg  # type: ignore
except ImportError:  # pragma: no cover
    asyncpg = None

logger = logging.getLogger(__name__)


@dataclass
class DebateRound:
    """A single round in a debate."""

    round_number: int
    round_type: str  # opening, rebuttal, closing
    model_name: str
    position: str  # FOR or AGAINST
    argument: str
    tokens_used: int = 0
    latency_ms: int = 0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DebateResult:
    """Complete result of a debate."""

    debate_id: str
    topic: str
    topic_category: str
    model_a: str
    model_b: str
    position_a: str  # FOR or AGAINST
    position_b: str
    winner: Optional[str]  # model name or None for draw
    score_a: float
    score_b: float
    elo_before_a: int
    elo_before_b: int
    elo_change_a: int
    elo_change_b: int
    verdict: str
    rounds: list[DebateRound]
    started_at: datetime
    completed_at: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "debate_id": self.debate_id,
            "topic": self.topic,
            "topic_category": self.topic_category,
            "model_a": self.model_a,
            "model_b": self.model_b,
            "position_a": self.position_a,
            "position_b": self.position_b,
            "winner": self.winner,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "elo_before_a": self.elo_before_a,
            "elo_before_b": self.elo_before_b,
            "elo_change_a": self.elo_change_a,
            "elo_change_b": self.elo_change_b,
            "verdict": self.verdict,
            "rounds": [
                {
                    "round_number": r.round_number,
                    "round_type": r.round_type,
                    "model_name": r.model_name,
                    "position": r.position,
                    "argument": (
                        r.argument[:500] + "..."
                        if len(r.argument) > 500
                        else r.argument
                    ),
                }
                for r in self.rounds
            ],
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (
                self.completed_at - self.started_at
            ).total_seconds(),
        }


class DebateEngine:
    """
    Orchestrates debates between AI models.

    Debate Structure:
    1. Opening - Model A presents position
    2. Opening - Model B presents position
    3. Rebuttal - Model A responds to B
    4. Rebuttal - Model B responds to A
    5. Closing - Model A summarizes
    6. Closing - Model B summarizes
    7. Judge evaluates and declares winner
    """

    # Models that can debate (exclude phi3.5 - too small)
    DEBATE_MODELS = ["llama3.1:8b", "qwen2.5-coder:7b", "deepseek-r1:8b"]

    # Model to use as judge (best reasoner)
    JUDGE_MODEL = "llama3.1:8b"

    def __init__(
        self,
        ollama_url: str = "http://aura-ia-ollama:11434",
        model_ratings: Optional[dict[str, int]] = None,
    ):
        self.ollama_url = ollama_url
        self.model_ratings = model_ratings or {
            m: INITIAL_ELO for m in self.DEBATE_MODELS
        }
        self._debate_history: list[DebateResult] = []
        self._lock = asyncio.Lock()
        self._db_pool: Optional["asyncpg.Pool"] = None

    async def _generate(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 1024,
    ) -> tuple[str, int, int]:
        """
        Generate a response from Ollama.

        Returns:
            Tuple of (response_text, tokens_used, latency_ms)
        """
        start = datetime.now()

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": 0.7,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()

                text = data.get("response", "")
                tokens = data.get("eval_count", len(text.split()))
                latency = int((datetime.now() - start).total_seconds() * 1000)

                return text, tokens, latency

        except Exception as e:
            logger.error(f"Generation failed for {model}: {e}")
            latency = int((datetime.now() - start).total_seconds() * 1000)
            return f"[Error: {e}]", 0, latency

    def _select_models(
        self,
        model_a: Optional[str] = None,
        model_b: Optional[str] = None,
    ) -> tuple[str, str]:
        """Select two models for debate."""
        available = self.DEBATE_MODELS.copy()

        if model_a and model_a in available:
            selected_a = model_a
            available.remove(model_a)
        else:
            selected_a = random.choice(available)
            available.remove(selected_a)

        if model_b and model_b in available:
            selected_b = model_b
        else:
            selected_b = random.choice(available)

        return selected_a, selected_b

    def _parse_judge_verdict(
        self, verdict: str
    ) -> tuple[Optional[str], float, float]:
        """
        Parse judge's verdict to extract winner and scores.

        Returns:
            Tuple of (winner_position, score_a, score_b)
            winner_position is "A", "B", or None for tie
        """
        # Extract scores
        score_a = 50.0
        score_b = 50.0

        # Look for "Model A: XX/100" pattern
        score_match_a = re.search(
            r"Model A[:\s]+(\d+)\s*/\s*100", verdict, re.I
        )
        score_match_b = re.search(
            r"Model B[:\s]+(\d+)\s*/\s*100", verdict, re.I
        )

        if score_match_a:
            score_a = float(score_match_a.group(1))
        if score_match_b:
            score_b = float(score_match_b.group(1))

        # Determine winner
        winner = None
        if "WINNER: Model A" in verdict or "WINNER: MODEL A" in verdict:
            winner = "A"
        elif "WINNER: Model B" in verdict or "WINNER: MODEL B" in verdict:
            winner = "B"
        elif "WINNER: Tie" in verdict or "WINNER: TIE" in verdict:
            winner = None
        else:
            # Infer from scores
            if score_a > score_b + 5:
                winner = "A"
            elif score_b > score_a + 5:
                winner = "B"

        return winner, score_a, score_b

    async def run_debate(
        self,
        topic: Optional[str] = None,
        topic_category: Optional[TopicCategory] = None,
        model_a: Optional[str] = None,
        model_b: Optional[str] = None,
    ) -> DebateResult:
        """
        Run a complete debate between two models.

        Args:
            topic: Debate topic (random if None)
            topic_category: Category for random topic selection
            model_a: First model (random if None)
            model_b: Second model (random if None)

        Returns:
            DebateResult with full outcome
        """
        async with self._lock:
            debate_id = str(uuid.uuid4())
            started_at = datetime.now()

            # Select topic
            if topic is None:
                topic, category = get_random_topic(category=topic_category)
            else:
                category = topic_category or TopicCategory.REASONING

            # Select models
            selected_a, selected_b = self._select_models(model_a, model_b)

            # Randomly assign positions
            if random.random() > 0.5:
                position_a, position_b = "FOR", "AGAINST"
            else:
                position_a, position_b = "AGAINST", "FOR"

            logger.info(
                f"🎭 Debate #{debate_id[:8]}: {selected_a} vs {selected_b}"
            )
            logger.info(f"   Topic: {topic[:50]}...")

            rounds: list[DebateRound] = []

            # Round 1: Opening statements
            logger.info("   Round 1: Opening statements...")

            # Model A opening
            prompt_a = get_debater_prompt("opening", topic, position_a)
            arg_a, tokens_a, latency_a = await self._generate(
                selected_a, prompt_a
            )
            rounds.append(
                DebateRound(
                    round_number=1,
                    round_type="opening",
                    model_name=selected_a,
                    position=position_a,
                    argument=arg_a,
                    tokens_used=tokens_a,
                    latency_ms=latency_a,
                )
            )

            # Model B opening
            prompt_b = get_debater_prompt("opening", topic, position_b)
            arg_b, tokens_b, latency_b = await self._generate(
                selected_b, prompt_b
            )
            rounds.append(
                DebateRound(
                    round_number=1,
                    round_type="opening",
                    model_name=selected_b,
                    position=position_b,
                    argument=arg_b,
                    tokens_used=tokens_b,
                    latency_ms=latency_b,
                )
            )

            # Round 2: Rebuttals
            logger.info("   Round 2: Rebuttals...")

            # Model A rebuttal to B's opening
            prompt_a = get_debater_prompt(
                "rebuttal", topic, position_a, opponent_argument=arg_b
            )
            rebuttal_a, tokens_a, latency_a = await self._generate(
                selected_a, prompt_a
            )
            rounds.append(
                DebateRound(
                    round_number=2,
                    round_type="rebuttal",
                    model_name=selected_a,
                    position=position_a,
                    argument=rebuttal_a,
                    tokens_used=tokens_a,
                    latency_ms=latency_a,
                )
            )

            # Model B rebuttal to A's opening
            prompt_b = get_debater_prompt(
                "rebuttal", topic, position_b, opponent_argument=arg_a
            )
            rebuttal_b, tokens_b, latency_b = await self._generate(
                selected_b, prompt_b
            )
            rounds.append(
                DebateRound(
                    round_number=2,
                    round_type="rebuttal",
                    model_name=selected_b,
                    position=position_b,
                    argument=rebuttal_b,
                    tokens_used=tokens_b,
                    latency_ms=latency_b,
                )
            )

            # Round 3: Closing statements
            logger.info("   Round 3: Closing statements...")

            # Build history for closing
            history = format_debate_transcript(
                [
                    {
                        "round_type": "opening",
                        "model": selected_a,
                        "position": position_a,
                        "argument": arg_a,
                    },
                    {
                        "round_type": "opening",
                        "model": selected_b,
                        "position": position_b,
                        "argument": arg_b,
                    },
                    {
                        "round_type": "rebuttal",
                        "model": selected_a,
                        "position": position_a,
                        "argument": rebuttal_a,
                    },
                    {
                        "round_type": "rebuttal",
                        "model": selected_b,
                        "position": position_b,
                        "argument": rebuttal_b,
                    },
                ]
            )

            # Model A closing
            prompt_a = get_debater_prompt(
                "closing", topic, position_a, debate_history=history
            )
            closing_a, tokens_a, latency_a = await self._generate(
                selected_a, prompt_a
            )
            rounds.append(
                DebateRound(
                    round_number=3,
                    round_type="closing",
                    model_name=selected_a,
                    position=position_a,
                    argument=closing_a,
                    tokens_used=tokens_a,
                    latency_ms=latency_a,
                )
            )

            # Model B closing
            prompt_b = get_debater_prompt(
                "closing", topic, position_b, debate_history=history
            )
            closing_b, tokens_b, latency_b = await self._generate(
                selected_b, prompt_b
            )
            rounds.append(
                DebateRound(
                    round_number=3,
                    round_type="closing",
                    model_name=selected_b,
                    position=position_b,
                    argument=closing_b,
                    tokens_used=tokens_b,
                    latency_ms=latency_b,
                )
            )

            # Judge evaluation
            logger.info("   Judging...")

            full_transcript = format_debate_transcript(
                [
                    {
                        "round_type": r.round_type,
                        "model": r.model_name,
                        "position": r.position,
                        "argument": r.argument,
                    }
                    for r in rounds
                ]
            )

            judge_prompt = get_judge_prompt(
                topic=topic,
                model_a=selected_a,
                model_b=selected_b,
                position_a=position_a,
                position_b=position_b,
                transcript=full_transcript,
            )

            verdict, _, _ = await self._generate(
                self.JUDGE_MODEL, judge_prompt, max_tokens=1500
            )

            # Parse verdict
            winner_pos, score_a, score_b = self._parse_judge_verdict(verdict)

            # Determine winning model
            if winner_pos == "A":
                winner_model = selected_a
                elo_score_a = 1.0
            elif winner_pos == "B":
                winner_model = selected_b
                elo_score_a = 0.0
            else:
                winner_model = None
                elo_score_a = 0.5

            # Calculate ELO changes
            elo_before_a = self.model_ratings.get(selected_a, INITIAL_ELO)
            elo_before_b = self.model_ratings.get(selected_b, INITIAL_ELO)

            elo_change_a, elo_change_b = calculate_elo_change(
                elo_before_a, elo_before_b, elo_score_a
            )

            # Update ratings
            self.model_ratings[selected_a] = elo_before_a + elo_change_a
            self.model_ratings[selected_b] = elo_before_b + elo_change_b

            completed_at = datetime.now()

            # Build result
            result = DebateResult(
                debate_id=debate_id,
                topic=topic,
                topic_category=(
                    category.value
                    if hasattr(category, "value")
                    else str(category)
                ),
                model_a=selected_a,
                model_b=selected_b,
                position_a=position_a,
                position_b=position_b,
                winner=winner_model,
                score_a=score_a,
                score_b=score_b,
                elo_before_a=elo_before_a,
                elo_before_b=elo_before_b,
                elo_change_a=elo_change_a,
                elo_change_b=elo_change_b,
                verdict=verdict,
                rounds=rounds,
                started_at=started_at,
                completed_at=completed_at,
            )

            self._debate_history.append(result)

            # Persist to DB if asyncpg is available
            if asyncpg is not None:
                try:
                    if self._db_pool is None:
                        self._db_pool = await get_pool()

                    await insert_debate(self._db_pool, result)

                    # Update rankings: outcomes
                    if winner_model is None:
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_a,
                            self.model_ratings[selected_a],
                            elo_change_a,
                            "draw",
                        )
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_b,
                            self.model_ratings[selected_b],
                            elo_change_b,
                            "draw",
                        )
                    elif winner_model == selected_a:
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_a,
                            self.model_ratings[selected_a],
                            elo_change_a,
                            "win",
                        )
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_b,
                            self.model_ratings[selected_b],
                            elo_change_b,
                            "loss",
                        )
                    else:
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_a,
                            self.model_ratings[selected_a],
                            elo_change_a,
                            "loss",
                        )
                        await upsert_model_ranking(
                            self._db_pool,
                            selected_b,
                            self.model_ratings[selected_b],
                            elo_change_b,
                            "win",
                        )
                except Exception as e:
                    logger.error(f"Failed to persist debate: {e}")

            # Log outcome
            duration = (completed_at - started_at).total_seconds()
            logger.info(
                f"   ✅ Winner: {winner_model or 'Tie'} ({score_a:.0f} vs {score_b:.0f})"
            )
            logger.info(
                f"   ELO: {selected_a} {elo_change_a:+d}, {selected_b} {elo_change_b:+d}"
            )
            logger.info(f"   Duration: {duration:.1f}s")

            return result

    async def get_leaderboard(self) -> list[dict]:
        """Get current model rankings (prefers DB, falls back to memory)."""
        if asyncpg is not None and self._db_pool is not None:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT model_name AS model, elo_rating AS elo, wins, losses, draws, total_debates
                        FROM model_rankings
                        ORDER BY elo_rating DESC
                        """
                    )
                    return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Falling back to in-memory leaderboard: {e}")

        rankings = []
        for model, rating in sorted(
            self.model_ratings.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            wins = sum(1 for d in self._debate_history if d.winner == model)
            losses = sum(
                1
                for d in self._debate_history
                if d.winner
                and d.winner != model
                and (d.model_a == model or d.model_b == model)
            )
            draws = sum(
                1
                for d in self._debate_history
                if d.winner is None
                and (d.model_a == model or d.model_b == model)
            )
            rankings.append(
                {
                    "model": model,
                    "elo": rating,
                    "wins": wins,
                    "losses": losses,
                    "draws": draws,
                    "total_debates": wins + losses + draws,
                }
            )
        return rankings

    async def get_debate_history(self, limit: int = 10) -> list[dict]:
        """Get recent debate history."""
        if asyncpg is not None and self._db_pool is not None:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        """
                        SELECT id, topic, topic_category, model_a, model_b, winner, elo_change_a, elo_change_b,
                               score_a, score_b, verdict, started_at, completed_at
                        FROM debates
                        ORDER BY completed_at DESC NULLS LAST
                        LIMIT $1
                        """,
                        limit,
                    )
                    return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Falling back to in-memory history: {e}")

        recent = self._debate_history[-limit:]
        return [d.to_dict() for d in reversed(recent)]

    async def get_debate(self, debate_id: str) -> Optional[dict]:
        """Get a specific debate by ID."""
        # Try DB first
        if asyncpg is not None and self._db_pool is not None:
            try:
                async with self._db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT id, topic, topic_category, model_a, model_b, winner, elo_change_a, elo_change_b,
                               score_a, score_b, verdict, rounds, started_at, completed_at
                        FROM debates d
                        LEFT JOIN (
                            SELECT debate_id, json_agg(
                                json_build_object(
                                    'round_number', round_number,
                                    'round_type', round_type,
                                    'model_name', model_name,
                                    'position', position,
                                    'argument', argument
                                ) ORDER BY round_number
                            ) as rounds
                            FROM debate_rounds
                            GROUP BY debate_id
                        ) r ON d.id = r.debate_id
                        WHERE d.id = $1
                        """,
                        debate_id,
                    )
                    if row:
                        data = dict(row)
                        # Fix UUID to string
                        if data.get("id"):
                            data["id"] = str(data["id"])
                        if data.get("rounds"):
                            import json

                            if isinstance(data["rounds"], str):
                                data["rounds"] = json.loads(data["rounds"])
                        return data
            except Exception as e:
                logger.error(f"Error fetching debate {debate_id}: {e}")

        # Fallback to memory
        for debate in self._debate_history:
            if debate.debate_id == debate_id:
                return debate.to_dict()

        return None


# Singleton instance
_debate_engine: Optional[DebateEngine] = None


async def get_debate_engine() -> DebateEngine:
    """Get or create the debate engine singleton."""
    global _debate_engine
    if _debate_engine is None:
        _debate_engine = DebateEngine()
    return _debate_engine
