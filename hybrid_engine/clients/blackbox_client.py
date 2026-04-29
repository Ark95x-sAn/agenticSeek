"""
BlackBox Desktop Client — Integration Points #6-10
====================================================
BlackBox Desktop is the local AI coding assistant with IDE integration.
This client bridges BlackBox Desktop's local IPC socket and REST API
into the hybrid engine routing layer.

Integration Points:
  #6  — BlackBox Desktop IPC socket bridge (local named pipe / Unix socket)
  #7  — BlackBox code completion passthrough to hybrid router
  #8  — BlackBox context window sync (file tree, open tabs, cursor position)
  #9  — BlackBox → Copilot suggestion arbitration (best-of-N selection)
  #10 — BlackBox telemetry aggregation for routing intelligence
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import struct
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("hybrid_engine.blackbox")


@dataclass
class BlackBoxConfig:
    rest_url: str = "http://localhost:3000"
    ipc_socket: str = "/tmp/blackbox-desktop.sock"
    api_key: str = ""
    timeout: int = 30
    arbitration_threshold: float = 0.75  # confidence threshold for suggestion arbitration


class BlackBoxDesktopClient:
    """
    Integration Points #6-10: BlackBox Desktop bridge.
    Handles IPC, code completion, context sync, Copilot arbitration, telemetry.
    """

    def __init__(self, config: Optional[BlackBoxConfig] = None):
        self.config = config or BlackBoxConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._context_cache: Dict[str, Any] = {}
        self.name = "blackbox_desktop"
        self.capabilities = ["code_completion", "context_sync", "arbitration"]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["X-API-Key"] = self.config.api_key
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session

    # ── Integration Point #6: IPC socket bridge ───────────────────────────────
    async def send_ipc(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to BlackBox Desktop via Unix domain socket (IPC).
        Falls back to REST if socket is unavailable.
        """
        if os.path.exists(self.config.ipc_socket):
            return await self._ipc_send(message)
        else:
            logger.warning("[BlackBox] IPC socket not found, falling back to REST")
            return await self._rest_send(message)

    async def _ipc_send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Low-level Unix socket send/recv."""
        try:
            reader, writer = await asyncio.open_unix_connection(self.config.ipc_socket)
            payload = json.dumps(message).encode()
            # Length-prefixed framing
            writer.write(struct.pack(">I", len(payload)) + payload)
            await writer.drain()
            # Read response
            raw_len = await reader.readexactly(4)
            resp_len = struct.unpack(">I", raw_len)[0]
            raw_resp = await reader.readexactly(resp_len)
            writer.close()
            await writer.wait_closed()
            return {"status": "ok", "source": "blackbox_ipc", "data": json.loads(raw_resp)}
        except Exception as e:
            logger.error(f"[BlackBox IPC] Error: {e}")
            return {"status": "error", "source": "blackbox_ipc", "error": str(e)}

    async def _rest_send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.config.rest_url}/api/message", json=message
            ) as resp:
                data = await resp.json()
                return {"status": "ok", "source": "blackbox_rest", "data": data}
        except Exception as e:
            return {"status": "error", "source": "blackbox_rest", "error": str(e)}

    # ── Integration Point #7: Code completion passthrough ─────────────────────
    async def get_completion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request a code completion from BlackBox Desktop.
        The result is passed to the hybrid router for arbitration.
        """
        session = await self._get_session()
        payload = {
            "file_path": context.get("file_path", ""),
            "language": context.get("language", "python"),
            "prefix": context.get("prefix", ""),
            "suffix": context.get("suffix", ""),
            "cursor_line": context.get("cursor_line", 0),
            "cursor_col": context.get("cursor_col", 0),
        }
        try:
            async with session.post(
                f"{self.config.rest_url}/api/complete", json=payload
            ) as resp:
                data = await resp.json()
                return {
                    "status": "ok",
                    "source": "blackbox_desktop",
                    "completion": data.get("completion", ""),
                    "confidence": data.get("confidence", 0.5),
                }
        except Exception as e:
            return {"status": "error", "source": "blackbox_desktop", "error": str(e)}

    # ── Integration Point #8: Context window sync ─────────────────────────────
    async def sync_context(self, workspace: Dict[str, Any]) -> bool:
        """
        Push IDE context (file tree, open tabs, cursor) to BlackBox Desktop.
        This keeps all agents in the hybrid engine aware of the current workspace.
        """
        session = await self._get_session()
        try:
            async with session.put(
                f"{self.config.rest_url}/api/context", json=workspace
            ) as resp:
                ok = resp.status in (200, 204)
                if ok:
                    self._context_cache = workspace
                    logger.info("[BlackBox] Context synced successfully")
                return ok
        except Exception as e:
            logger.error(f"[BlackBox] Context sync failed: {e}")
            return False

    def get_cached_context(self) -> Dict[str, Any]:
        return self._context_cache

    # ── Integration Point #9: Copilot suggestion arbitration ──────────────────
    async def arbitrate_suggestions(
        self, suggestions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Given N suggestions from different sources (BlackBox, Copilot, Ollama),
        select the best one based on confidence scores and context alignment.
        """
        if not suggestions:
            return {"status": "error", "error": "no_suggestions"}

        # Score each suggestion
        scored = []
        for s in suggestions:
            score = s.get("confidence", 0.5)
            # Boost local sources for privacy
            if s.get("source") in ("ollama", "blackbox_desktop"):
                score *= 1.1
            # Penalize offline sources
            if s.get("status") == "offline":
                score = 0.0
            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]

        if best_score < self.config.arbitration_threshold:
            logger.warning(f"[BlackBox Arbitration] Low confidence: {best_score:.2f}")

        return {
            "status": "ok",
            "source": "arbitration",
            "winner": best,
            "score": best_score,
            "all_scores": [(s, d.get("source")) for s, d in scored],
        }

    # ── Integration Point #10: Telemetry aggregation ──────────────────────────
    async def collect_telemetry(self) -> Dict[str, Any]:
        """
        Pull usage telemetry from BlackBox Desktop for routing intelligence.
        Used by the BottleneckBridge to make smarter routing decisions.
        """
        session = await self._get_session()
        try:
            async with session.get(f"{self.config.rest_url}/api/telemetry") as resp:
                data = await resp.json()
                return {
                    "status": "ok",
                    "source": "blackbox_telemetry",
                    "metrics": {
                        "completions_today": data.get("completions_today", 0),
                        "avg_latency_ms": data.get("avg_latency_ms", 0),
                        "error_rate": data.get("error_rate", 0.0),
                        "active_sessions": data.get("active_sessions", 0),
                    },
                }
        except Exception as e:
            return {"status": "error", "source": "blackbox_telemetry", "error": str(e)}

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.rest_url}/health") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
