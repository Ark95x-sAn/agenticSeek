"""
Comet / Perplexity AI Browser Client — Integration Points #15-18
=================================================================
Comet is Perplexity AI's browser — a search-augmented AI browser.
This client bridges Comet's search/answer API and browser automation
into the hybrid engine for real-time web-grounded reasoning.

Integration Points:
  #15 — Comet/Perplexity search API for web-grounded answers
  #16 — Comet browser automation bridge (CDP / WebDriver)
  #17 — Perplexity Pro API passthrough for deep research tasks
  #18 — Comet result injection into hybrid engine context window
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

logger = logging.getLogger("hybrid_engine.comet")


@dataclass
class CometConfig:
    perplexity_api_url: str = "https://api.perplexity.ai"
    comet_local_url: str = "http://localhost:9090"  # Comet browser local API
    api_key: str = ""
    search_model: str = "llama-3.1-sonar-large-128k-online"
    deep_research_model: str = "llama-3.1-sonar-huge-128k-online"
    timeout: int = 60
    max_search_results: int = 10


class CometPerplexityClient:
    """
    Integration Points #15-18: Comet/Perplexity browser bridge.
    Handles search, browser automation, deep research, and context injection.
    """

    def __init__(self, config: Optional[CometConfig] = None):
        self.config = config or CometConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._context_buffer: List[Dict[str, Any]] = []
        self.name = "comet_perplexity"
        self.capabilities = ["web_search", "deep_research", "browser", "real_time"]

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

    # ── Integration Point #15: Perplexity search API ──────────────────────────
    async def search(self, query: str, focus: str = "internet") -> Dict[str, Any]:
        """
        Query Perplexity's online search model for web-grounded answers.
        Results are injected into the hybrid engine context window.
        """
        session = await self._get_session()
        payload = {
            "model": self.config.search_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Be precise and concise. Cite sources.",
                },
                {"role": "user", "content": query},
            ],
            "max_tokens": 1024,
            "search_domain_filter": [],
            "return_images": False,
            "return_related_questions": True,
            "search_recency_filter": "month",
        }
        try:
            async with session.post(
                f"{self.config.perplexity_api_url}/chat/completions", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    answer = data["choices"][0]["message"]["content"]
                    citations = data.get("citations", [])
                    result = {
                        "status": "ok",
                        "source": "perplexity",
                        "query": query,
                        "answer": answer,
                        "citations": citations,
                        "related_questions": data.get("related_questions", []),
                    }
                    # Auto-inject into context buffer
                    self._inject_context(result)
                    return result
                else:
                    text = await resp.text()
                    return {"status": "error", "source": "perplexity", "error": text}
        except aiohttp.ClientConnectorError:
            logger.warning("[Comet] Perplexity API unreachable, trying local Comet")
            return await self._local_comet_search(query)
        except Exception as e:
            return {"status": "error", "source": "perplexity", "error": str(e)}

    async def _local_comet_search(self, query: str) -> Dict[str, Any]:
        """Fallback: use locally running Comet browser API."""
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.config.comet_local_url}/search",
                json={"query": query},
            ) as resp:
                data = await resp.json()
                return {"status": "ok", "source": "comet_local", "data": data}
        except Exception as e:
            return {"status": "offline", "source": "comet_local", "error": str(e)}

    # ── Integration Point #16: Browser automation bridge ─────────────────────
    async def browse_url(self, url: str, extract: str = "text") -> Dict[str, Any]:
        """
        Use Comet browser to navigate to a URL and extract content.
        Bridges Comet's CDP interface into the hybrid engine.
        """
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.config.comet_local_url}/browse",
                json={"url": url, "extract": extract},
            ) as resp:
                data = await resp.json()
                result = {
                    "status": "ok",
                    "source": "comet_browser",
                    "url": url,
                    "content": data.get("content", ""),
                    "title": data.get("title", ""),
                    "links": data.get("links", []),
                }
                self._inject_context(result)
                return result
        except Exception as e:
            logger.error(f"[Comet Browser] browse_url failed: {e}")
            return {"status": "error", "source": "comet_browser", "error": str(e)}

    async def screenshot_url(self, url: str) -> bytes:
        """Capture a screenshot of a URL via Comet browser."""
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.config.comet_local_url}/screenshot", json={"url": url}
            ) as resp:
                return await resp.read()
        except Exception as e:
            logger.error(f"[Comet Browser] screenshot failed: {e}")
            return b""

    # ── Integration Point #17: Deep research passthrough ─────────────────────
    async def deep_research(self, topic: str, depth: int = 3) -> AsyncGenerator[str, None]:
        """
        Run a multi-step deep research task via Perplexity Pro.
        Streams intermediate findings into the hybrid engine comms hub.
        """
        session = await self._get_session()
        payload = {
            "model": self.config.deep_research_model,
            "messages": [
                {
                    "role": "system",
                    "content": f"Conduct deep research with {depth} levels of analysis. Be thorough.",
                },
                {"role": "user", "content": f"Deep research: {topic}"},
            ],
            "stream": True,
            "max_tokens": 4096,
        }
        try:
            async with session.post(
                f"{self.config.perplexity_api_url}/chat/completions", json=payload
            ) as resp:
                async for line in resp.content:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        line = line[6:]
                    if line == "[DONE]" or not line:
                        continue
                    try:
                        data = json.loads(line)
                        token = data["choices"][0]["delta"].get("content", "")
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"[Comet deep_research error: {e}]"

    # ── Integration Point #18: Context injection ──────────────────────────────
    def _inject_context(self, result: Dict[str, Any]) -> None:
        """Inject search/browse results into the shared context buffer."""
        self._context_buffer.append(result)
        if len(self._context_buffer) > 20:
            self._context_buffer.pop(0)

    def get_context_window(self) -> List[Dict[str, Any]]:
        """Return the current context buffer for injection into other agents."""
        return list(self._context_buffer)

    def build_context_string(self) -> str:
        """Format context buffer as a string for LLM injection."""
        parts = []
        for item in self._context_buffer[-5:]:  # Last 5 results
            if item.get("source") == "perplexity":
                parts.append(f"[Web Search: {item.get('query', '')}]\n{item.get('answer', '')}")
            elif item.get("source") == "comet_browser":
                parts.append(f"[Browsed: {item.get('url', '')}]\n{item.get('content', '')[:500]}")
        return "\n\n---\n\n".join(parts)

    def clear_context(self) -> None:
        self._context_buffer.clear()

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.comet_local_url}/health") as resp:
                return resp.status == 200
        except Exception:
            # Try Perplexity API
            try:
                session = await self._get_session()
                async with session.get(f"{self.config.perplexity_api_url}/models") as resp:
                    return resp.status in (200, 401)  # 401 = API key needed but reachable
            except Exception:
                return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
