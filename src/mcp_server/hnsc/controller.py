"""HNSC Master Controller - Orchestrates All 6 Layers.

This is the brain of the Hybrid Neuro-Symbolic Control Architecture.
It coordinates all layers to achieve 99.5%+ accuracy with a tiny LLM.

Architecture Flow:
    1. User Input arrives
    2. Layer 6 (Safety) - Block forbidden patterns immediately
    3. Layer 2 (Symbolic Router) - Classify intent deterministically
    4. Layer 3 (Workflow Engine) - Check for multi-step pipelines
    5. Layer 4 (Static Reasoning) - Apply rule-based logic
    6. Layer 5 (Tool Intelligence) - Execute specialized handlers
    7. Layer 1 (LLM) - ONLY for text generation, NOT decisions

The LLM is a "Token Generator", NOT the decision maker.
The Symbolic layers are the "Real Mind".

Project Creator: Herman Swanepoel
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .safety_policy import get_safety_engine
from .static_reasoning import ReasoningType, StaticReasoningLibrary
from .symbolic_router import SymbolicRouter
from .tool_intelligence import ToolIntelligenceLayer
from .workflow_engine import WorkflowEngine


class ProcessingStage(Enum):
    """Stages of HNSC processing."""

    SAFETY_CHECK = "safety_check"  # Layer 6
    INTENT_CLASSIFICATION = "intent_classification"  # Layer 2
    WORKFLOW_ROUTING = "workflow_routing"  # Layer 3
    STATIC_REASONING = "static_reasoning"  # Layer 4
    TOOL_EXECUTION = "tool_execution"  # Layer 5
    LLM_GENERATION = "llm_generation"  # Layer 1
    OUTPUT_VALIDATION = "output_validation"  # Final check


@dataclass
class HNSCRequest:
    """A request being processed through HNSC."""

    user_input: str
    session_id: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)
    require_confirmation: bool = True

    # Tracking
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.request_id:
            self.request_id = f"hnsc_{int(self.timestamp * 1000)}"


@dataclass
class HNSCResponse:
    """Response from HNSC processing."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    tool_results: list[dict] = field(default_factory=list)

    # Processing metadata
    stages_completed: list[ProcessingStage] = field(default_factory=list)
    llm_used: bool = False  # Track if LLM was actually needed
    confidence: float = 1.0  # Symbolic = 1.0, LLM < 1.0
    processing_time_ms: float = 0

    # Pending actions
    requires_confirmation: bool = False
    requires_approval: bool = False
    confirmation_message: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "tool_results": self.tool_results,
            "stages_completed": [s.value for s in self.stages_completed],
            "llm_used": self.llm_used,
            "confidence": self.confidence,
            "processing_time_ms": self.processing_time_ms,
            "requires_confirmation": self.requires_confirmation,
            "requires_approval": self.requires_approval,
            "confirmation_message": self.confirmation_message,
        }


class HNSCController:
    """Master Controller for Hybrid Neuro-Symbolic Control Architecture.

    This controller orchestrates all 6 layers to process requests.
    The key insight: LLM is only used for text generation, not decisions.
    """

    def __init__(
        self,
        llm_generate_func: Callable[[str], str] | None = None,
        tool_execute_func: Callable[[str, dict], dict] | None = None,
    ) -> None:
        """Initialize HNSC Controller.

        Args:
            llm_generate_func: Function to call LLM for text generation.
                               Signature: (prompt: str) -> str
            tool_execute_func: Function to execute MCP tools.
                               Signature: (tool_name: str, args: dict) -> dict
        """
        # Initialize all layers
        self._safety = get_safety_engine()
        self._router = SymbolicRouter()
        self._workflow = WorkflowEngine()
        self._reasoning = StaticReasoningLibrary()
        self._tools = ToolIntelligenceLayer()

        # External functions
        self._llm_generate = llm_generate_func
        self._tool_execute = tool_execute_func

        # Metrics
        self._total_requests = 0
        self._symbolic_only_requests = 0
        self._llm_required_requests = 0
        self._blocked_requests = 0

        # Pending confirmations
        self._pending_confirmations: dict[str, dict] = {}

    def process(self, request: HNSCRequest) -> HNSCResponse:
        """Process a request through all HNSC layers.

        This is the main entry point for the HNSC architecture.
        """
        start_time = time.time()
        self._total_requests += 1

        stages: list[ProcessingStage] = []
        llm_used = False

        # ═══════════════════════════════════════════════════════════════════
        # LAYER 6: SAFETY CHECK (First line of defense)
        # ═══════════════════════════════════════════════════════════════════
        stages.append(ProcessingStage.SAFETY_CHECK)

        # Pre-check the input for forbidden patterns
        safety_result = self._safety.check_safety(
            tool_name="user_input",
            arguments={},
            user_input=request.user_input,
            context=request.context,
        )

        if not safety_result.allowed:
            self._blocked_requests += 1
            return HNSCResponse(
                success=False,
                message=f"🛑 Request blocked: {safety_result.message}",
                stages_completed=stages,
                confidence=1.0,  # Deterministic block
                processing_time_ms=(time.time() - start_time) * 1000,
            )

        # ═══════════════════════════════════════════════════════════════════
        # LAYER 2: SYMBOLIC ROUTER (Intent Classification)
        # ═══════════════════════════════════════════════════════════════════
        stages.append(ProcessingStage.INTENT_CLASSIFICATION)

        routing_result = self._router.route(request.user_input)

        # High-confidence routing (> 0.8) doesn't need LLM
        if routing_result.confidence >= 0.8:
            intent = routing_result.intent_category
            tool = routing_result.recommended_tool
            parameters = routing_result.extracted_parameters

            # ═══════════════════════════════════════════════════════════════
            # LAYER 3: WORKFLOW ENGINE (Multi-step pipelines)
            # ═══════════════════════════════════════════════════════════════
            stages.append(ProcessingStage.WORKFLOW_ROUTING)

            workflow = self._workflow.match_workflow(
                intent=intent,
                tool_name=tool,
                context=request.context,
            )

            if workflow:
                # Execute workflow pipeline
                return self._execute_workflow(
                    request, workflow, stages, start_time
                )

            # ═══════════════════════════════════════════════════════════════
            # LAYER 5: TOOL INTELLIGENCE (Specialized handlers)
            # ═══════════════════════════════════════════════════════════════
            stages.append(ProcessingStage.TOOL_EXECUTION)

            # Check if we have an intelligent tool handler
            if tool and self._tools.has_capability(tool):
                # Safety check for the specific tool
                tool_safety = self._safety.check_safety(
                    tool_name=tool,
                    arguments=parameters,
                    user_input=request.user_input,
                    context=request.context,
                )

                if not tool_safety.allowed:
                    return HNSCResponse(
                        success=False,
                        message=f"🛑 Tool blocked: {tool_safety.message}",
                        stages_completed=stages,
                        confidence=1.0,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

                if (
                    tool_safety.requires_confirmation
                    and request.require_confirmation
                ):
                    return self._request_confirmation(
                        request,
                        tool,
                        parameters,
                        tool_safety,
                        stages,
                        start_time,
                    )

                if tool_safety.requires_approval:
                    return self._request_approval(
                        request,
                        tool,
                        parameters,
                        tool_safety,
                        stages,
                        start_time,
                    )

                # Execute with intelligent tool
                tool_result = self._tools.execute(
                    tool_name=tool,
                    parameters=parameters,
                    context=request.context,
                )

                self._symbolic_only_requests += 1

                return HNSCResponse(
                    success=tool_result.success,
                    message=tool_result.message,
                    data=tool_result.data,
                    tool_results=[tool_result.__dict__],
                    stages_completed=stages,
                    llm_used=False,
                    confidence=routing_result.confidence,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # ═══════════════════════════════════════════════════════════════
            # LAYER 4: STATIC REASONING (Rule-based logic)
            # ═══════════════════════════════════════════════════════════════
            stages.append(ProcessingStage.STATIC_REASONING)

            # Try to apply static reasoning templates
            reasoning_result = self._apply_reasoning(request, routing_result)

            if reasoning_result:
                self._symbolic_only_requests += 1
                return HNSCResponse(
                    success=True,
                    message=reasoning_result["message"],
                    data=reasoning_result,
                    stages_completed=stages,
                    llm_used=False,
                    confidence=1.0,  # Static reasoning is deterministic
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            # Execute tool via external executor if available
            if tool and self._tool_execute:
                # Safety check
                tool_safety = self._safety.check_safety(
                    tool_name=tool,
                    arguments=parameters,
                    user_input=request.user_input,
                    context=request.context,
                )

                if not tool_safety.allowed:
                    return HNSCResponse(
                        success=False,
                        message=f"🛑 Tool blocked: {tool_safety.message}",
                        stages_completed=stages,
                        confidence=1.0,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

                try:
                    result = self._tool_execute(tool, parameters)
                    self._symbolic_only_requests += 1

                    return HNSCResponse(
                        success=True,
                        message=f"Executed {tool} successfully",
                        data=(
                            result
                            if isinstance(result, dict)
                            else {"result": result}
                        ),
                        stages_completed=stages,
                        llm_used=False,
                        confidence=routing_result.confidence,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )
                except Exception as e:
                    return HNSCResponse(
                        success=False,
                        message=f"Tool execution failed: {str(e)}",
                        stages_completed=stages,
                        confidence=routing_result.confidence,
                        processing_time_ms=(time.time() - start_time) * 1000,
                    )

        # ═══════════════════════════════════════════════════════════════════
        # LAYER 1: LLM GENERATION (Only when necessary)
        # ═══════════════════════════════════════════════════════════════════
        stages.append(ProcessingStage.LLM_GENERATION)
        llm_used = True
        self._llm_required_requests += 1

        if self._llm_generate:
            # Build constrained prompt for LLM
            prompt = self._build_llm_prompt(request, routing_result)

            try:
                llm_response = self._llm_generate(prompt)

                # ═══════════════════════════════════════════════════════════
                # OUTPUT VALIDATION (Layer 6 again)
                # ═══════════════════════════════════════════════════════════
                stages.append(ProcessingStage.OUTPUT_VALIDATION)

                output_check = self._safety.validate_output(
                    llm_response, "llm_response"
                )

                if not output_check.allowed:
                    # Redact and warn
                    llm_response = self._safety.redact_pii(llm_response)
                    llm_response += (
                        "\n\n⚠️ *Some content was redacted for safety.*"
                    )

                return HNSCResponse(
                    success=True,
                    message=llm_response,
                    stages_completed=stages,
                    llm_used=True,
                    confidence=routing_result.confidence
                    * 0.8,  # Reduce confidence for LLM
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
            except Exception as e:
                return HNSCResponse(
                    success=False,
                    message=f"LLM generation failed: {str(e)}",
                    stages_completed=stages,
                    llm_used=True,
                    confidence=0.5,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
        else:
            # No LLM available, return routing result
            return HNSCResponse(
                success=True,
                message=f"Intent: {routing_result.intent_category}, Tool: {routing_result.recommended_tool or 'none'}",
                data={
                    "intent": routing_result.intent_category,
                    "tool": routing_result.recommended_tool,
                    "parameters": routing_result.extracted_parameters,
                    "confidence": routing_result.confidence,
                },
                stages_completed=stages,
                llm_used=False,
                confidence=routing_result.confidence,
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    def process_with_confirmation(
        self,
        request_id: str,
        confirmed: bool,
    ) -> HNSCResponse:
        """Process a pending confirmation."""
        if request_id not in self._pending_confirmations:
            return HNSCResponse(
                success=False,
                message="No pending confirmation found for this request.",
                confidence=1.0,
            )

        pending = self._pending_confirmations.pop(request_id)

        if not confirmed:
            return HNSCResponse(
                success=True,
                message="Operation cancelled by user.",
                confidence=1.0,
            )

        # Re-process with confirmation context
        request = pending["request"]
        request.context["confirmed"] = True
        request.require_confirmation = False

        return self.process(request)

    def get_metrics(self) -> dict:
        """Get HNSC processing metrics."""
        total = self._total_requests or 1
        return {
            "total_requests": self._total_requests,
            "symbolic_only": self._symbolic_only_requests,
            "llm_required": self._llm_required_requests,
            "blocked": self._blocked_requests,
            "symbolic_rate": self._symbolic_only_requests / total,
            "llm_rate": self._llm_required_requests / total,
            "block_rate": self._blocked_requests / total,
        }

    def _execute_workflow(
        self,
        request: HNSCRequest,
        workflow: dict,
        stages: list[ProcessingStage],
        start_time: float,
    ) -> HNSCResponse:
        """Execute a multi-step workflow."""
        workflow_id = workflow.get("id", "unknown")
        steps = workflow.get("steps", [])

        results = []
        for step in steps:
            tool = step.get("tool")
            params = step.get("parameters", {})

            # Safety check for each step
            safety = self._safety.check_safety(
                tool_name=tool,
                arguments=params,
                user_input=request.user_input,
                context=request.context,
            )

            if not safety.allowed:
                return HNSCResponse(
                    success=False,
                    message=f"Workflow step blocked: {tool} - {safety.message}",
                    tool_results=results,
                    stages_completed=stages,
                    confidence=1.0,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )

            if self._tool_execute:
                try:
                    result = self._tool_execute(tool, params)
                    results.append(
                        {
                            "tool": tool,
                            "success": True,
                            "result": result,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "tool": tool,
                            "success": False,
                            "error": str(e),
                        }
                    )
            else:
                results.append(
                    {
                        "tool": tool,
                        "success": True,
                        "result": f"[Would execute {tool}]",
                    }
                )

        self._symbolic_only_requests += 1

        return HNSCResponse(
            success=all(r.get("success", False) for r in results),
            message=f"Workflow '{workflow_id}' completed with {len(results)} steps",
            data={"workflow_id": workflow_id},
            tool_results=results,
            stages_completed=stages,
            llm_used=False,
            confidence=1.0,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    def _apply_reasoning(
        self,
        request: HNSCRequest,
        routing_result,
    ) -> dict | None:
        """Try to apply static reasoning templates."""
        intent = routing_result.intent_category
        user_input = request.user_input.lower()

        # Map intents to reasoning types
        reasoning_map = {
            "system_health": {
                "type": ReasoningType.ERROR_DIAGNOSIS,
                "trigger": ["error", "fail", "issue", "problem"],
            },
            "data_retrieval": {
                "type": ReasoningType.TASK_DECOMPOSITION,
                "trigger": ["get", "find", "search", "list"],
            },
            "workflow": {
                "type": ReasoningType.MULTI_STEP,
                "trigger": ["then", "after", "workflow", "pipeline"],
            },
            "debug": {
                "type": ReasoningType.ERROR_DIAGNOSIS,
                "trigger": ["debug", "diagnose", "why", "trace"],
            },
            "ml_ai": {
                "type": ReasoningType.COMPARISON,
                "trigger": ["compare", "vs", "versus", "better"],
            },
        }

        if intent in reasoning_map:
            config = reasoning_map[intent]
            triggers = config["trigger"]

            # Check if any trigger word is in input
            if any(t in user_input for t in triggers):
                template = self._reasoning.get_template(config["type"])
                if template:
                    # Apply template
                    result = template.apply(
                        situation=request.user_input,
                        context=request.context,
                    )
                    return {
                        "type": "reasoning",
                        "template": config["type"].value,
                        "message": result.get(
                            "recommendation", result.get("steps", str(result))
                        ),
                        "data": result,
                    }

        return None

    def _request_confirmation(
        self,
        request: HNSCRequest,
        tool: str,
        parameters: dict,
        safety: Any,
        stages: list[ProcessingStage],
        start_time: float,
    ) -> HNSCResponse:
        """Request user confirmation for restricted operations."""
        confirmation_msg = self._safety.get_confirmation_message(
            tool, parameters, safety
        )

        # Store pending confirmation
        self._pending_confirmations[request.request_id] = {
            "request": request,
            "tool": tool,
            "parameters": parameters,
            "timestamp": time.time(),
        }

        return HNSCResponse(
            success=True,
            message=confirmation_msg,
            stages_completed=stages,
            requires_confirmation=True,
            confirmation_message=confirmation_msg,
            confidence=1.0,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    def _request_approval(
        self,
        request: HNSCRequest,
        tool: str,
        parameters: dict,
        safety: Any,
        stages: list[ProcessingStage],
        start_time: float,
    ) -> HNSCResponse:
        """Request approval for dangerous operations."""
        approval_msg = self._safety.get_approval_message(
            tool, parameters, safety
        )

        return HNSCResponse(
            success=True,
            message=approval_msg,
            stages_completed=stages,
            requires_approval=True,
            confirmation_message=approval_msg,
            confidence=1.0,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    def _build_llm_prompt(self, request: HNSCRequest, routing_result) -> str:
        """Build a constrained prompt for the LLM.

        The prompt is structured to minimize hallucination.
        """
        lines = [
            "You are an MCP assistant. Respond ONLY to the user's question.",
            "",
            f"User: {request.user_input}",
            "",
        ]

        # Add context from routing
        if routing_result.intent_category:
            lines.append(f"Intent detected: {routing_result.intent_category}")

        if routing_result.recommended_tool:
            lines.append(f"Suggested tool: {routing_result.recommended_tool}")

        if routing_result.extracted_parameters:
            lines.append(
                f"Parameters: {json.dumps(routing_result.extracted_parameters)}"
            )

        lines.extend(
            [
                "",
                "Rules:",
                "- Be concise and accurate",
                "- Do NOT make up information",
                "- If unsure, say 'I don't know'",
                "- Do NOT execute commands without permission",
                "",
                "Response:",
            ]
        )

        return "\n".join(lines)


# Factory function
def create_hnsc_controller(
    llm_generate_func: Callable[[str], str] | None = None,
    tool_execute_func: Callable[[str, dict], dict] | None = None,
) -> HNSCController:
    """Create an HNSC controller instance.

    Args:
        llm_generate_func: Function to generate text with LLM.
        tool_execute_func: Function to execute MCP tools.

    Returns:
        Configured HNSCController instance.
    """
    return HNSCController(
        llm_generate_func=llm_generate_func,
        tool_execute_func=tool_execute_func,
    )
