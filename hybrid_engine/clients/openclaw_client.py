"""
OpenClaw Client — Integration Point #1-5
=========================================
OpenClaw is an open-source AI coding assistant / agent framework.
This client wraps its REST API and WebSocket streams for the hybrid engine.

Integration Points:
  #1  — OpenClaw REST API task dispatch
  #2  — OpenClaw WebSocket streaming response bridge
  #3  — OpenClaw tool-call passthrough (shell, file, browser)
  #4  — OpenClaw session state sync with BottleneckBridge
  #5  — OpenClaw → Ollama model handoff for local inference
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

logger = logging.getLogger("hybrid_engine.openclaw")


@dataclass
class OpenClawConfig:
    base_url: str = "http://localhost:8080"
    ws_url: str = "ws://localhost:8080/ws"
    api_key: str = ""
    timeout: int = 60
    model: str = "gpt-4o"
    max_retries: int = 3


class OpenClawClient:
    """
    Integration Point #1: OpenClaw REST API task dispatch
    Integration Point #2: WebSocket streaming bridge
    Integration Point #3: Tool-call passthrough
    Integration Point #4: Session state sync
    Integration Point #5: Ollama model handoff
    """

    def __init__(self, config: Optional[OpenClawConfig] = None):
        self.config = config or OpenClawConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._active_sessions: Dict[str, Any] = {}
        self.name = "openclaw"
        self.capabilities = ["code", "shell", "file", "browser", "reasoning"]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session

    # ── Integration Point #1: REST task dispatch ──────────────────────────────
    async def dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Send a task to OpenClaw and return the result."""
        session = await self._get_session()
        payload = {
            "model": self.config.model,
            "task": task.get("prompt", ""),
            "tools": task.get("tools", ["shell", "file", "browser"]),
            "session_id": task.get("session_id", "default"),
            "stream": False,
        }
        try:
            async with session.post(
                f"{self.config.base_url}/api/task", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"[OpenClaw] Task dispatched: {data.get('task_id')}")
                    return {"status": "ok", "source": "openclaw", "data": data}
                else:
                    text = await resp.text()
                    logger.warning(f"[OpenClaw] HTTP {resp.status}: {text}")
                    return {"status": "error", "source": "openclaw", "error": text}
        except aiohttp.ClientConnectorError:
            logger.error("[OpenClaw] Connection refused — is OpenClaw running?")
            return {"status": "offline", "source": "openclaw", "error": "connection_refused"}

    # ── Integration Point #2: WebSocket streaming ─────────────────────────────
    async def stream_task(self, task: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Stream tokens from OpenClaw via WebSocket."""
        session = await self._get_session()
        ws_url = f"{self.config.ws_url}/stream"
        try:
            async with session.ws_connect(ws_url) as ws:
                await ws.send_json({
                    "model": self.config.model,
                    "prompt": task.get("prompt", ""),
                    "session_id": task.get("session_id", "default"),
                })
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("done"):
                            break
                        yield data.get("token", "")
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error(f"[OpenClaw WS] Error: {ws.exception()}")
                        break
        except Exception as e:
            logger.error(f"[OpenClaw WS] Stream failed: {e}")
            yield f"[OpenClaw stream error: {e}]"

    # ── Integration Point #3: Tool-call passthrough ───────────────────────────
    async def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Pass a tool call through OpenClaw's execution engine."""
        session = await self._get_session()
        payload = {"tool": tool_name, "args": tool_args}
        try:
            async with session.post(
                f"{self.config.base_url}/api/tool", json=payload
            ) as resp:
                data = await resp.json()
                return {"status": "ok", "source": "openclaw", "tool": tool_name, "result": data}
        except Exception as e:
            return {"status": "error", "source": "openclaw", "error": str(e)}

    # ── Integration Point #4: Session state sync ──────────────────────────────
    async def sync_session(self, session_id: str, state: Dict[str, Any]) -> bool:
        """Push session state to OpenClaw for continuity across bridge hops."""
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.config.base_url}/api/session/{session_id}", json=state
            ) as resp:
                ok = resp.status in (200, 204)
                if ok:
                    self._active_sessions[session_id] = state
                return ok
        except Exception as e:
            logger.error(f"[OpenClaw] Session sync failed: {e}")
            return False

    # ── Integration Point #5: Ollama model handoff ────────────────────────────
    async def handoff_to_ollama(self, task: Dict[str, Any], ollama_url: str = "http://localhost:11434") -> Dict[str, Any]:
        """
        When OpenClaw is overloaded or offline, hand the task off to local Ollama.
        This is the primary local-inference fallback in the hybrid stack.
        """
        session = await self._get_session()
        payload = {
            "model": task.get("local_model", "llama3"),
            "prompt": task.get("prompt", ""),
            "stream": False,
        }
        try:
            async with session.post(f"{ollama_url}/api/generate", json=payload) as resp:
                data = await resp.json()
                return {
                    "status": "ok",
                    "source": "ollama_via_openclaw_handoff",
                    "data": data,
                }
        except Exception as e:
            return {"status": "error", "source": "ollama_handoff", "error": str(e)}

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.base_url}/health") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
