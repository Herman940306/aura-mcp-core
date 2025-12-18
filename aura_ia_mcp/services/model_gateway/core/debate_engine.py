"""
Advanced Dual-Model Debate Engine with Adversarial Reasoning.

This module implements a sophisticated debate system where two AI models
engage in structured adversarial reasoning to arrive at better conclusions.

Features:
- Round-based debate with position assignment
- Evidence tracking and claim verification
- Confidence scoring and consensus detection
- Judge model for final arbitration
- Audit logging for transparency
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class DebatePosition(Enum):
    """Position in a debate."""

    PROPONENT = "proponent"
    OPPONENT = "opponent"
    JUDGE = "judge"
    NEUTRAL = "neutral"


class DebatePhase(Enum):
    """Phase of the debate."""

    OPENING = "opening"
    ARGUMENT = "argument"
    REBUTTAL = "rebuttal"
    CLOSING = "closing"
    JUDGMENT = "judgment"


@dataclass
class Claim:
    """A claim made during debate."""

    text: str
    source_model: str
    position: DebatePosition
    phase: DebatePhase
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)
    rebuttals: list[str] = field(default_factory=list)
    verified: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_model": self.source_model,
            "position": self.position.value,
            "phase": self.phase.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "rebuttals": self.rebuttals,
            "verified": self.verified,
        }


@dataclass
class DebateTurn:
    """A single turn in the debate."""

    model: str
    position: DebatePosition
    phase: DebatePhase
    content: str
    claims: list[Claim] = field(default_factory=list)
    reasoning_trace: list[str] = field(default_factory=list)
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "position": self.position.value,
            "phase": self.phase.value,
            "content": self.content,
            "claims": [c.to_dict() for c in self.claims],
            "reasoning_trace": self.reasoning_trace,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class DebateResult:
    """Result of a complete debate."""

    debate_id: str
    topic: str
    turns: list[DebateTurn]
    winner: str | None = None
    consensus_reached: bool = False
    consensus_position: str | None = None
    final_verdict: str | None = None
    confidence_score: float = 0.0
    reasoning_summary: str = ""
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "debate_id": self.debate_id,
            "topic": self.topic,
            "turns": [t.to_dict() for t in self.turns],
            "winner": self.winner,
            "consensus_reached": self.consensus_reached,
            "consensus_position": self.consensus_position,
            "final_verdict": self.final_verdict,
            "confidence_score": self.confidence_score,
            "reasoning_summary": self.reasoning_summary,
            "audit_hash": self.audit_hash,
        }


class ModelBackend(Protocol):
    """Protocol for model backends."""

    async def generate(
        self, prompt: str, model: str, options: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...


class DebateEngine:
    """
    Advanced debate engine for adversarial reasoning between models.

    This engine orchestrates structured debates between two AI models,
    with an optional judge model for final arbitration.
    """

    def __init__(
        self,
        proponent_backend: ModelBackend,
        opponent_backend: ModelBackend,
        judge_backend: ModelBackend | None = None,
        audit_log_path: str | None = None,
    ):
        self.proponent_backend = proponent_backend
        self.opponent_backend = opponent_backend
        self.judge_backend = judge_backend or proponent_backend
        self.prompts_dir = Path(__file__).parent / "prompts"

        # Audit logging
        self.audit_enabled = os.environ.get("DEBATE_AUDIT_LOG", "1") in (
            "1",
            "true",
        )
        self.audit_path = audit_log_path or os.environ.get(
            "DEBATE_AUDIT_PATH", "logs/debate_audit.jsonl"
        )

        # Debate configuration
        self.max_rounds = int(os.environ.get("DEBATE_MAX_ROUNDS", "5"))
        self.consensus_threshold = float(
            os.environ.get("DEBATE_CONSENSUS_THRESHOLD", "0.8")
        )
        self.early_consensus_enabled = os.environ.get(
            "DEBATE_EARLY_CONSENSUS", "1"
        ) in ("1", "true")

    def _generate_debate_id(self, topic: str) -> str:
        """Generate unique debate ID."""
        timestamp = str(time.time())
        content = f"{topic}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_audit_hash(self, turns: list[DebateTurn]) -> str:
        """Compute hash for audit integrity."""
        content = json.dumps([t.to_dict() for t in turns], sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _log_audit(self, result: DebateResult) -> None:
        """Log debate result for audit."""
        if not self.audit_enabled:
            return

        try:
            Path(self.audit_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_path, "a") as f:
                f.write(json.dumps(result.to_dict()) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write audit log: {e}")

    def _build_opening_prompt(
        self, topic: str, position: DebatePosition
    ) -> str:
        """Build opening statement prompt."""
        if position == DebatePosition.PROPONENT:
            return f"""You are the PROPONENT in a structured debate.

TOPIC: {topic}

Your task is to deliver an OPENING STATEMENT that:
1. Clearly states your position supporting the topic
2. Outlines your main arguments (3-5 key points)
3. Presents initial evidence or reasoning
4. Sets the framework for your case

Be clear, logical, and persuasive. Cite evidence where possible.
Mark your key claims with [CLAIM: ...] tags for tracking.

OPENING STATEMENT:"""

        return f"""You are the OPPONENT in a structured debate.

TOPIC: {topic}

Your task is to deliver an OPENING STATEMENT that:
1. Clearly states your position opposing/challenging the topic
2. Outlines your main counter-arguments (3-5 key points)
3. Presents initial evidence or reasoning against
4. Identifies potential weaknesses in the proponent's likely arguments

Be clear, logical, and persuasive. Cite evidence where possible.
Mark your key claims with [CLAIM: ...] tags for tracking.

OPENING STATEMENT:"""

    def _build_argument_prompt(
        self,
        topic: str,
        position: DebatePosition,
        previous_turns: list[DebateTurn],
        round_num: int,
    ) -> str:
        """Build argument/rebuttal prompt."""
        history = self._format_history(previous_turns)

        phase = "ARGUMENT" if round_num <= 2 else "REBUTTAL"

        if position == DebatePosition.PROPONENT:
            return f"""You are the PROPONENT in round {round_num} of a structured debate.

TOPIC: {topic}

DEBATE HISTORY:
{history}

Your task for this {phase} ROUND:
1. Address the opponent's most recent points
2. Strengthen your existing arguments with new evidence
3. Identify logical flaws in the opponent's reasoning
4. Maintain coherence with your opening position

Rules:
- Stay on topic and address specific claims
- Use [CLAIM: ...] tags for new claims
- Use [REBUTTAL: ...] tags when countering opponent claims
- Provide reasoning trace with [REASONING: ...]

YOUR {phase}:"""

        return f"""You are the OPPONENT in round {round_num} of a structured debate.

TOPIC: {topic}

DEBATE HISTORY:
{history}

Your task for this {phase} ROUND:
1. Address the proponent's most recent points
2. Strengthen your counter-arguments with new evidence
3. Identify logical flaws in the proponent's reasoning
4. Maintain coherence with your opening position

Rules:
- Stay on topic and address specific claims
- Use [CLAIM: ...] tags for new claims
- Use [REBUTTAL: ...] tags when countering proponent claims
- Provide reasoning trace with [REASONING: ...]

YOUR {phase}:"""

    def _build_closing_prompt(
        self, topic: str, position: DebatePosition, all_turns: list[DebateTurn]
    ) -> str:
        """Build closing statement prompt."""
        history = self._format_history(all_turns)
        pos_name = (
            "PROPONENT" if position == DebatePosition.PROPONENT else "OPPONENT"
        )

        return f"""You are the {pos_name} delivering your CLOSING STATEMENT.

TOPIC: {topic}

FULL DEBATE:
{history}

Your CLOSING STATEMENT should:
1. Summarize your strongest arguments
2. Highlight unaddressed weaknesses in the opponent's case
3. Reinforce why your position is correct
4. End with a clear, memorable conclusion

Provide a confidence score (0.0-1.0) for your position with [CONFIDENCE: X.X]

CLOSING STATEMENT:"""

    def _build_judge_prompt(
        self, topic: str, all_turns: list[DebateTurn]
    ) -> str:
        """Build judge's verdict prompt."""
        history = self._format_history(all_turns)

        return f"""You are the JUDGE in a structured debate. Your role is to provide an impartial verdict.

TOPIC: {topic}

FULL DEBATE:
{history}

Evaluate the debate on these criteria:
1. LOGICAL COHERENCE: Which side presented more logically sound arguments?
2. EVIDENCE QUALITY: Which side provided better supporting evidence?
3. REBUTTAL EFFECTIVENESS: Which side more effectively countered the other's arguments?
4. CONSISTENCY: Which side maintained a more consistent position throughout?

Provide your VERDICT with:
- [WINNER: proponent/opponent/tie]
- [CONFIDENCE: X.X] (0.0-1.0)
- [CONSENSUS: true/false] - Did the sides converge on any points?
- A reasoning summary explaining your decision

VERDICT:"""

    def _format_history(self, turns: list[DebateTurn]) -> str:
        """Format debate history for prompts."""
        lines = []
        for turn in turns:
            pos = turn.position.value.upper()
            phase = turn.phase.value.upper()
            lines.append(f"[{pos} - {phase}]")
            lines.append(turn.content)
            lines.append("")
        return "\n".join(lines)

    def _extract_claims(
        self,
        content: str,
        model: str,
        position: DebatePosition,
        phase: DebatePhase,
    ) -> list[Claim]:
        """Extract claims from response content."""
        claims = []

        # Extract [CLAIM: ...] tags
        import re

        claim_pattern = r"\[CLAIM:\s*([^\]]+)\]"
        matches = re.findall(claim_pattern, content, re.IGNORECASE)

        for match in matches:
            claims.append(
                Claim(
                    text=match.strip(),
                    source_model=model,
                    position=position,
                    phase=phase,
                )
            )

        return claims

    def _extract_confidence(self, content: str) -> float:
        """Extract confidence score from content."""
        import re

        conf_pattern = r"\[CONFIDENCE:\s*([\d.]+)\]"
        match = re.search(conf_pattern, content, re.IGNORECASE)
        if match:
            try:
                return min(1.0, max(0.0, float(match.group(1))))
            except ValueError:
                pass
        return 0.5

    def _extract_reasoning(self, content: str) -> list[str]:
        """Extract reasoning traces from content."""
        import re

        reasoning_pattern = r"\[REASONING:\s*([^\]]+)\]"
        matches = re.findall(reasoning_pattern, content, re.IGNORECASE)
        return [m.strip() for m in matches]

    def _parse_judge_verdict(
        self, content: str
    ) -> tuple[str | None, bool, float, str]:
        """Parse judge's verdict."""
        import re

        # Extract winner
        winner = None
        winner_match = re.search(
            r"\[WINNER:\s*(\w+)\]", content, re.IGNORECASE
        )
        if winner_match:
            w = winner_match.group(1).lower()
            if w in ("proponent", "opponent", "tie"):
                winner = w

        # Extract consensus
        consensus = False
        consensus_match = re.search(
            r"\[CONSENSUS:\s*(\w+)\]", content, re.IGNORECASE
        )
        if consensus_match:
            consensus = consensus_match.group(1).lower() == "true"

        # Extract confidence
        confidence = self._extract_confidence(content)

        # Extract reasoning (everything after VERDICT markers)
        reasoning = content
        for marker in ("[WINNER:", "[CONSENSUS:", "[CONFIDENCE:"):
            reasoning = (
                reasoning.split(marker)[0]
                if marker in reasoning
                else reasoning
            )

        return winner, consensus, confidence, reasoning.strip()

    async def run_debate(
        self,
        topic: str,
        proponent_model: str,
        opponent_model: str,
        judge_model: str | None = None,
        rounds: int = 3,
    ) -> DebateResult:
        """
        Run a full structured debate.

        Args:
            topic: The debate topic/question
            proponent_model: Model name for proponent
            opponent_model: Model name for opponent
            judge_model: Model name for judge (defaults to proponent_model)
            rounds: Number of argument rounds (excluding opening/closing)

        Returns:
            DebateResult with full debate record
        """
        debate_id = self._generate_debate_id(topic)
        turns: list[DebateTurn] = []
        judge_model = judge_model or proponent_model

        rounds = min(rounds, self.max_rounds)

        logger.info(f"Starting debate {debate_id}: {topic}")

        # Phase 1: Opening Statements
        # Proponent opens
        prompt_p = self._build_opening_prompt(topic, DebatePosition.PROPONENT)
        resp_p = await self.proponent_backend.generate(
            prompt_p, proponent_model
        )
        content_p = resp_p.get("response", "")

        turn_p = DebateTurn(
            model=proponent_model,
            position=DebatePosition.PROPONENT,
            phase=DebatePhase.OPENING,
            content=content_p,
            claims=self._extract_claims(
                content_p,
                proponent_model,
                DebatePosition.PROPONENT,
                DebatePhase.OPENING,
            ),
            reasoning_trace=self._extract_reasoning(content_p),
            confidence=self._extract_confidence(content_p),
        )
        turns.append(turn_p)

        # Opponent opens
        prompt_o = self._build_opening_prompt(topic, DebatePosition.OPPONENT)
        resp_o = await self.opponent_backend.generate(prompt_o, opponent_model)
        content_o = resp_o.get("response", "")

        turn_o = DebateTurn(
            model=opponent_model,
            position=DebatePosition.OPPONENT,
            phase=DebatePhase.OPENING,
            content=content_o,
            claims=self._extract_claims(
                content_o,
                opponent_model,
                DebatePosition.OPPONENT,
                DebatePhase.OPENING,
            ),
            reasoning_trace=self._extract_reasoning(content_o),
            confidence=self._extract_confidence(content_o),
        )
        turns.append(turn_o)

        # Phase 2: Argument/Rebuttal Rounds
        for round_num in range(1, rounds + 1):
            phase = (
                DebatePhase.ARGUMENT
                if round_num <= rounds // 2
                else DebatePhase.REBUTTAL
            )

            # Proponent argues
            prompt_p = self._build_argument_prompt(
                topic, DebatePosition.PROPONENT, turns, round_num
            )
            resp_p = await self.proponent_backend.generate(
                prompt_p, proponent_model
            )
            content_p = resp_p.get("response", "")

            turn_p = DebateTurn(
                model=proponent_model,
                position=DebatePosition.PROPONENT,
                phase=phase,
                content=content_p,
                claims=self._extract_claims(
                    content_p, proponent_model, DebatePosition.PROPONENT, phase
                ),
                reasoning_trace=self._extract_reasoning(content_p),
                confidence=self._extract_confidence(content_p),
            )
            turns.append(turn_p)

            # Opponent argues
            prompt_o = self._build_argument_prompt(
                topic, DebatePosition.OPPONENT, turns, round_num
            )
            resp_o = await self.opponent_backend.generate(
                prompt_o, opponent_model
            )
            content_o = resp_o.get("response", "")

            turn_o = DebateTurn(
                model=opponent_model,
                position=DebatePosition.OPPONENT,
                phase=phase,
                content=content_o,
                claims=self._extract_claims(
                    content_o, opponent_model, DebatePosition.OPPONENT, phase
                ),
                reasoning_trace=self._extract_reasoning(content_o),
                confidence=self._extract_confidence(content_o),
            )
            turns.append(turn_o)

            # Early consensus check
            if self.early_consensus_enabled and round_num >= 2:
                p_conf = turn_p.confidence
                o_conf = turn_o.confidence
                # If both have low confidence, might be converging
                if p_conf < 0.4 and o_conf < 0.4:
                    logger.info(
                        f"Debate {debate_id}: Early consensus signal detected"
                    )
                    break

        # Phase 3: Closing Statements
        prompt_p_close = self._build_closing_prompt(
            topic, DebatePosition.PROPONENT, turns
        )
        resp_p_close = await self.proponent_backend.generate(
            prompt_p_close, proponent_model
        )
        content_p_close = resp_p_close.get("response", "")

        turns.append(
            DebateTurn(
                model=proponent_model,
                position=DebatePosition.PROPONENT,
                phase=DebatePhase.CLOSING,
                content=content_p_close,
                claims=self._extract_claims(
                    content_p_close,
                    proponent_model,
                    DebatePosition.PROPONENT,
                    DebatePhase.CLOSING,
                ),
                reasoning_trace=self._extract_reasoning(content_p_close),
                confidence=self._extract_confidence(content_p_close),
            )
        )

        prompt_o_close = self._build_closing_prompt(
            topic, DebatePosition.OPPONENT, turns
        )
        resp_o_close = await self.opponent_backend.generate(
            prompt_o_close, opponent_model
        )
        content_o_close = resp_o_close.get("response", "")

        turns.append(
            DebateTurn(
                model=opponent_model,
                position=DebatePosition.OPPONENT,
                phase=DebatePhase.CLOSING,
                content=content_o_close,
                claims=self._extract_claims(
                    content_o_close,
                    opponent_model,
                    DebatePosition.OPPONENT,
                    DebatePhase.CLOSING,
                ),
                reasoning_trace=self._extract_reasoning(content_o_close),
                confidence=self._extract_confidence(content_o_close),
            )
        )

        # Phase 4: Judge's Verdict
        prompt_judge = self._build_judge_prompt(topic, turns)
        resp_judge = await self.judge_backend.generate(
            prompt_judge, judge_model
        )
        content_judge = resp_judge.get("response", "")

        winner, consensus, confidence, reasoning = self._parse_judge_verdict(
            content_judge
        )

        turns.append(
            DebateTurn(
                model=judge_model,
                position=DebatePosition.JUDGE,
                phase=DebatePhase.JUDGMENT,
                content=content_judge,
                claims=[],
                reasoning_trace=[reasoning],
                confidence=confidence,
            )
        )

        # Build result
        result = DebateResult(
            debate_id=debate_id,
            topic=topic,
            turns=turns,
            winner=winner,
            consensus_reached=consensus,
            consensus_position=winner if consensus else None,
            final_verdict=content_judge,
            confidence_score=confidence,
            reasoning_summary=reasoning,
            audit_hash=self._compute_audit_hash(turns),
        )

        # Log for audit
        self._log_audit(result)

        logger.info(
            f"Debate {debate_id} complete: winner={winner}, consensus={consensus}, "
            f"confidence={confidence:.2f}"
        )

        return result

    async def quick_debate(
        self,
        question: str,
        model: str,
        rounds: int = 2,
    ) -> DebateResult:
        """
        Run a quick self-debate using the same model for both sides.

        Useful for exploring multiple perspectives on a question.
        """
        return await self.run_debate(
            topic=question,
            proponent_model=model,
            opponent_model=model,
            judge_model=model,
            rounds=rounds,
        )
