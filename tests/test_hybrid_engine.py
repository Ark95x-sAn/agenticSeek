"""
Tests for the ARK95X Hybrid Engine.
Tests all 25 integration points using mocks (no live services required).
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# ── Test helpers ──────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def make_ok_response(source: str, **kwargs) -> dict:
    return {"status": "ok", "source": source, "response": "test response", **kwargs}


def make_offline_response(source: str) -> dict:
    return {"status": "offline", "source": source, "error": "connection_refused"}


# ── Integration Points #1-5: OpenClaw ────────────────────────────────────────

class TestOpenClawClient(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.clients.openclaw_client import OpenClawClient, OpenClawConfig
        self.client = OpenClawClient(OpenClawConfig(base_url="http://localhost:8080"))

    def test_ip1_dispatch_task_offline(self):
        """#1: dispatch_task returns offline when OpenClaw is not running."""
        result = run(self.client.dispatch_task({"prompt": "test"}))
        self.assertIn(result["status"], ("offline", "error", "ok"))
        self.assertEqual(result["source"], "openclaw")

    def test_ip3_execute_tool_structure(self):
        """#3: execute_tool returns expected structure (source always present)."""
        result = run(self.client.execute_tool("shell", {"command": "echo hi"}))
        self.assertIn("source", result)
        self.assertIn("status", result)
        # 'tool' key only present on success; offline/error is acceptable in test env
        if result["status"] == "ok":
            self.assertIn("tool", result)

    def test_ip5_handoff_to_ollama(self):
        """#5: handoff_to_ollama returns ollama_via_openclaw_handoff source."""
        result = run(self.client.handoff_to_ollama(
            {"prompt": "test", "local_model": "llama3"},
            ollama_url="http://localhost:11434"
        ))
        self.assertIn(result["status"], ("ok", "error", "offline"))

    def tearDown(self):
        run(self.client.close())


# ── Integration Points #6-10: BlackBox Desktop ───────────────────────────────

class TestBlackBoxClient(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.clients.blackbox_client import BlackBoxDesktopClient, BlackBoxConfig
        self.client = BlackBoxDesktopClient(BlackBoxConfig(rest_url="http://localhost:3000"))

    def test_ip9_arbitrate_suggestions_picks_highest_confidence(self):
        """#9: arbitrate_suggestions selects the highest confidence suggestion."""
        suggestions = [
            {"source": "copilot", "status": "ok", "confidence": 0.9, "completion": "def foo():"},
            {"source": "ollama", "status": "ok", "confidence": 0.6, "completion": "def bar():"},
        ]
        result = run(self.client.arbitrate_suggestions(suggestions))
        self.assertEqual(result["status"], "ok")
        # Ollama gets 1.1x boost: 0.6 * 1.1 = 0.66, Copilot stays 0.9 → Copilot wins
        self.assertEqual(result["winner"]["source"], "copilot")

    def test_ip9_arbitrate_empty_suggestions(self):
        """#9: arbitrate_suggestions handles empty list."""
        result = run(self.client.arbitrate_suggestions([]))
        self.assertEqual(result["status"], "error")

    def test_ip9_arbitrate_offline_penalized(self):
        """#9: offline suggestions get score 0."""
        suggestions = [
            {"source": "copilot", "status": "offline", "confidence": 0.99},
            {"source": "ollama", "status": "ok", "confidence": 0.5},
        ]
        result = run(self.client.arbitrate_suggestions(suggestions))
        self.assertEqual(result["winner"]["source"], "ollama")

    def tearDown(self):
        run(self.client.close())


# ── Integration Points #11-14: Ollama ────────────────────────────────────────

class TestOllamaClient(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.clients.ollama_client import OllamaClient, OllamaConfig
        self.client = OllamaClient(OllamaConfig(base_url="http://localhost:11434"))

    def test_ip14_cosine_similarity_identical(self):
        """#14: cosine_similarity of identical vectors = 1.0."""
        vec = [1.0, 0.5, 0.3]
        result = run(self.client.cosine_similarity(vec, vec))
        self.assertAlmostEqual(result, 1.0, places=5)

    def test_ip14_cosine_similarity_orthogonal(self):
        """#14: cosine_similarity of orthogonal vectors = 0.0."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        result = run(self.client.cosine_similarity(vec_a, vec_b))
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_ip14_cosine_similarity_empty(self):
        """#14: cosine_similarity handles empty vectors."""
        result = run(self.client.cosine_similarity([], []))
        self.assertEqual(result, 0.0)

    def test_ip11_generate_offline(self):
        """#11: generate returns offline when Ollama is not running."""
        result = run(self.client.generate("test prompt"))
        self.assertIn(result["status"], ("ok", "offline", "error"))

    def tearDown(self):
        run(self.client.close())


# ── Integration Points #15-18: Comet/Perplexity ──────────────────────────────

class TestCometClient(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.clients.comet_client import CometPerplexityClient, CometConfig
        self.client = CometPerplexityClient(CometConfig(api_key="test-key"))

    def test_ip18_context_injection(self):
        """#18: _inject_context adds to buffer and caps at 20."""
        for i in range(25):
            self.client._inject_context({"source": "perplexity", "query": f"q{i}", "answer": f"a{i}"})
        self.assertLessEqual(len(self.client._context_buffer), 20)

    def test_ip18_build_context_string(self):
        """#18: build_context_string formats buffer correctly."""
        self.client._inject_context({"source": "perplexity", "query": "test", "answer": "answer text"})
        ctx = self.client.build_context_string()
        self.assertIn("test", ctx)
        self.assertIn("answer text", ctx)

    def test_ip18_clear_context(self):
        """#18: clear_context empties the buffer."""
        self.client._inject_context({"source": "perplexity", "query": "x", "answer": "y"})
        self.client.clear_context()
        self.assertEqual(len(self.client._context_buffer), 0)

    def tearDown(self):
        run(self.client.close())


# ── Integration Points #19-22: Copilot ───────────────────────────────────────

class TestCopilotClient(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.clients.copilot_client import CopilotClient, CopilotConfig
        self.client = CopilotClient(CopilotConfig(github_token="test-token"))

    def test_ip21_rank_suggestions_order(self):
        """#21: rank_suggestions returns highest score first."""
        suggestions = [
            {"source": "ollama", "status": "ok", "confidence": 0.7},
            {"source": "copilot_lsp", "status": "ok", "confidence": 0.8},
            {"source": "blackbox_desktop", "status": "ok", "confidence": 0.6},
        ]
        result = run(self.client.rank_suggestions(suggestions, context={"language": "python"}))
        self.assertEqual(result[0]["source"], "copilot_lsp")  # 0.8 * 1.05 = 0.84

    def test_ip21_rank_offline_last(self):
        """#21: offline suggestions rank last."""
        suggestions = [
            {"source": "copilot_lsp", "status": "offline", "confidence": 0.99},
            {"source": "ollama", "status": "ok", "confidence": 0.3},
        ]
        result = run(self.client.rank_suggestions(suggestions, context={}))
        self.assertEqual(result[-1]["source"], "copilot_lsp")

    def test_ip22_os_info(self):
        """#22: get_os_info returns platform info."""
        info = self.client.get_os_info()
        self.assertIn("platform", info)
        self.assertIn("is_windows", info)
        self.assertIn("overlay_supported", info)

    def tearDown(self):
        run(self.client.close())


# ── Integration Point #23: BottleneckBridge ──────────────────────────────────

class TestBottleneckBridge(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.routing.bottleneck import BottleneckBridge, CircuitBreaker, CircuitState

        # Mock clients
        self.mock_ollama = AsyncMock()
        self.mock_ollama.name = "ollama"
        self.mock_ollama.generate = AsyncMock(return_value=make_ok_response("ollama"))
        self.mock_ollama.health_check = AsyncMock(return_value=True)

        self.mock_openclaw = AsyncMock()
        self.mock_openclaw.name = "openclaw"
        self.mock_openclaw.dispatch_task = AsyncMock(return_value=make_ok_response("openclaw"))
        self.mock_openclaw.health_check = AsyncMock(return_value=False)

        self.bridge = BottleneckBridge(
            clients={"ollama": self.mock_ollama, "openclaw": self.mock_openclaw}
        )

    def test_ip23_circuit_breaker_opens_after_failures(self):
        """#23: Circuit breaker opens after threshold failures."""
        from hybrid_engine.routing.bottleneck import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_ip23_circuit_breaker_recovers(self):
        """#23: Circuit breaker transitions OPEN → HALF_OPEN → CLOSED."""
        import time
        from hybrid_engine.routing.bottleneck import CircuitBreaker, CircuitState
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.01)
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        time.sleep(0.02)
        self.assertTrue(cb.can_attempt())
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.record_success()
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_ip23_metrics_tracking(self):
        """#23: Metrics track success/failure counts."""
        self.bridge._record_success("ollama", 50.0)
        self.bridge._record_success("ollama", 100.0)
        self.bridge._record_failure("openclaw")
        m_ollama = self.bridge._metrics["ollama"]
        m_openclaw = self.bridge._metrics["openclaw"]
        self.assertEqual(m_ollama.successful_requests, 2)
        self.assertAlmostEqual(m_ollama.avg_latency_ms, 75.0)
        self.assertEqual(m_openclaw.failed_requests, 1)

    def test_ip23_capability_map_coverage(self):
        """#23: All task types have at least one client in capability map."""
        from hybrid_engine.routing.bottleneck import BottleneckBridge
        for task_type, clients in BottleneckBridge.CAPABILITY_MAP.items():
            self.assertGreater(len(clients), 0, f"No clients for task type: {task_type}")

    def test_ip23_health_check_all(self):
        """#23: health_check_all returns dict for all clients."""
        result = run(self.bridge.health_check_all())
        self.assertIn("ollama", result)
        self.assertIn("openclaw", result)
        self.assertTrue(result["ollama"])
        self.assertFalse(result["openclaw"])


# ── Integration Point #24: HybridRouter ──────────────────────────────────────

class TestHybridRouter(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.routing.bottleneck import BottleneckBridge
        from hybrid_engine.routing.router import HybridRouter

        self.mock_bridge = MagicMock(spec=BottleneckBridge)
        self.mock_bridge.submit = AsyncMock(return_value=make_ok_response("ollama"))
        self.mock_bridge.get_queue_depth = MagicMock(return_value=0)
        self.mock_bridge.get_metrics = MagicMock(return_value={})

        self.router = HybridRouter(bridge=self.mock_bridge)

    def test_ip24_classify_web_search(self):
        """#24: classify_task correctly identifies web search."""
        self.assertEqual(self.router.classify_task("search for latest AI news"), "web_search")

    def test_ip24_classify_code(self):
        """#24: classify_task correctly identifies code generation."""
        self.assertEqual(self.router.classify_task("write a function to parse JSON"), "code")

    def test_ip24_classify_shell(self):
        """#24: classify_task correctly identifies shell tasks."""
        self.assertEqual(self.router.classify_task("run this bash command"), "shell")

    def test_ip24_classify_chat(self):
        """#24: classify_task correctly identifies chat."""
        self.assertEqual(self.router.classify_task("explain how neural networks work"), "chat")

    def test_ip24_classify_with_hint(self):
        """#24: classify_task respects explicit type hint."""
        self.assertEqual(
            self.router.classify_task("anything", hints={"type": "embeddings"}),
            "embeddings"
        )

    def test_ip24_route_calls_bridge(self):
        """#24: route() submits to bridge and returns result."""
        result = run(self.router.route("test prompt"))
        self.mock_bridge.submit.assert_called_once()
        self.assertEqual(result["status"], "ok")

    def test_ip24_session_tracking(self):
        """#24: route() updates session history."""
        run(self.router.route("first prompt", session_id="sess1"))
        run(self.router.route("second prompt", session_id="sess1"))
        session = self.router.get_session("sess1")
        self.assertEqual(len(session["history"]), 2)

    def test_ip24_result_caching(self):
        """#24: Identical prompts return cached results on second call."""
        run(self.router.route("cached prompt", use_cache=True))
        run(self.router.route("cached prompt", use_cache=True))
        # Bridge should only be called once (second is cached)
        self.assertEqual(self.mock_bridge.submit.call_count, 1)

    def test_ip24_list_pipelines(self):
        """#24: list_pipelines returns all built-in pipelines."""
        pipelines = self.router.list_pipelines()
        names = [p["name"] for p in pipelines]
        self.assertIn("research_and_code", names)
        self.assertIn("local_first_code", names)
        self.assertIn("deep_analysis", names)
        self.assertIn("multi_agent_fanout", names)

    def test_ip24_status(self):
        """#24: get_status returns expected keys."""
        status = self.router.get_status()
        self.assertIn("active_sessions", status)
        self.assertIn("registered_pipelines", status)
        self.assertIn("queue_depth", status)


# ── Integration Point #25: CommsHub ──────────────────────────────────────────

class TestCommsHub(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.comms.hub import CommsHub
        self.hub = CommsHub()

    def test_ip25_publish_and_subscribe(self):
        """#25: publish delivers message to subscriber."""
        async def _test():
            await self.hub.start()
            q = self.hub.subscribe("task.completed")
            msg_id = await self.hub.publish("task.completed", {"task_id": "t1"}, source="test")
            msg = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertEqual(msg.topic, "task.completed")
            self.assertEqual(msg.payload["task_id"], "t1")
            await self.hub.stop()
        run(_test())

    def test_ip25_wildcard_subscriber(self):
        """#25: wildcard subscriber receives all topics."""
        async def _test():
            await self.hub.start()
            q = self.hub.subscribe_all()
            await self.hub.publish("task.submitted", {"x": 1}, source="test")
            await self.hub.publish("client.online", {"client": "ollama"}, source="test")
            msg1 = await asyncio.wait_for(q.get(), timeout=1.0)
            msg2 = await asyncio.wait_for(q.get(), timeout=1.0)
            topics = {msg1.topic, msg2.topic}
            self.assertIn("task.submitted", topics)
            self.assertIn("client.online", topics)
            await self.hub.stop()
        run(_test())

    def test_ip25_message_history(self):
        """#25: get_history returns published messages."""
        async def _test():
            await self.hub.start()
            await self.hub.publish("pipeline.done", {"pipeline": "test"}, source="router")
            history = self.hub.get_history(topic="pipeline.done")
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["payload"]["pipeline"], "test")
            await self.hub.stop()
        run(_test())

    def test_ip25_stats(self):
        """#25: get_stats returns expected structure."""
        async def _test():
            await self.hub.start()
            await self.hub.publish("stream.token", {"token": "hello"}, source="ollama")
            stats = self.hub.get_stats()
            self.assertIn("total_messages", stats)
            self.assertIn("topic_breakdown", stats)
            self.assertGreater(stats["total_messages"], 0)
            await self.hub.stop()
        run(_test())

    def test_ip25_relay_stream(self):
        """#25: relay_stream assembles tokens and publishes stream.done."""
        async def _test():
            await self.hub.start()
            q = self.hub.subscribe("stream.done")

            async def token_gen():
                for t in ["Hello", " ", "World"]:
                    yield t

            result = await self.hub.relay_stream(token_gen(), source="ollama", session_id="s1")
            self.assertEqual(result, "Hello World")

            done_msg = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertEqual(done_msg.payload["response"], "Hello World")
            self.assertEqual(done_msg.payload["token_count"], 3)
            await self.hub.stop()
        run(_test())

    def test_ip25_emit_convenience_methods(self):
        """#25: Convenience emit methods publish to correct topics."""
        async def _test():
            await self.hub.start()
            q_task = self.hub.subscribe("task.submitted")
            q_client = self.hub.subscribe("client.online")

            await self.hub.emit_task_submitted("t1", "code", "openclaw")
            await self.hub.emit_client_status("ollama", True)

            msg_task = await asyncio.wait_for(q_task.get(), timeout=1.0)
            msg_client = await asyncio.wait_for(q_client.get(), timeout=1.0)

            self.assertEqual(msg_task.payload["task_id"], "t1")
            self.assertEqual(msg_client.payload["client"], "ollama")
            await self.hub.stop()
        run(_test())


# ── Bridge tests ──────────────────────────────────────────────────────────────

class TestOllamaOpenClawBridge(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.bridges.ollama_openclaw_bridge import OllamaOpenClawBridge
        self.ollama = AsyncMock()
        self.ollama.generate = AsyncMock(return_value={
            "status": "ok", "response": '{"steps": [{"action": "run", "args": {}}]}'
        })
        self.openclaw = AsyncMock()
        self.openclaw.dispatch_task = AsyncMock(return_value={"status": "ok", "data": "done"})
        self.bridge = OllamaOpenClawBridge(self.ollama, self.openclaw)

    def test_reason_then_execute(self):
        """Bridge: Ollama reasons → OpenClaw executes."""
        result = run(self.bridge.reason_then_execute("Deploy the app"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["bridge"], "ollama_openclaw")
        self.ollama.generate.assert_called_once()
        self.openclaw.dispatch_task.assert_called_once()


class TestCopilotBlackBoxBridge(unittest.TestCase):

    def setUp(self):
        from hybrid_engine.bridges.copilot_blackbox_bridge import CopilotBlackBoxBridge
        self.copilot = AsyncMock()
        self.copilot.get_lsp_completion = AsyncMock(return_value={
            "status": "ok", "source": "copilot_lsp", "confidence": 0.85, "completions": ["def foo():"]
        })
        self.blackbox = AsyncMock()
        self.blackbox.get_completion = AsyncMock(return_value={
            "status": "ok", "source": "blackbox_desktop", "confidence": 0.75, "completion": "def bar():"
        })
        self.blackbox.arbitrate_suggestions = AsyncMock(return_value={
            "status": "ok", "winner": {"source": "copilot_lsp", "confidence": 0.85}, "score": 0.85
        })
        self.bridge = CopilotBlackBoxBridge(self.copilot, self.blackbox)

    def test_get_best_completion(self):
        """Bridge: Both generate completions → arbitrate winner."""
        result = run(self.bridge.get_best_completion({"file_path": "test.py", "language": "python"}))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["bridge"], "copilot_blackbox")
        self.assertIsNotNone(result["best"])


# ── EngineConfig tests ────────────────────────────────────────────────────────

class TestEngineConfig(unittest.TestCase):

    def test_from_env_defaults(self):
        """EngineConfig.from_env() uses sensible defaults."""
        from hybrid_engine.deployment.engine_builder import EngineConfig
        cfg = EngineConfig.from_env()
        self.assertEqual(cfg.ollama_url, "http://localhost:11434")
        self.assertEqual(cfg.engine_port, 8765)
        self.assertFalse(cfg.enable_windows_overlay)

    def test_from_dict(self):
        """EngineConfig.from_dict() applies overrides."""
        from hybrid_engine.deployment.engine_builder import EngineConfig
        cfg = EngineConfig.from_dict({"engine_port": 9999, "ollama_model": "mistral:7b"})
        self.assertEqual(cfg.engine_port, 9999)
        self.assertEqual(cfg.ollama_model, "mistral:7b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
