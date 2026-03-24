from __future__ import annotations

import asyncio
from typing import Any

from .config import AppConfig
from .task_runner import AsyncTaskRunner
from .utils import utc_timestamp


class Ark95xOmniOrchestrator:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.task_runner = AsyncTaskRunner(retries=3, backoff_seconds=0.25)

    async def _route_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_type = payload.get("type", "generic")
        provider = self._pick_provider(task_type)
        return {
            "task_id": payload.get("task_id", "task-local"),
            "task_type": task_type,
            "provider": provider,
            "status": "routed",
            "timestamp": utc_timestamp(),
        }

    def _pick_provider(self, task_type: str) -> str:
        configured = self.config.configured_providers
        if not configured:
            return "local-fallback"
        if task_type in {"analysis", "reasoning"} and "anthropic" in configured:
            return "anthropic"
        if task_type in {"research", "search"} and "perplexity" in configured:
            return "perplexity"
        if "openai" in configured:
            return "openai"
        return configured[0]

    async def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.task_runner.run("omni_dispatch", self._route_task, payload)
        return {
            "success": result.success,
            "attempts": result.attempts,
            "error": result.error,
            "data": result.result,
        }

    async def handle_webhook(self, payload: dict[str, Any], signature: str = "") -> dict[str, Any]:
        if self.config.omni_webhook_secret and signature != self.config.omni_webhook_secret:
            return {"accepted": False, "reason": "invalid_signature"}

        routed = await self.dispatch(payload)
        return {
            "accepted": routed.get("success", False),
            "webhook_url_configured": bool(self.config.omni_webhook_ingest_url),
            "route": routed,
        }

    def dispatch_sync(self, payload: dict[str, Any]) -> dict[str, Any]:
        return asyncio.run(self.dispatch(payload))
