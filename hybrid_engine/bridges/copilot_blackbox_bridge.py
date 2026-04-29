"""
Copilot ↔ BlackBox Desktop Bridge
====================================
Arbitrates code completions between GitHub Copilot and BlackBox Desktop.
Implements best-of-N selection, context sharing, and suggestion merging.

Use case: Both Copilot and BlackBox generate completions → bridge picks the best.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid_engine.bridge.copilot_blackbox")


class CopilotBlackBoxBridge:
    """
    Bidirectional bridge between Copilot and BlackBox Desktop.
    Handles completion arbitration and context synchronization.
    """

    def __init__(self, copilot_client: Any, blackbox_client: Any):
        self.copilot = copilot_client
        self.blackbox = blackbox_client

    async def get_best_completion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request completions from both Copilot and BlackBox simultaneously.
        Return the best one based on confidence and context alignment.
        """
        # Fan out to both simultaneously
        copilot_task = asyncio.create_task(self.copilot.get_lsp_completion(context))
        blackbox_task = asyncio.create_task(self.blackbox.get_completion(context))

        results = await asyncio.gather(copilot_task, blackbox_task, return_exceptions=True)

        suggestions = []
        for r in results:
            if isinstance(r, dict) and r.get("status") == "ok":
                suggestions.append(r)

        if not suggestions:
            return {"status": "error", "bridge": "copilot_blackbox", "error": "no_completions"}

        # Use BlackBox arbitration
        best = await self.blackbox.arbitrate_suggestions(suggestions)
        return {
            "status": "ok",
            "bridge": "copilot_blackbox",
            "best": best.get("winner"),
            "score": best.get("score"),
            "all_suggestions": suggestions,
        }

    async def sync_workspace_context(self, workspace: Dict[str, Any]) -> Dict[str, bool]:
        """Push workspace context to both tools simultaneously."""
        bb_task = asyncio.create_task(self.blackbox.sync_context(workspace))
        # Copilot context is set per-request via file injection
        bb_ok = await bb_task
        return {"blackbox": bb_ok, "copilot": True}

    async def ranked_chat(
        self, messages: List[Dict[str, str]], context_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get chat responses from both tools and return the highest-ranked one.
        """
        copilot_task = asyncio.create_task(
            self.copilot.chat(messages, context_files=context_files)
        )
        blackbox_task = asyncio.create_task(
            self.blackbox.send_ipc({"type": "chat", "messages": messages})
        )

        results = await asyncio.gather(copilot_task, blackbox_task, return_exceptions=True)
        valid = [r for r in results if isinstance(r, dict) and r.get("status") == "ok"]

        if not valid:
            return {"status": "error", "bridge": "copilot_blackbox", "error": "no_chat_response"}

        ranked = await self.copilot.rank_suggestions(valid, context={"language": "python"})
        return {
            "status": "ok",
            "bridge": "copilot_blackbox",
            "response": ranked[0].get("response", "") if ranked else "",
            "ranked": ranked,
        }
