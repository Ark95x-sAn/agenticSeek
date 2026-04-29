"""
EngineBuilder — The Engine That Builds It All
===============================================
EngineBuilder is the top-level factory and lifecycle manager for the
entire hybrid engine stack. It:
  1. Reads configuration (env vars, config files, CLI args)
  2. Instantiates all 5 AI tool clients
  3. Wires them into the BottleneckBridge
  4. Starts the HybridRouter on top
  5. Launches the CommsHub
  6. Starts the health monitor
  7. Optionally launches the Windows OS wrapper overlay
  8. Exposes a FastAPI server for external access
  9. Provides a CLI for direct interaction
  10. Handles graceful shutdown

This is the single entry point to deploy the entire hybrid engine.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("hybrid_engine.builder")


@dataclass
class EngineConfig:
    """Master configuration for the hybrid engine."""

    # OpenClaw
    openclaw_url: str = field(default_factory=lambda: os.getenv("OPENCLAW_URL", "http://localhost:8080"))
    openclaw_api_key: str = field(default_factory=lambda: os.getenv("OPENCLAW_API_KEY", ""))

    # BlackBox Desktop
    blackbox_url: str = field(default_factory=lambda: os.getenv("BLACKBOX_URL", "http://localhost:3000"))
    blackbox_api_key: str = field(default_factory=lambda: os.getenv("BLACKBOX_API_KEY", ""))

    # Ollama
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3:8b"))

    # Comet / Perplexity
    perplexity_api_key: str = field(default_factory=lambda: os.getenv("PERPLEXITY_API_KEY", ""))
    comet_url: str = field(default_factory=lambda: os.getenv("COMET_URL", "http://localhost:9090"))

    # Copilot
    github_token: str = field(default_factory=lambda: os.getenv("GITHUB_TOKEN", ""))
    copilot_lsp_port: int = field(default_factory=lambda: int(os.getenv("COPILOT_LSP_PORT", "6009")))

    # Engine
    engine_host: str = field(default_factory=lambda: os.getenv("ENGINE_HOST", "0.0.0.0"))
    engine_port: int = field(default_factory=lambda: int(os.getenv("ENGINE_PORT", "8765")))
    enable_windows_overlay: bool = field(default_factory=lambda: os.getenv("ENABLE_OVERLAY", "false").lower() == "true")
    health_check_interval: float = 30.0
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    @classmethod
    def from_env(cls) -> "EngineConfig":
        return cls()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EngineConfig":
        cfg = cls()
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


class EngineBuilder:
    """
    The Engine That Builds It All.
    Assembles and manages the complete hybrid AI engine lifecycle.
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig.from_env()
        self._clients: Dict[str, Any] = {}
        self._bridge: Optional[Any] = None
        self._router: Optional[Any] = None
        self._comms: Optional[Any] = None
        self._health_task: Optional[asyncio.Task] = None
        self._api_server: Optional[Any] = None
        self._built = False

        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper(), logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

    # ── Build ─────────────────────────────────────────────────────────────────
    async def build(self) -> "EngineBuilder":
        """
        Assemble the complete hybrid engine.
        Returns self for chaining: await EngineBuilder().build()
        """
        logger.info("=" * 60)
        logger.info("  HYBRID ENGINE — ARK95X Build Starting")
        logger.info("=" * 60)

        # Step 1: Import clients (lazy to avoid circular imports at module level)
        from hybrid_engine.clients.openclaw_client import OpenClawClient, OpenClawConfig
        from hybrid_engine.clients.blackbox_client import BlackBoxDesktopClient, BlackBoxConfig
        from hybrid_engine.clients.ollama_client import OllamaClient, OllamaConfig
        from hybrid_engine.clients.comet_client import CometPerplexityClient, CometConfig
        from hybrid_engine.clients.copilot_client import CopilotClient, CopilotConfig
        from hybrid_engine.routing.bottleneck import BottleneckBridge
        from hybrid_engine.routing.router import HybridRouter
        from hybrid_engine.comms.hub import CommsHub

        # Step 2: Instantiate clients
        logger.info("[Build] Instantiating AI tool clients...")

        self._clients["openclaw"] = OpenClawClient(
            OpenClawConfig(base_url=self.config.openclaw_url, api_key=self.config.openclaw_api_key)
        )
        logger.info("  ✓ OpenClaw client ready")

        self._clients["blackbox_desktop"] = BlackBoxDesktopClient(
            BlackBoxConfig(rest_url=self.config.blackbox_url, api_key=self.config.blackbox_api_key)
        )
        logger.info("  ✓ BlackBox Desktop client ready")

        self._clients["ollama"] = OllamaClient(
            OllamaConfig(base_url=self.config.ollama_url, default_model=self.config.ollama_model)
        )
        logger.info("  ✓ Ollama client ready")

        self._clients["comet_perplexity"] = CometPerplexityClient(
            CometConfig(
                perplexity_api_url="https://api.perplexity.ai",
                comet_local_url=self.config.comet_url,
                api_key=self.config.perplexity_api_key,
            )
        )
        logger.info("  ✓ Comet/Perplexity client ready")

        self._clients["copilot"] = CopilotClient(
            CopilotConfig(
                github_token=self.config.github_token,
                lsp_port=self.config.copilot_lsp_port,
            )
        )
        logger.info("  ✓ Copilot client ready")

        # Step 3: Wire BottleneckBridge
        logger.info("[Build] Wiring BottleneckBridge...")
        self._bridge = BottleneckBridge(clients=self._clients)
        await self._bridge.start()
        logger.info("  ✓ BottleneckBridge started")

        # Step 4: Start HybridRouter
        logger.info("[Build] Starting HybridRouter...")
        self._router = HybridRouter(bridge=self._bridge)
        logger.info("  ✓ HybridRouter ready")

        # Step 5: Start CommsHub
        logger.info("[Build] Starting CommsHub...")
        self._comms = CommsHub()
        await self._comms.start()
        logger.info("  ✓ CommsHub started")

        # Step 6: Start health monitor
        logger.info("[Build] Starting health monitor...")
        self._health_task = asyncio.create_task(self._health_monitor())
        logger.info("  ✓ Health monitor running")

        # Step 7: Windows overlay (optional)
        if self.config.enable_windows_overlay:
            logger.info("[Build] Launching Windows OS overlay...")
            copilot_client = self._clients.get("copilot")
            if copilot_client:
                copilot_client.launch_windows_overlay()

        self._built = True
        logger.info("=" * 60)
        logger.info("  HYBRID ENGINE — Build Complete ✓")
        logger.info(f"  Clients: {list(self._clients.keys())}")
        logger.info(f"  API: http://{self.config.engine_host}:{self.config.engine_port}")
        logger.info("=" * 60)

        return self

    # ── FastAPI server ────────────────────────────────────────────────────────
    def build_api(self):
        """Build and return the FastAPI app for the hybrid engine."""
        try:
            from fastapi import FastAPI, WebSocket, WebSocketDisconnect
            from fastapi.middleware.cors import CORSMiddleware
            from fastapi.responses import JSONResponse
            from pydantic import BaseModel
        except ImportError:
            logger.error("[Build] FastAPI not installed. Run: pip install fastapi uvicorn")
            return None

        app = FastAPI(
            title="Hybrid Engine API",
            description="ARK95X Hybrid AI Engine — OpenClaw · BlackBox · Ollama · Comet · Copilot",
            version="1.0.0",
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        class RouteRequest(BaseModel):
            prompt: str
            session_id: str = "default"
            priority: str = "NORMAL"
            hints: Optional[Dict[str, Any]] = None
            pipeline: Optional[str] = None

        @app.get("/health")
        async def health():
            if not self._bridge:
                return JSONResponse({"status": "not_built"}, status_code=503)
            checks = await self._bridge.health_check_all()
            return {"status": "ok", "clients": checks}

        @app.get("/status")
        async def status():
            if not self._router:
                return JSONResponse({"status": "not_built"}, status_code=503)
            return self._router.get_status()

        @app.get("/pipelines")
        async def list_pipelines():
            if not self._router:
                return []
            return self._router.list_pipelines()

        @app.get("/metrics")
        async def metrics():
            if not self._bridge:
                return {}
            return self._bridge.get_metrics()

        @app.post("/route")
        async def route(req: RouteRequest):
            if not self._router:
                return JSONResponse({"error": "engine_not_built"}, status_code=503)

            from hybrid_engine.routing.bottleneck import TaskPriority
            priority = TaskPriority[req.priority.upper()] if req.priority.upper() in TaskPriority.__members__ else TaskPriority.NORMAL

            if req.pipeline:
                result = await self._router.run_pipeline(req.pipeline, req.prompt, req.session_id)
            else:
                result = await self._router.route(req.prompt, req.session_id, priority, req.hints)

            return result

        @app.websocket("/ws/comms")
        async def ws_comms(websocket: WebSocket):
            """WebSocket endpoint: stream all comms hub events to the client."""
            await websocket.accept()
            if not self._comms:
                await websocket.close()
                return
            q = self._comms.add_ws_connection()
            try:
                async for msg_json in self._comms.ws_stream(q):
                    await websocket.send_text(msg_json)
            except WebSocketDisconnect:
                pass
            finally:
                self._comms.remove_ws_connection(q)

        @app.get("/comms/history")
        async def comms_history(topic: Optional[str] = None, limit: int = 50):
            if not self._comms:
                return []
            return self._comms.get_history(topic=topic, limit=limit)

        @app.get("/comms/stats")
        async def comms_stats():
            if not self._comms:
                return {}
            return self._comms.get_stats()

        return app

    # ── Health monitor ────────────────────────────────────────────────────────
    async def _health_monitor(self):
        """Periodically check all client health and publish to comms hub."""
        while True:
            await asyncio.sleep(self.config.health_check_interval)
            if not self._bridge:
                continue
            try:
                checks = await self._bridge.health_check_all()
                for client_name, is_healthy in checks.items():
                    if self._comms:
                        await self._comms.emit_client_status(client_name, is_healthy)
                    status = "✓" if is_healthy else "✗"
                    logger.debug(f"[Health] {status} {client_name}")
            except Exception as e:
                logger.error(f"[Health Monitor] Error: {e}")

    # ── CLI ───────────────────────────────────────────────────────────────────
    async def run_cli(self):
        """Interactive CLI for the hybrid engine."""
        if not self._built:
            await self.build()

        print("\n" + "=" * 60)
        print("  HYBRID ENGINE CLI — ARK95X")
        print("  Commands: route, pipeline, status, health, quit")
        print("=" * 60 + "\n")

        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("hybrid> ").strip()
                )
            except (EOFError, KeyboardInterrupt):
                break

            if not line:
                continue

            parts = line.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("quit", "exit", "q"):
                break
            elif cmd == "route":
                result = await self._router.route(arg)
                print(f"\n[{result.get('routed_via', '?')}] {result.get('response', result.get('answer', result))}\n")
            elif cmd == "pipeline":
                sub = arg.split(None, 1)
                pipeline_name = sub[0] if sub else "research_and_code"
                prompt = sub[1] if len(sub) > 1 else "Tell me about AI"
                result = await self._router.run_pipeline(pipeline_name, prompt)
                print(f"\n[Pipeline: {pipeline_name}]\n{result.get('final_output', result)}\n")
            elif cmd == "status":
                import json
                print(json.dumps(self._router.get_status(), indent=2))
            elif cmd == "health":
                checks = await self._bridge.health_check_all()
                for name, ok in checks.items():
                    print(f"  {'✓' if ok else '✗'} {name}")
            elif cmd == "pipelines":
                for p in self._router.list_pipelines():
                    print(f"  {p['name']}: {p['description']}")
            else:
                print(f"Unknown command: {cmd}")

        await self.shutdown()

    # ── Serve ─────────────────────────────────────────────────────────────────
    async def serve(self):
        """Build the engine and start the FastAPI server."""
        if not self._built:
            await self.build()

        try:
            import uvicorn
        except ImportError:
            logger.error("uvicorn not installed. Run: pip install uvicorn")
            return

        app = self.build_api()
        if not app:
            return

        config = uvicorn.Config(
            app,
            host=self.config.engine_host,
            port=self.config.engine_port,
            log_level=self.config.log_level.lower(),
        )
        server = uvicorn.Server(config)

        # Handle shutdown signals
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        await server.serve()

    # ── Shutdown ──────────────────────────────────────────────────────────────
    async def shutdown(self):
        """Gracefully shut down the entire hybrid engine."""
        logger.info("[Engine] Shutting down...")

        if self._health_task:
            self._health_task.cancel()

        if self._bridge:
            await self._bridge.stop()

        if self._comms:
            await self._comms.stop()

        for name, client in self._clients.items():
            if hasattr(client, "close"):
                try:
                    await client.close()
                    logger.info(f"  ✓ {name} closed")
                except Exception as e:
                    logger.warning(f"  ✗ {name} close error: {e}")

        logger.info("[Engine] Shutdown complete")

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def router(self) -> Optional[Any]:
        return self._router

    @property
    def bridge(self) -> Optional[Any]:
        return self._bridge

    @property
    def comms(self) -> Optional[Any]:
        return self._comms

    @property
    def clients(self) -> Dict[str, Any]:
        return self._clients
