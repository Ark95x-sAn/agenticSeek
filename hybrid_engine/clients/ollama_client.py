"""
Ollama Client — Integration Points #11-14
==========================================
Ollama runs local LLMs (Llama3, Mistral, CodeLlama, Phi-3, etc.)
This client provides the local inference backbone of the hybrid engine.

Integration Points:
  #11 — Ollama local model inference (primary local backend)
  #12 — Ollama model pull/management via hybrid engine CLI
  #13 — Ollama streaming token bridge to comms hub
  #14 — Ollama embeddings for semantic routing decisions
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

logger = logging.getLogger("hybrid_engine.ollama")

# Default model priority list for the hybrid engine
DEFAULT_MODEL_PRIORITY = [
    "llama3:8b",
    "codellama:13b",
    "mistral:7b",
    "phi3:mini",
    "deepseek-coder:6.7b",
]


@dataclass
class OllamaConfig:
    base_url: str = "http://localhost:11434"
    default_model: str = "llama3:8b"
    timeout: int = 120
    context_window: int = 8192
    temperature: float = 0.2
    model_priority: List[str] = field(default_factory=lambda: DEFAULT_MODEL_PRIORITY)


class OllamaClient:
    """
    Integration Points #11-14: Ollama local inference bridge.
    Handles inference, model management, streaming, and embeddings.
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._available_models: List[str] = []
        self.name = "ollama"
        self.capabilities = ["inference", "embeddings", "code", "reasoning"]

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        return self._session

    # ── Integration Point #11: Local model inference ──────────────────────────
    async def generate(self, prompt: str, model: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Run local inference via Ollama. Primary local backend for the hybrid engine."""
        session = await self._get_session()
        model = model or self.config.default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_ctx": kwargs.get("context_window", self.config.context_window),
            },
        }
        if kwargs.get("system"):
            payload["system"] = kwargs["system"]

        try:
            async with session.post(
                f"{self.config.base_url}/api/generate", json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "status": "ok",
                        "source": "ollama",
                        "model": model,
                        "response": data.get("response", ""),
                        "eval_count": data.get("eval_count", 0),
                        "eval_duration_ns": data.get("eval_duration", 0),
                    }
                else:
                    text = await resp.text()
                    return {"status": "error", "source": "ollama", "error": text}
        except aiohttp.ClientConnectorError:
            logger.error("[Ollama] Connection refused — is Ollama running?")
            return {"status": "offline", "source": "ollama", "error": "connection_refused"}
        except Exception as e:
            return {"status": "error", "source": "ollama", "error": str(e)}

    async def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Chat-format inference (OpenAI-compatible messages list)."""
        session = await self._get_session()
        model = model or self.config.default_model
        payload = {"model": model, "messages": messages, "stream": False}
        try:
            async with session.post(
                f"{self.config.base_url}/api/chat", json=payload
            ) as resp:
                data = await resp.json()
                return {
                    "status": "ok",
                    "source": "ollama",
                    "model": model,
                    "response": data.get("message", {}).get("content", ""),
                }
        except Exception as e:
            return {"status": "error", "source": "ollama", "error": str(e)}

    # ── Integration Point #12: Model pull/management ──────────────────────────
    async def pull_model(self, model_name: str) -> AsyncGenerator[str, None]:
        """Pull a model from Ollama registry, streaming progress updates."""
        session = await self._get_session()
        payload = {"name": model_name, "stream": True}
        try:
            async with session.post(
                f"{self.config.base_url}/api/pull", json=payload
            ) as resp:
                async for line in resp.content:
                    if line.strip():
                        data = json.loads(line)
                        status = data.get("status", "")
                        completed = data.get("completed", 0)
                        total = data.get("total", 0)
                        if total > 0:
                            pct = (completed / total) * 100
                            yield f"[Ollama Pull] {model_name}: {status} {pct:.1f}%"
                        else:
                            yield f"[Ollama Pull] {model_name}: {status}"
        except Exception as e:
            yield f"[Ollama Pull Error] {e}"

    async def list_models(self) -> List[str]:
        """List all locally available Ollama models."""
        session = await self._get_session()
        try:
            async with session.get(f"{self.config.base_url}/api/tags") as resp:
                data = await resp.json()
                models = [m["name"] for m in data.get("models", [])]
                self._available_models = models
                return models
        except Exception as e:
            logger.error(f"[Ollama] list_models failed: {e}")
            return []

    async def get_best_available_model(self) -> str:
        """Return the highest-priority model that is locally available."""
        available = await self.list_models()
        for preferred in self.config.model_priority:
            if preferred in available:
                return preferred
        return available[0] if available else self.config.default_model

    async def delete_model(self, model_name: str) -> bool:
        session = await self._get_session()
        try:
            async with session.delete(
                f"{self.config.base_url}/api/delete", json={"name": model_name}
            ) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    # ── Integration Point #13: Streaming token bridge ─────────────────────────
    async def stream_generate(self, prompt: str, model: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama directly into the comms hub."""
        session = await self._get_session()
        model = model or self.config.default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": self.config.temperature},
        }
        try:
            async with session.post(
                f"{self.config.base_url}/api/generate", json=payload
            ) as resp:
                async for line in resp.content:
                    if line.strip():
                        data = json.loads(line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
        except Exception as e:
            yield f"[Ollama stream error: {e}]"

    # ── Integration Point #14: Embeddings for semantic routing ────────────────
    async def embed(self, text: str, model: str = "nomic-embed-text") -> List[float]:
        """
        Generate embeddings via Ollama for semantic routing decisions.
        The BottleneckBridge uses these to route tasks to the most capable agent.
        """
        session = await self._get_session()
        payload = {"model": model, "prompt": text}
        try:
            async with session.post(
                f"{self.config.base_url}/api/embeddings", json=payload
            ) as resp:
                data = await resp.json()
                return data.get("embedding", [])
        except Exception as e:
            logger.error(f"[Ollama] Embeddings failed: {e}")
            return []

    async def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two embedding vectors."""
        if not vec_a or not vec_b:
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = sum(a ** 2 for a in vec_a) ** 0.5
        mag_b = sum(b ** 2 for b in vec_b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    async def health_check(self) -> bool:
        try:
            session = await self._get_session()
            async with session.get(f"{self.config.base_url}/api/tags") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
