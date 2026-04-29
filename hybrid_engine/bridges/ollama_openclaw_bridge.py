"""
Ollama ↔ OpenClaw Bridge
=========================
Translates between Ollama's generate/chat API format and
OpenClaw's task dispatch format. Enables seamless handoff
between local inference (Ollama) and agentic execution (OpenClaw).

Use case: Ollama reasons about a task → OpenClaw executes it (shell/file/browser).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid_engine.bridge.ollama_openclaw")


class OllamaOpenClawBridge:
    """
    Bidirectional bridge between Ollama and OpenClaw.
    Handles format translation and capability routing.
    """

    def __init__(self, ollama_client: Any, openclaw_client: Any):
        self.ollama = ollama_client
        self.openclaw = openclaw_client

    async def reason_then_execute(
        self, task_description: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 1: Use Ollama to reason about the task and produce a plan.
        Step 2: Pass the plan to OpenClaw for execution.
        """
        # Step 1: Ollama reasoning
        reasoning_prompt = (
            f"You are a task planner. Given this task, produce a JSON execution plan "
            f"with steps for an AI agent to follow.\n\nTask: {task_description}\n\n"
            f"Respond with JSON only: {{\"steps\": [{{\"action\": \"...\", \"args\": {{}}}}]}}"
        )
        reasoning_result = await self.ollama.generate(
            reasoning_prompt, model=model, temperature=0.1
        )

        if reasoning_result.get("status") != "ok":
            return {"status": "error", "stage": "reasoning", "error": reasoning_result.get("error")}

        plan_text = reasoning_result.get("response", "")
        logger.info(f"[OllamaOpenClaw] Reasoning complete, plan length: {len(plan_text)}")

        # Step 2: OpenClaw execution
        execution_result = await self.openclaw.dispatch_task({
            "prompt": f"Execute this plan:\n{plan_text}\n\nOriginal task: {task_description}",
            "tools": ["shell", "file", "browser"],
            "session_id": "ollama_openclaw_bridge",
        })

        return {
            "status": "ok",
            "bridge": "ollama_openclaw",
            "reasoning": plan_text,
            "execution": execution_result,
        }

    async def execute_then_summarize(
        self, task: Dict[str, Any], model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 1: OpenClaw executes the task.
        Step 2: Ollama summarizes/interprets the result.
        """
        exec_result = await self.openclaw.dispatch_task(task)

        if exec_result.get("status") not in ("ok", "success"):
            return exec_result

        raw_output = str(exec_result.get("data", ""))
        summary_prompt = (
            f"Summarize this execution result concisely:\n\n{raw_output[:2000]}"
        )
        summary = await self.ollama.generate(summary_prompt, model=model)

        return {
            "status": "ok",
            "bridge": "openclaw_ollama",
            "execution": exec_result,
            "summary": summary.get("response", ""),
        }

    async def local_tool_call(
        self, tool_name: str, tool_args: Dict[str, Any], model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use Ollama to validate/enhance tool args, then execute via OpenClaw.
        """
        validation_prompt = (
            f"Validate and enhance these tool arguments for tool '{tool_name}':\n"
            f"{tool_args}\n\nReturn improved JSON args only."
        )
        validation = await self.ollama.generate(validation_prompt, model=model, temperature=0.0)
        enhanced_args = tool_args  # Fallback to original if parsing fails

        try:
            import json
            response_text = validation.get("response", "")
            # Extract JSON from response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                enhanced_args = json.loads(response_text[start:end])
        except Exception:
            pass

        return await self.openclaw.execute_tool(tool_name, enhanced_args)
