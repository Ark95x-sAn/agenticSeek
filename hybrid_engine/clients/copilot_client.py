"""
GitHub Copilot / Windows OS Wrapper Client — Integration Points #19-22
=======================================================================
GitHub Copilot provides AI code completion via the LSP protocol and REST API.
This client also implements the Windows OS wrapper overlay that sits on top
of the entire hybrid engine stack.

Integration Points:
  #19 — Copilot LSP (Language Server Protocol) bridge for IDE integration
  #20 — Copilot Chat API passthrough for conversational coding
  #21 — Copilot suggestion ranking and injection into arbitration layer
  #22 — Windows OS wrapper: system tray, hotkeys, overlay UI bridge
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("hybrid_engine.copilot")


@dataclass
class CopilotConfig:
    lsp_port: int = 6009  # Copilot LSP server port
    chat_api_url: str = "https://api.githubcopilot.com"
    github_token: str = ""
    timeout: int = 30
    # Windows overlay settings
    overlay_hotkey: str = "ctrl+shift+space"
    tray_icon_path: str = "assets/hybrid_engine_tray.ico"
    overlay_opacity: float = 0.92


class CopilotClient:
    """
    Integration Points #19-22: GitHub Copilot bridge + Windows OS wrapper.
    """

    def __init__(self, config: Optional[CopilotConfig] = None):
        self.config = config or CopilotConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._lsp_reader: Optional[asyncio.StreamReader] = None
        self._lsp_writer: Optional[asyncio.StreamWriter] = None
        self._lsp_request_id: int = 0
        self._is_windows = platform.system() == "Windows"
        self.name = "copilot"
        self.capabilities = ["code_completion", "chat", "lsp", "os_wrapper"]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Content-Type": "application/json",
                "Editor-Version": "Neovim/0.9.0",
                "Editor-Plugin-Version": "copilot.vim/1.16.0",
                "User-Agent": "GithubCopilot/1.155.0",
            }
            if self.config.github_token:
                headers["Authorization"] = f"token {self.config.github_token}"
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            )
        return self._session

    # ── Integration Point #19: LSP bridge ────────────────────────────────────
    async def connect_lsp(self) -> bool:
        """Connect to the Copilot Language Server Protocol server."""
        try:
            self._lsp_reader, self._lsp_writer = await asyncio.open_connection(
                "127.0.0.1", self.config.lsp_port
            )
            # Send LSP initialize request
            await self._lsp_send({
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "processId": os.getpid(),
                    "clientInfo": {"name": "hybrid-engine", "version": "1.0.0"},
                    "capabilities": {},
                    "rootUri": None,
                },
            })
            logger.info("[Copilot LSP] Connected")
            return True
        except Exception as e:
            logger.warning(f"[Copilot LSP] Connection failed: {e}")
            return False

    def _next_id(self) -> int:
        self._lsp_request_id += 1
        return self._lsp_request_id

    async def _lsp_send(self, message: Dict[str, Any]) -> None:
        """Send an LSP message with Content-Length framing."""
        if not self._lsp_writer:
            return
        body = json.dumps(message).encode()
        header = f"Content-Length: {len(body)}\r\n\r\n".encode()
        self._lsp_writer.write(header + body)
        await self._lsp_writer.drain()

    async def _lsp_recv(self) -> Optional[Dict[str, Any]]:
        """Read one LSP message from the server."""
        if not self._lsp_reader:
            return None
        try:
            header = b""
            while b"\r\n\r\n" not in header:
                header += await self._lsp_reader.read(1)
            content_length = int(
                [l for l in header.decode().split("\r\n") if "Content-Length" in l][0]
                .split(": ")[1]
            )
            body = await self._lsp_reader.readexactly(content_length)
            return json.loads(body)
        except Exception as e:
            logger.error(f"[Copilot LSP] recv error: {e}")
            return None

    async def get_lsp_completion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Request code completion via LSP protocol."""
        if not self._lsp_writer:
            connected = await self.connect_lsp()
            if not connected:
                return {"status": "offline", "source": "copilot_lsp"}

        req_id = self._next_id()
        await self._lsp_send({
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "getCompletions",
            "params": {
                "doc": {
                    "source": context.get("source", ""),
                    "tabSize": 4,
                    "indentSize": 4,
                    "insertSpaces": True,
                    "path": context.get("file_path", ""),
                    "uri": f"file://{context.get('file_path', '')}",
                    "relativePath": context.get("file_path", ""),
                    "languageId": context.get("language", "python"),
                    "position": {
                        "line": context.get("cursor_line", 0),
                        "character": context.get("cursor_col", 0),
                    },
                }
            },
        })
        response = await self._lsp_recv()
        if response and "result" in response:
            completions = response["result"].get("completions", [])
            return {
                "status": "ok",
                "source": "copilot_lsp",
                "completions": completions,
                "confidence": 0.85 if completions else 0.0,
            }
        return {"status": "error", "source": "copilot_lsp", "error": "no_result"}

    # ── Integration Point #20: Copilot Chat API ───────────────────────────────
    async def chat(self, messages: List[Dict[str, str]], context_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Send a conversational coding request to Copilot Chat.
        Optionally inject file context for workspace-aware responses.
        """
        session = await self._get_session()
        payload = {
            "messages": messages,
            "model": "gpt-4o",
            "stream": False,
            "n": 1,
            "top_p": 1,
            "temperature": 0.1,
        }
        if context_files:
            # Inject file contents as system context
            file_context = "\n\n".join(
                f"// File: {f}\n{self._read_file_safe(f)}" for f in context_files
            )
            payload["messages"].insert(0, {
                "role": "system",
                "content": f"Workspace context:\n{file_context}",
            })
        try:
            async with session.post(
                f"{self.config.chat_api_url}/chat/completions", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "ok",
                        "source": "copilot_chat",
                        "response": data["choices"][0]["message"]["content"],
                        "confidence": 0.88,
                    }
                else:
                    text = await resp.text()
                    return {"status": "error", "source": "copilot_chat", "error": text}
        except Exception as e:
            return {"status": "error", "source": "copilot_chat", "error": str(e)}

    def _read_file_safe(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(4000)  # Limit to 4KB per file
        except Exception:
            return f"[Could not read {path}]"

    # ── Integration Point #21: Suggestion ranking ─────────────────────────────
    async def rank_suggestions(
        self, suggestions: List[Dict[str, Any]], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Rank suggestions from all sources (Copilot, BlackBox, Ollama) using
        Copilot's confidence scores and context alignment heuristics.
        """
        ranked = []
        for s in suggestions:
            score = s.get("confidence", 0.5)
            # Boost Copilot's own suggestions slightly
            if s.get("source") == "copilot_lsp":
                score *= 1.05
            # Penalize offline sources
            if s.get("status") in ("offline", "error"):
                score = 0.0
            # Context language match bonus
            if s.get("language") == context.get("language"):
                score *= 1.02
            ranked.append({**s, "final_score": min(score, 1.0)})

        ranked.sort(key=lambda x: x["final_score"], reverse=True)
        return ranked

    # ── Integration Point #22: Windows OS wrapper ─────────────────────────────
    def launch_windows_overlay(self) -> bool:
        """
        Launch the Windows OS wrapper overlay for the hybrid engine.
        Creates a system tray icon and registers global hotkeys.
        Only runs on Windows; on Linux/Mac, logs a compatibility notice.
        """
        if not self._is_windows:
            logger.info("[Copilot OS Wrapper] Windows overlay skipped (not Windows)")
            return False

        try:
            # Launch the overlay subprocess (see deployment/windows_overlay.py)
            overlay_script = os.path.join(
                os.path.dirname(__file__), "..", "deployment", "windows_overlay.py"
            )
            subprocess.Popen(
                ["pythonw", overlay_script,
                 "--hotkey", self.config.overlay_hotkey,
                 "--opacity", str(self.config.overlay_opacity)],
                creationflags=subprocess.DETACHED_PROCESS,
            )
            logger.info(f"[Copilot OS Wrapper] Overlay launched (hotkey: {self.config.overlay_hotkey})")
            return True
        except Exception as e:
            logger.error(f"[Copilot OS Wrapper] Launch failed: {e}")
            return False

    def get_os_info(self) -> Dict[str, Any]:
        return {
            "platform": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "is_windows": self._is_windows,
            "overlay_supported": self._is_windows,
        }

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.chat_api_url}/models") as resp:
                return resp.status in (200, 401)
        except Exception:
            return False

    async def close(self):
        if self._lsp_writer:
            self._lsp_writer.close()
        if self._session and not self._session.closed:
            await self._session.close()
