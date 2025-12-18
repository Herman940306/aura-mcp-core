"""
Debate storage helpers for PostgreSQL persistence.
"""

from __future__ import annotations

import os
from typing import Optional

import asyncpg


async def get_pool() -> asyncpg.Pool:
    """Get a shared asyncpg pool configured from environment."""
    host = os.getenv("POSTGRES_HOST", "aura-ia-postgres")
    port = int(os.getenv("POSTGRES_PORT", "5432"))
    user = os.getenv("POSTGRES_USER", "Admin")
    password = os.getenv("POSTGRES_PASSWORD", "")
    database = os.getenv("POSTGRES_DB", "aura_db")

    return await asyncpg.create_pool(
        host=host,
        port=port,
        user=user,
        password=password or None,
        database=database,
        min_size=1,
        max_size=5,
    )


async def upsert_model_ranking(
    pool: asyncpg.Pool,
    model: str,
    elo: int,
    elo_change: int,
    outcome: str,
) -> None:
    """Update model_rankings wins/losses/draws and rating."""
    outcome_field = {
        "win": "wins",
        "loss": "losses",
        "draw": "draws",
    }[outcome]

    async with pool.acquire() as conn:
        await conn.execute(
            f"""
            UPDATE model_rankings
            SET elo_rating = $1,
                {outcome_field} = {outcome_field} + 1,
                total_debates = total_debates + 1,
                updated_at = NOW()
            WHERE model_name = $2
            """,
            elo,
            model,
        )


async def insert_debate(
    pool: asyncpg.Pool,
    result,
) -> None:
    """Persist debate summary and rounds."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO debates (
                id, topic, topic_category, model_a, model_b, judge_model,
                winner, elo_change_a, elo_change_b, elo_before_a, elo_before_b,
                score_a, score_b, verdict, started_at, completed_at, status, total_rounds
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14, $15, $16, 'completed', 3
            )
            ON CONFLICT (id) DO NOTHING
            """,
            result.debate_id,
            result.topic,
            result.topic_category,
            result.model_a,
            result.model_b,
            result.__dict__.get("judge_model", "llama3.1:8b"),
            result.winner,
            result.elo_change_a,
            result.elo_change_b,
            result.elo_before_a,
            result.elo_before_b,
            result.score_a,
            result.score_b,
            result.verdict,
            result.started_at,
            result.completed_at,
        )

        rounds_payload = [
            (
                r.round_number,
                r.round_type,
                r.model_name,
                r.position,
                r.argument,
                r.tokens_used,
                r.latency_ms,
            )
            for r in result.rounds
        ]

        await conn.executemany(
            """
            INSERT INTO debate_rounds (
                id, debate_id, round_number, round_type, model_name, position,
                argument, tokens_used, latency_ms
            ) VALUES (
                gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8
            )
            """,
            [
                (
                    result.debate_id,
                    rn,
                    rt,
                    mn,
                    pos,
                    arg,
                    tok,
                    lat,
                )
                for (rn, rt, mn, pos, arg, tok, lat) in rounds_payload
            ],
        )
