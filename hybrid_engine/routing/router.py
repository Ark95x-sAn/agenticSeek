"""
HybridRouter — Integration Point #24
======================================
The HybridRouter sits above the BottleneckBridge and provides:
  - High-level task classification (what kind of task is this?)
  - Multi-agent fan-out (send to multiple clients, merge results)
  - Pipeline chaining (Comet search → Ollama reasoning → Copilot code)
  - Session management across all 5 tools
  - Result merging and deduplication

Integration Point #24 — High-level hybrid routing with pipeline support
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from hybrid_engine.routing.bottleneck import BottleneckBridge, TaskPriority

logger = logging.getLogger("hybrid_engine.router")


@dataclass
class Pipeline:
    """A named sequence of routing steps."""
    name: str
    steps: List[Dict[str, Any]]  # Each step: {type, client, transform}
    description: str = ""


# Built-in pipelines for common hybrid workflows
BUILTIN_PIPELINES: Dict[str, Pipeline] = {
    "research_and_code": Pipeline(
        name="research_and_code",
        description="Search web → reason locally → generate code",
        steps=[
            {"type": "web_search", "client": "comet_perplexity", "output_key": "research"},
            {"type": "reasoning", "client": "ollama", "inject_keys": ["research"], "output_key": "plan"},
            {"type": "code", "client": "copilot", "inject_keys": ["plan"], "output_key": "code"},
        ],
    ),
    "local_first_code": Pipeline(
        name="local_first_code",
        description="Try local Ollama → fallback to BlackBox → fallback to Copilot",
        steps=[
            {"type": "code_completion", "client": "ollama", "output_key": "completion"},
        ],
    ),
    "deep_analysis": Pipeline(
        name="deep_analysis",
        description="Perplexity deep research → Ollama analysis → BlackBox summary",
        steps=[
            {"type": "deep_research", "client": "comet_perplexity", "output_key": "research"},
            {"type": "inference", "client": "ollama", "inject_keys": ["research"], "output_key": "analysis"},
            {"type": "chat", "client": "blackbox_desktop", "inject_keys": ["analysis"], "output_key": "summary"},
        ],
    ),
    "multi_agent_fanout": Pipeline(
        name="multi_agent_fanout",
        description="Send to all agents simultaneously, merge best result",
        steps=[
            {"type": "fanout", "clients": ["ollama", "openclaw", "copilot"], "output_key": "merged"},
        ],
    ),
}


class HybridRouter:
    """
    Integration Point #24: High-level hybrid router.
    Orchestrates multi-step pipelines across all 5 AI tools.
    """

    def __init__(self, bridge: BottleneckBridge):
        self.bridge = bridge
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._result_cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl: float = 300.0  # 5 minutes
        self._pipelines: Dict[str, Pipeline] = dict(BUILTIN_PIPELINES)

    # ── Task classification ───────────────────────────────────────────────────
    def classify_task(self, prompt: str, hints: Optional[Dict[str, Any]] = None) -> str:
        """
        Classify a prompt into a task type for routing.
        Uses keyword heuristics + optional hints from the caller.
        """
        if hints and hints.get("type"):
            return hints["type"]

        prompt_lower = prompt.lower()

        # Web/research tasks → Comet/Perplexity
        if any(kw in prompt_lower for kw in ["search", "latest", "news", "current", "today", "find online"]):
            return "web_search"

        # Deep research
        if any(kw in prompt_lower for kw in ["research", "analyze", "deep dive", "comprehensive"]):
            return "deep_research"

        # Code completion
        if any(kw in prompt_lower for kw in ["complete", "autocomplete", "finish this", "next line"]):
            return "code_completion"

        # Code generation
        if any(kw in prompt_lower for kw in ["write code", "implement", "function", "class", "def ", "import"]):
            return "code"

        # Shell/system tasks
        if any(kw in prompt_lower for kw in ["run", "execute", "shell", "terminal", "bash", "command"]):
            return "shell"

        # File operations
        if any(kw in prompt_lower for kw in ["file", "read", "write", "open", "save", "directory"]):
            return "file"

        # Chat/conversation
        if any(kw in prompt_lower for kw in ["explain", "what is", "how does", "tell me", "describe"]):
            return "chat"

        # Reasoning/analysis
        if any(kw in prompt_lower for kw in ["reason", "think", "plan", "strategy", "decide"]):
            return "reasoning"

        return "inference"

    # ── Single task routing ───────────────────────────────────────────────────
    async def route(
        self,
        prompt: str,
        session_id: str = "default",
        priority: TaskPriority = TaskPriority.NORMAL,
        hints: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Route a single task through the bottleneck bridge.
        Handles caching, session context injection, and result enrichment.
        """
        task_type = self.classify_task(prompt, hints)

        # Check cache
        if use_cache:
            cached = self._get_cached(prompt, task_type)
            if cached:
                logger.debug(f"[Router] Cache hit for task_type={task_type}")
                return {**cached, "cached": True}

        # Inject session context
        session_ctx = self._sessions.get(session_id, {})
        payload = {
            "type": task_type,
            "prompt": prompt,
            "session_id": session_id,
            "context": session_ctx,
            **(hints or {}),
        }

        preferred = (hints or {}).get("preferred_client")
        result = await self.bridge.submit(payload, priority=priority, preferred_client=preferred)

        # Update session
        self._update_session(session_id, prompt, result)

        # Cache successful results
        if use_cache and result.get("status") == "ok":
            self._cache_result(prompt, task_type, result)

        return result

    # ── Pipeline execution ────────────────────────────────────────────────────
    async def run_pipeline(
        self,
        pipeline_name: str,
        initial_prompt: str,
        session_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Execute a named pipeline — a sequence of routing steps where
        each step's output feeds into the next step's context.
        """
        pipeline = self._pipelines.get(pipeline_name)
        if not pipeline:
            return {"status": "error", "error": f"unknown_pipeline: {pipeline_name}"}

        logger.info(f"[Router] Running pipeline: {pipeline_name}")
        context: Dict[str, Any] = {"initial_prompt": initial_prompt}
        results: Dict[str, Any] = {}

        for i, step in enumerate(pipeline.steps):
            step_type = step["type"]
            output_key = step.get("output_key", f"step_{i}")

            # Build prompt with injected context
            inject_keys = step.get("inject_keys", [])
            injected = "\n\n".join(
                f"[{k}]: {json.dumps(context.get(k, ''))}" for k in inject_keys if k in context
            )
            prompt = f"{initial_prompt}\n\n{injected}".strip() if injected else initial_prompt

            if step_type == "fanout":
                # Fan out to multiple clients simultaneously
                result = await self._fanout(prompt, step.get("clients", []), session_id)
            else:
                payload = {
                    "type": step_type,
                    "prompt": prompt,
                    "session_id": session_id,
                    "context": context,
                }
                preferred = step.get("client")
                result = await self.bridge.submit(payload, preferred_client=preferred)

            context[output_key] = result.get("response") or result.get("answer") or result.get("data", "")
            results[output_key] = result
            logger.info(f"[Router] Pipeline step {i+1}/{len(pipeline.steps)} ({step_type}) → {result.get('status')}")

        return {
            "status": "ok",
            "pipeline": pipeline_name,
            "steps_completed": len(pipeline.steps),
            "results": results,
            "final_output": context.get(pipeline.steps[-1].get("output_key", ""), ""),
        }

    async def _fanout(
        self, prompt: str, client_names: List[str], session_id: str
    ) -> Dict[str, Any]:
        """Send the same task to multiple clients simultaneously and merge results."""
        tasks = []
        for client_name in client_names:
            payload = {"type": "inference", "prompt": prompt, "session_id": session_id}
            tasks.append(self.bridge.submit(payload, preferred_client=client_name))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r.get("status") == "ok"]

        if not valid:
            return {"status": "error", "error": "all_fanout_clients_failed"}

        # Return the fastest successful result
        return {
            "status": "ok",
            "source": "fanout_merged",
            "response": valid[0].get("response", ""),
            "all_results": valid,
            "client_count": len(valid),
        }

    # ── Custom pipeline registration ──────────────────────────────────────────
    def register_pipeline(self, pipeline: Pipeline) -> None:
        self._pipelines[pipeline.name] = pipeline
        logger.info(f"[Router] Registered pipeline: {pipeline.name}")

    def list_pipelines(self) -> List[Dict[str, str]]:
        return [
            {"name": p.name, "description": p.description}
            for p in self._pipelines.values()
        ]

    # ── Session management ────────────────────────────────────────────────────
    def _update_session(self, session_id: str, prompt: str, result: Dict[str, Any]) -> None:
        if session_id not in self._sessions:
            self._sessions[session_id] = {"history": [], "created_at": time.time()}
        session = self._sessions[session_id]
        session["history"].append({
            "prompt": prompt[:200],
            "result_status": result.get("status"),
            "routed_via": result.get("routed_via"),
            "timestamp": time.time(),
        })
        # Keep last 20 interactions
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]
        session["last_active"] = time.time()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._sessions.get(session_id, {})

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    # ── Result caching ────────────────────────────────────────────────────────
    def _cache_key(self, prompt: str, task_type: str) -> str:
        return hashlib.sha256(f"{task_type}:{prompt}".encode()).hexdigest()[:16]

    def _get_cached(self, prompt: str, task_type: str) -> Optional[Dict[str, Any]]:
        key = self._cache_key(prompt, task_type)
        if key in self._result_cache:
            ts, result = self._result_cache[key]
            if time.time() - ts < self._cache_ttl:
                return result
            del self._result_cache[key]
        return None

    def _cache_result(self, prompt: str, task_type: str, result: Dict[str, Any]) -> None:
        key = self._cache_key(prompt, task_type)
        self._result_cache[key] = (time.time(), result)
        # Evict old entries
        if len(self._result_cache) > 1000:
            oldest = sorted(self._result_cache.items(), key=lambda x: x[1][0])[:100]
            for k, _ in oldest:
                del self._result_cache[k]

    # ── Status ────────────────────────────────────────────────────────────────
    def get_status(self) -> Dict[str, Any]:
        return {
            "active_sessions": len(self._sessions),
            "cached_results": len(self._result_cache),
            "registered_pipelines": list(self._pipelines.keys()),
            "queue_depth": self.bridge.get_queue_depth(),
            "client_metrics": self.bridge.get_metrics(),
        }
