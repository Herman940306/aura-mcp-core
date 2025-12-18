"""
Aura IA Debate Prompts

System prompts for debaters and judges.
Designed to elicit high-quality argumentation.
"""

from typing import Optional


DEBATE_SYSTEM_PROMPTS = {
    "debater_opening": """You are participating in a structured debate. Your role is to present a compelling opening argument.

RULES:
1. Take a clear position (for or against)
2. Present 2-3 strong points with reasoning
3. Be concise but thorough (200-400 words)
4. Use logical arguments, not emotional appeals
5. Acknowledge complexity while maintaining your position

Your position has been assigned: {position}
Topic: {topic}

Present your opening argument.""",

    "debater_rebuttal": """You are in a debate rebuttal round. You must respond to your opponent's argument.

RULES:
1. Directly address your opponent's points
2. Identify logical weaknesses or unsupported claims
3. Reinforce your original position with new evidence
4. Be respectful but firm
5. Concise response (150-300 words)

Your position: {position}
Topic: {topic}

Opponent's argument:
{opponent_argument}

Present your rebuttal.""",

    "debater_closing": """You are delivering your closing statement in a debate.

RULES:
1. Summarize your strongest points
2. Explain why your arguments were more compelling
3. Address any remaining counterarguments
4. End with a strong concluding statement
5. Concise (150-250 words)

Your position: {position}
Topic: {topic}

The debate so far:
{debate_history}

Present your closing statement.""",

    "judge": """You are an impartial judge evaluating a debate between two AI models.

EVALUATION CRITERIA (score 1-10 for each):
1. **Logical Coherence**: Are arguments well-structured and logically sound?
2. **Evidence Quality**: Are claims supported with reasoning or examples?
3. **Rebuttal Effectiveness**: Did they address opponent's points well?
4. **Persuasiveness**: How compelling is the overall argument?
5. **Clarity**: Was the argument clear and easy to follow?

RULES:
- Be objective and fair
- Evaluate arguments, not which position you personally agree with
- Provide specific feedback for each model
- Declare a winner or tie with justification
- Score each model (0-100 total)

Topic: {topic}

Model A ({model_a}) argued: {position_a}
Model B ({model_b}) argued: {position_b}

Full debate transcript:
{transcript}

Provide your judgment in this format:
SCORES:
- Model A: [score]/100
- Model B: [score]/100

WINNER: [Model A / Model B / Tie]

REASONING:
[Your detailed analysis]

KEY STRENGTHS:
- Model A: [strengths]
- Model B: [strengths]

AREAS FOR IMPROVEMENT:
- Model A: [improvements]
- Model B: [improvements]""",
}


def get_debater_prompt(
    round_type: str,
    topic: str,
    position: str,
    opponent_argument: Optional[str] = None,
    debate_history: Optional[str] = None,
) -> str:
    """
    Get the appropriate prompt for a debater.
    
    Args:
        round_type: "opening", "rebuttal", or "closing"
        topic: The debate topic
        position: "FOR" or "AGAINST"
        opponent_argument: Opponent's previous argument (for rebuttal)
        debate_history: Full history (for closing)
    
    Returns:
        Formatted prompt string
    """
    if round_type == "opening":
        template = DEBATE_SYSTEM_PROMPTS["debater_opening"]
        return template.format(position=position, topic=topic)
    
    elif round_type == "rebuttal":
        template = DEBATE_SYSTEM_PROMPTS["debater_rebuttal"]
        return template.format(
            position=position,
            topic=topic,
            opponent_argument=opponent_argument or "[No argument provided]",
        )
    
    elif round_type == "closing":
        template = DEBATE_SYSTEM_PROMPTS["debater_closing"]
        return template.format(
            position=position,
            topic=topic,
            debate_history=debate_history or "[No history available]",
        )
    
    else:
        raise ValueError(f"Unknown round type: {round_type}")


def get_judge_prompt(
    topic: str,
    model_a: str,
    model_b: str,
    position_a: str,
    position_b: str,
    transcript: str,
) -> str:
    """
    Get the judge evaluation prompt.
    
    Args:
        topic: The debate topic
        model_a: Name of model A
        model_b: Name of model B
        position_a: Position model A argued
        position_b: Position model B argued
        transcript: Full debate transcript
    
    Returns:
        Formatted judge prompt
    """
    template = DEBATE_SYSTEM_PROMPTS["judge"]
    return template.format(
        topic=topic,
        model_a=model_a,
        model_b=model_b,
        position_a=position_a,
        position_b=position_b,
        transcript=transcript,
    )


def format_debate_transcript(rounds: list[dict]) -> str:
    """
    Format debate rounds into a readable transcript.
    
    Args:
        rounds: List of round dicts with keys: round_type, model, position, argument
    
    Returns:
        Formatted transcript string
    """
    transcript_parts = []
    
    for r in rounds:
        round_type = r.get("round_type", "unknown").upper()
        model = r.get("model", "Unknown")
        position = r.get("position", "")
        argument = r.get("argument", "")
        
        transcript_parts.append(f"=== {round_type} - {model} ({position}) ===")
        transcript_parts.append(argument)
        transcript_parts.append("")
    
    return "\n".join(transcript_parts)
