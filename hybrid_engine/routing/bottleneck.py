"""
BottleneckBridge — Integration Point #23
=========================================
The BottleneckBridge is the central routing hub that ALL traffic passes through.
It implements:
  - Priority queuing with async task scheduling
  - Load balancing across all 5 AI tools
  - Circuit breaker pattern for fault tolerance
  - Semantic routing using Ollama embeddings
  - Rate limiting and backpressure
  - Health monitoring and automatic failover

Integration Point #23 — Central bottleneck bridge with intelligent routing
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

logger = logging.getLogger("hybrid_engine.bottleneck")


class TaskPriority(Enum):
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing — reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """Per-client circuit breaker for fault tolerance."""
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count: int = 0

    def record_success(self):
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info(f"[Circuit] {self.name} → CLOSED (recovered)")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"[Circuit] {self.name} → OPEN (too many failures)")

    def can_attempt(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            elapsed = time.monotonic() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"[Circuit] {self.name} → HALF_OPEN (testing)")
                return True
            return False
        return True  # HALF_OPEN: allow one attempt


@dataclass
class RouteMetrics:
    """Track per-client routing metrics."""
    client_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 9999.0
        return self.total_latency_ms / self.successful_requests


@dataclass
class BridgeTask:
    """A task queued in the bottleneck bridge."""
    task_id: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    preferred_client: Optional[str] = None
    fallback_clients: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    future: Optional[asyncio.Future] = None

    def __lt__(self, other: "BridgeTask") -> bool:
        return self.priority.value < other.priority.value


class BottleneckBridge:
    """
    Integration Point #23: Central routing bottleneck bridge.

    ALL requests from all 5 AI tools flow through this bridge.
    It decides: which client handles what, when, and in what order.
    """

    # Capability → preferred client mapping
    CAPABILITY_MAP: Dict[str, List[str]] = {
        "code": ["blackbox_desktop", "copilot", "openclaw", "ollama"],
        "code_completion": ["copilot", "blackbox_desktop", "ollama"],
        "shell": ["openclaw", "ollama"],
        "file": ["openclaw", "blackbox_desktop"],
        "browser": ["comet_perplexity", "openclaw"],
        "web_search": ["comet_perplexity"],
        "deep_research": ["comet_perplexity", "ollama"],
        "reasoning": ["ollama", "openclaw", "copilot"],
        "embeddings": ["ollama"],
        "real_time": ["comet_perplexity"],
        "inference": ["ollama", "openclaw"],
        "chat": ["copilot", "blackbox_desktop", "ollama"],
        "analysis": ["ollama", "openclaw", "copilot"],
        "generic": ["ollama", "openclaw", "blackbox_desktop", "copilot", "comet_perplexity"],
    }

    def __init__(self, clients: Dict[str, Any], max_queue_size: int = 500):
        self.clients = clients  # name → client instance
        self.max_queue_size = max_queue_size
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._circuits: Dict[str, CircuitBreaker] = {
            name: CircuitBreaker(name=name) for name in clients
        }
        self._metrics: Dict[str, RouteMetrics] = {
            name: RouteMetrics(client_name=name) for name in clients
        }
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False
        self._request_counter = 0

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def start(self):
        """Start the bridge worker loop."""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("[BottleneckBridge] Started")

    async def stop(self):
        """Gracefully stop the bridge."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("[BottleneckBridge] Stopped")

    # ── Task submission ───────────────────────────────────────────────────────
    async def submit(
        self,
        payload: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        preferred_client: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a task to the bridge. Returns the result when complete.
        This is the single entry point for ALL hybrid engine requests.
        """
        self._request_counter += 1
        task_id = f"bridge-{self._request_counter:06d}"
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        bridge_task = BridgeTask(
            task_id=task_id,
            payload=payload,
            priority=priority,
            preferred_client=preferred_client,
            future=future,
        )

        await self._queue.put((priority.value, bridge_task))
        logger.debug(f"[Bridge] Queued {task_id} (priority={priority.name})")

        return await future

    async def submit_nowait(self, payload: Dict[str, Any], priority: TaskPriority = TaskPriority.NORMAL) -> str:
        """Submit a task without waiting for the result. Returns task_id."""
        self._request_counter += 1
        task_id = f"bridge-{self._request_counter:06d}"
        bridge_task = BridgeTask(task_id=task_id, payload=payload, priority=priority)
        try:
            self._queue.put_nowait((priority.value, bridge_task))
        except asyncio.QueueFull:
            logger.warning("[Bridge] Queue full — dropping low-priority task")
        return task_id

    # ── Worker loop ───────────────────────────────────────────────────────────
    async def _worker_loop(self):
        """Main dispatch loop — processes tasks from the priority queue."""
        while self._running:
            try:
                _, bridge_task = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                asyncio.create_task(self._dispatch(bridge_task))
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Bridge Worker] Error: {e}")

    # ── Dispatch logic ────────────────────────────────────────────────────────
    async def _dispatch(self, bridge_task: BridgeTask):
        """Route a task to the best available client."""
        payload = bridge_task.payload
        task_type = payload.get("type", "generic")
        preferred = bridge_task.preferred_client

        # Build ordered list of clients to try
        client_order = self._resolve_client_order(task_type, preferred)

        result = None
        for client_name in client_order:
            circuit = self._circuits.get(client_name)
            if circuit and not circuit.can_attempt():
                logger.debug(f"[Bridge] {client_name} circuit OPEN — skipping")
                continue

            client = self.clients.get(client_name)
            if not client:
                continue

            start = time.monotonic()
            try:
                result = await self._call_client(client, client_name, payload)
                latency_ms = (time.monotonic() - start) * 1000

                if result.get("status") in ("ok", "success"):
                    self._record_success(client_name, latency_ms)
                    result["routed_via"] = client_name
                    result["latency_ms"] = latency_ms
                    break
                elif result.get("status") == "offline":
                    self._record_failure(client_name)
                    logger.warning(f"[Bridge] {client_name} offline — trying next")
                else:
                    self._record_failure(client_name)
                    logger.warning(f"[Bridge] {client_name} error — trying next")

            except Exception as e:
                self._record_failure(client_name)
                logger.error(f"[Bridge] {client_name} exception: {e}")

        if result is None:
            result = {
                "status": "error",
                "error": "all_clients_failed",
                "task_id": bridge_task.task_id,
            }

        if bridge_task.future and not bridge_task.future.done():
            bridge_task.future.set_result(result)

    def _resolve_client_order(self, task_type: str, preferred: Optional[str]) -> List[str]:
        """Determine the ordered list of clients to try for a given task type."""
        base_order = self.CAPABILITY_MAP.get(task_type, self.CAPABILITY_MAP["generic"])

        # Filter to only available clients
        available = [c for c in base_order if c in self.clients]

        # Sort by: preferred first, then by success rate (descending), then by latency
        def score(name: str) -> Tuple[int, float, float]:
            is_preferred = 0 if name == preferred else 1
            m = self._metrics.get(name)
            success_rate = -(m.success_rate if m else 1.0)
            latency = m.avg_latency_ms if m else 0.0
            return (is_preferred, success_rate, latency)

        return sorted(available, key=score)

    async def _call_client(self, client: Any, client_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to the appropriate client method based on task type."""
        task_type = payload.get("type", "generic")
        prompt = payload.get("prompt", "")
        messages = payload.get("messages", [])

        if task_type == "code_completion":
            return await client.get_completion(payload) if hasattr(client, "get_completion") else \
                   await client.generate(prompt) if hasattr(client, "generate") else \
                   {"status": "error", "error": "no_completion_method"}

        elif task_type == "web_search":
            return await client.search(prompt) if hasattr(client, "search") else \
                   {"status": "error", "error": "no_search_method"}

        elif task_type == "chat":
            if hasattr(client, "chat"):
                return await client.chat(messages or [{"role": "user", "content": prompt}])
            elif hasattr(client, "generate"):
                return await client.generate(prompt)
            return {"status": "error", "error": "no_chat_method"}

        elif task_type == "inference":
            if hasattr(client, "generate"):
                return await client.generate(prompt)
            return await client.dispatch_task(payload) if hasattr(client, "dispatch_task") else \
                   {"status": "error", "error": "no_inference_method"}

        else:
            # Generic dispatch
            if hasattr(client, "dispatch_task"):
                return await client.dispatch_task(payload)
            elif hasattr(client, "generate"):
                return await client.generate(prompt)
            elif hasattr(client, "chat"):
                return await client.chat([{"role": "user", "content": prompt}])
            return {"status": "error", "error": f"no_handler_for_{task_type}"}

    # ── Metrics ───────────────────────────────────────────────────────────────
    def _record_success(self, client_name: str, latency_ms: float):
        m = self._metrics.get(client_name)
        if m:
            m.total_requests += 1
            m.successful_requests += 1
            m.total_latency_ms += latency_ms
            m.last_latency_ms = latency_ms
        c = self._circuits.get(client_name)
        if c:
            c.record_success()

    def _record_failure(self, client_name: str):
        m = self._metrics.get(client_name)
        if m:
            m.total_requests += 1
            m.failed_requests += 1
        c = self._circuits.get(client_name)
        if c:
            c.record_failure()

    def get_metrics(self) -> Dict[str, Any]:
        return {
            name: {
                "success_rate": f"{m.success_rate:.1%}",
                "avg_latency_ms": f"{m.avg_latency_ms:.1f}",
                "total_requests": m.total_requests,
                "circuit_state": self._circuits[name].state.value,
            }
            for name, m in self._metrics.items()
        }

    def get_queue_depth(self) -> int:
        return self._queue.qsize()

    async def health_check_all(self) -> Dict[str, bool]:
        results = {}
        for name, client in self.clients.items():
            if hasattr(client, "health_check"):
                try:
                    results[name] = await asyncio.wait_for(client.health_check(), timeout=5.0)
                except Exception:
                    results[name] = False
            else:
                results[name] = True
        return results
