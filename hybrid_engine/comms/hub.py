"""
CommsHub — Integration Point #25
==================================
The CommsHub provides real-time pub/sub messaging between all components
of the hybrid engine. It enables:
  - Event broadcasting (tool status changes, task completions)
  - WebSocket relay for frontend/overlay UIs
  - Inter-agent messaging (OpenClaw ↔ Ollama ↔ Copilot)
  - Streaming token relay from any source to any subscriber
  - Audit logging of all cross-tool communications

Integration Point #25 — Real-time comms hub with pub/sub and WebSocket relay
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set

logger = logging.getLogger("hybrid_engine.comms")


@dataclass
class Message:
    """A message in the comms hub."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = "general"
    source: str = "system"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    ttl: float = 60.0  # seconds

    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "topic": self.topic,
            "source": self.source,
            "payload": self.payload,
            "timestamp": self.timestamp,
        })

    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


# Standard topics used across the hybrid engine
TOPICS = {
    "task.submitted": "A task was submitted to the bridge",
    "task.completed": "A task completed successfully",
    "task.failed": "A task failed",
    "client.online": "A client came online",
    "client.offline": "A client went offline",
    "stream.token": "A streaming token from any LLM",
    "stream.done": "A stream completed",
    "context.updated": "Shared context was updated",
    "session.created": "A new session was created",
    "session.ended": "A session ended",
    "health.check": "Health check result",
    "pipeline.started": "A pipeline started",
    "pipeline.step": "A pipeline step completed",
    "pipeline.done": "A pipeline completed",
    "overlay.command": "A command from the Windows overlay",
    "overlay.response": "A response to the overlay",
}


class CommsHub:
    """
    Integration Point #25: Real-time comms hub.
    Pub/sub messaging backbone for the entire hybrid engine.
    """

    def __init__(self, max_history: int = 500):
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)
        self._wildcard_subscribers: List[asyncio.Queue] = []
        self._message_history: List[Message] = []
        self._max_history = max_history
        self._ws_connections: Set[asyncio.Queue] = set()
        self._audit_log: List[Dict[str, Any]] = []
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def start(self):
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("[CommsHub] Started")

    async def stop(self):
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
        logger.info("[CommsHub] Stopped")

    # ── Publishing ────────────────────────────────────────────────────────────
    async def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        source: str = "system",
        ttl: float = 60.0,
    ) -> str:
        """Publish a message to a topic. Returns the message ID."""
        msg = Message(topic=topic, source=source, payload=payload, ttl=ttl)

        # Store in history
        self._message_history.append(msg)
        if len(self._message_history) > self._max_history:
            self._message_history.pop(0)

        # Audit log
        self._audit_log.append({
            "id": msg.id,
            "topic": topic,
            "source": source,
            "timestamp": msg.timestamp,
        })

        # Deliver to topic subscribers
        for queue in self._subscribers.get(topic, []):
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                logger.warning(f"[CommsHub] Subscriber queue full for topic={topic}")

        # Deliver to wildcard subscribers
        for queue in self._wildcard_subscribers:
            try:
                queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass

        # Relay to WebSocket connections
        for ws_queue in list(self._ws_connections):
            try:
                ws_queue.put_nowait(msg)
            except asyncio.QueueFull:
                pass

        logger.debug(f"[CommsHub] Published {topic} from {source} (id={msg.id})")
        return msg.id

    # ── Subscribing ───────────────────────────────────────────────────────────
    def subscribe(self, topic: str, queue_size: int = 100) -> asyncio.Queue:
        """Subscribe to a specific topic. Returns a queue to receive messages."""
        q: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._subscribers[topic].append(q)
        return q

    def subscribe_all(self, queue_size: int = 200) -> asyncio.Queue:
        """Subscribe to ALL topics (wildcard). Returns a queue."""
        q: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._wildcard_subscribers.append(q)
        return q

    def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(queue)
            except ValueError:
                pass

    def unsubscribe_all(self, queue: asyncio.Queue) -> None:
        try:
            self._wildcard_subscribers.remove(queue)
        except ValueError:
            pass

    # ── Async iteration ───────────────────────────────────────────────────────
    async def listen(self, topic: str) -> AsyncGenerator[Message, None]:
        """Async generator: yield messages from a topic indefinitely."""
        q = self.subscribe(topic)
        try:
            while self._running:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=1.0)
                    if not msg.is_expired:
                        yield msg
                except asyncio.TimeoutError:
                    continue
        finally:
            self.unsubscribe(topic, q)

    async def listen_once(self, topic: str, timeout: float = 30.0) -> Optional[Message]:
        """Wait for a single message on a topic."""
        q = self.subscribe(topic)
        try:
            return await asyncio.wait_for(q.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self.unsubscribe(topic, q)

    # ── WebSocket relay ───────────────────────────────────────────────────────
    def add_ws_connection(self) -> asyncio.Queue:
        """Register a WebSocket connection to receive all messages."""
        q: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._ws_connections.add(q)
        return q

    def remove_ws_connection(self, queue: asyncio.Queue) -> None:
        self._ws_connections.discard(queue)

    async def ws_stream(self, queue: asyncio.Queue) -> AsyncGenerator[str, None]:
        """Stream messages from a WebSocket queue as JSON strings."""
        while self._running:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield msg.to_json()
            except asyncio.TimeoutError:
                yield json.dumps({"type": "ping", "timestamp": time.time()})
            except Exception as e:
                logger.error(f"[CommsHub WS] Stream error: {e}")
                break

    # ── Streaming token relay ─────────────────────────────────────────────────
    async def relay_stream(
        self,
        token_generator: AsyncGenerator[str, None],
        source: str,
        session_id: str = "default",
    ) -> str:
        """
        Relay streaming tokens from any LLM into the comms hub.
        Publishes each token as a stream.token event.
        Returns the full assembled response.
        """
        full_response = []
        async for token in token_generator:
            full_response.append(token)
            await self.publish(
                "stream.token",
                {"token": token, "session_id": session_id},
                source=source,
                ttl=10.0,
            )

        assembled = "".join(full_response)
        await self.publish(
            "stream.done",
            {"response": assembled, "session_id": session_id, "token_count": len(full_response)},
            source=source,
        )
        return assembled

    # ── Convenience publishers ────────────────────────────────────────────────
    async def emit_task_submitted(self, task_id: str, task_type: str, source: str):
        await self.publish("task.submitted", {"task_id": task_id, "type": task_type}, source=source)

    async def emit_task_completed(self, task_id: str, result: Dict[str, Any], source: str):
        await self.publish("task.completed", {"task_id": task_id, "result": result}, source=source)

    async def emit_client_status(self, client_name: str, online: bool):
        topic = "client.online" if online else "client.offline"
        await self.publish(topic, {"client": client_name}, source="health_monitor")

    async def emit_pipeline_step(self, pipeline: str, step: int, result: Dict[str, Any]):
        await self.publish(
            "pipeline.step",
            {"pipeline": pipeline, "step": step, "result": result},
            source="router",
        )

    async def emit_overlay_command(self, command: str, args: Dict[str, Any]):
        await self.publish("overlay.command", {"command": command, "args": args}, source="windows_overlay")

    # ── History and audit ─────────────────────────────────────────────────────
    def get_history(self, topic: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        msgs = self._message_history
        if topic:
            msgs = [m for m in msgs if m.topic == topic]
        return [
            {"id": m.id, "topic": m.topic, "source": m.source, "payload": m.payload, "timestamp": m.timestamp}
            for m in msgs[-limit:]
        ]

    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._audit_log[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        topic_counts: Dict[str, int] = defaultdict(int)
        for m in self._message_history:
            topic_counts[m.topic] += 1
        return {
            "total_messages": len(self._message_history),
            "active_subscribers": sum(len(v) for v in self._subscribers.values()),
            "wildcard_subscribers": len(self._wildcard_subscribers),
            "ws_connections": len(self._ws_connections),
            "topic_breakdown": dict(topic_counts),
        }

    # ── Cleanup ───────────────────────────────────────────────────────────────
    async def _cleanup_loop(self):
        """Periodically remove expired messages from history."""
        while self._running:
            await asyncio.sleep(30)
            before = len(self._message_history)
            self._message_history = [m for m in self._message_history if not m.is_expired]
            removed = before - len(self._message_history)
            if removed > 0:
                logger.debug(f"[CommsHub] Cleaned {removed} expired messages")
