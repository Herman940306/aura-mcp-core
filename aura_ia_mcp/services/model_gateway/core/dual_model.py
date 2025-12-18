"""Dual-model conversation engine for improved reasoning."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aura_ia_mcp.services.model_gateway.retrieval_pipeline import (
    RetrievalConfig,
    Retriever,
)


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    model: str
    role: str
    content: str
    metadata: dict[str, Any] | None = None


class DualModelEngine:
    """Orchestrate conversation between two models."""

    def __init__(self, backend_a, backend_b):
        """
        Initialize dual-model engine.

        Args:
            backend_a: First model backend
            backend_b: Second model backend
        """
        self.backend_a = backend_a
        self.backend_b = backend_b
        self.prompts_dir = Path(__file__).parent / "prompts"
        # Retrieval wiring (feature-flagged)
        self.retriever: Retriever | None = None
        self.retrieval_enabled: bool = bool(
            os.environ.get("RETRIEVAL_ENABLED", "0") in ("1", "true", "True")
        )
        if self.retrieval_enabled:
            coll = os.environ.get("RETRIEVAL_COLLECTION", "default")
            top_k = int(os.environ.get("RETRIEVAL_TOP_K", "5"))
            budget = int(os.environ.get("RETRIEVAL_BUDGET_TOKENS", "1024"))
            # Defer actual client wiring; assume embed_fn provided by model_a
            embed_fn = getattr(self.backend_a, "embed", lambda x: [0.0])
            try:
                from qdrant_client import QdrantClient

                client = QdrantClient(
                    os.environ.get("QDRANT_URL", "http://localhost:6333")
                )
            except Exception:
                client = None
            self.retriever = Retriever(
                client,
                embed_fn,
                RetrievalConfig(
                    collection=coll,
                    top_k=top_k,
                    retrieval_budget_tokens=budget,
                ),
            )

    def load_system_prompt(self, prompt_name: str) -> str:
        """Load a system prompt from file."""
        prompt_path = self.prompts_dir / f"{prompt_name}.md"
        if not prompt_path.exists():
            raise ValueError(f"Prompt not found: {prompt_name}")
        return prompt_path.read_text()

    async def run_conversation(
        self,
        user_message: str,
        model_a: str,
        model_b: str,
        prompt_a: str = "base_system",
        prompt_b: str = "critic_mode",
        exchanges: int = 2,
    ) -> list[ConversationTurn]:
        """
        Run a dual-model conversation.

        Args:
            user_message: Initial user message
            model_a: Name of first model
            model_b: Name of second model
            prompt_a: System prompt for model A
            prompt_b: System prompt for model B
            exchanges: Number of back-and-forth exchanges

        Returns:
            List of conversation turns
        """
        conversation: list[ConversationTurn] = []

        # Load system prompts
        system_a = self.load_system_prompt(prompt_a)
        system_b = self.load_system_prompt(prompt_b)

        # Optional retrieval context
        retrieval_ctx = []
        if self.retrieval_enabled and self.retriever is not None:
            retrieval_ctx = self.retriever.retrieve(user_message)
        ctx_text = "\n\n".join(d.get("text", "") for d in retrieval_ctx)

        # Initial context
        context_a = f"{system_a}\n\nUser: {user_message}"
        context_b = f"{system_b}\n\nUser: {user_message}"

        for i in range(exchanges):
            # Model A responds
            response_a = await self.backend_a.generate(
                prompt=context_a, model=model_a
            )
            content_a = response_a.get("response", "")

            turn_a = ConversationTurn(
                model=model_a,
                role="assistant_a",
                content=content_a,
                metadata={"exchange": i, "prompt": prompt_a},
            )
            conversation.append(turn_a)

            # Update context for Model B
            context_b += f"\n\nModel A ({model_a}): {content_a}"

            # Model B responds
            response_b = await self.backend_b.generate(
                prompt=context_b, model=model_b
            )
            content_b = response_b.get("response", "")

            turn_b = ConversationTurn(
                model=model_b,
                role="assistant_b",
                content=content_b,
                metadata={"exchange": i, "prompt": prompt_b},
            )
            conversation.append(turn_b)

            # Update context for Model A
            context_a += f"\n\nModel B ({model_b}): {content_b}"

        return conversation

    async def run_debate(
        self, topic: str, model_a: str, model_b: str, rounds: int = 3
    ) -> list[ConversationTurn]:
        """
        Run a debate between two models.

        Args:
            topic: Debate topic
            model_a: First model
            model_b: Second model (takes opposing view)
            rounds: Number of debate rounds

        Returns:
            List of debate turns
        """
        prompt_a = f"""You are debating the topic: "{topic}"

Take a position and argue for it with evidence and reasoning.
Be persuasive but intellectually honest."""

        prompt_b = f"""You are debating the topic: "{topic}"

Take the OPPOSING position to your debate partner.
Challenge their arguments and present counterpoints."""

        return await self.run_conversation(
            user_message=f"Debate topic: {topic}",
            model_a=model_a,
            model_b=model_b,
            prompt_a="developer_mode",  # Use as base, will be overridden
            prompt_b="critic_mode",
            exchanges=rounds,
        )
