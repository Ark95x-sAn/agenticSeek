from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from .config import AppConfig
from .task_runner import AsyncTaskRunner
from .utils import utc_timestamp


class CometBridge:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        schema_path = Path(__file__).with_name("comet_tasks.json")
        with schema_path.open("r", encoding="utf-8") as fp:
            return json.load(fp)

    def _validate_task(self, task: dict[str, Any]) -> None:
        required = self._schema.get("required", [])
        for field in required:
            if field not in task:
                raise ValueError(f"Missing required field: {field}")

        action_types = set(self._schema["properties"]["action_type"].get("enum", []))
        priorities = set(self._schema["properties"]["priority"].get("enum", []))
        statuses = set(self._schema["properties"]["status"].get("enum", []))

        if task.get("action_type") not in action_types:
            raise ValueError("Invalid action_type")
        if task.get("priority") not in priorities:
            raise ValueError("Invalid priority")
        if task.get("status") not in statuses:
            raise ValueError("Invalid status")
        if not isinstance(task.get("payload"), dict):
            raise ValueError("payload must be an object")

    def dispatch_to_comet(
        self,
        action_type: str,
        title: str,
        payload: dict[str, Any],
        priority: str = "normal",
    ) -> dict[str, Any]:
        task_payload = {
            "id": payload.get("id", f"comet-{utc_timestamp()}"),
            "action_type": action_type,
            "title": title,
            "payload": payload,
            "priority": priority,
            "status": "queued",
            "created_at": utc_timestamp(),
            "completed_at": None,
        }
        self._validate_task(task_payload)
        return task_payload

    def receive_from_comet(self, response_payload: dict[str, Any], signature: str) -> dict[str, Any]:
        secret = getattr(self.config, "comet_webhook_secret", "") or os.getenv("COMET_WEBHOOK_SECRET", "")
        if secret and signature != secret:
            return {"accepted": False, "reason": "invalid_signature"}

        return {
            "accepted": True,
            "ingested_at": utc_timestamp(),
            "signature_valid": True,
            "response": response_payload,
        }

    def get_bridge_config(self) -> dict[str, Any]:
        webhook_url = getattr(self.config, "comet_webhook_url", "") or os.getenv("COMET_WEBHOOK_URL", "")
        secret = getattr(self.config, "comet_webhook_secret", "") or os.getenv("COMET_WEBHOOK_SECRET", "")
        return {
            "webhook_url": webhook_url,
            "webhook_secret_configured": bool(secret),
            "supported_actions": self._schema.get("properties", {}).get("action_type", {}).get("enum", []),
            "supported_priorities": self._schema.get("properties", {}).get("priority", {}).get("enum", []),
        }


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
