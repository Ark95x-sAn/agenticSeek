#!/usr/bin/env python3
"""
hybrid_engine_main.py — ARK95X Hybrid Engine Entry Point
==========================================================
The single command to build and run the entire hybrid AI engine.

Usage:
  python hybrid_engine_main.py serve      # Start API server (port 8765)
  python hybrid_engine_main.py cli        # Interactive CLI
  python hybrid_engine_main.py route "your prompt here"
  python hybrid_engine_main.py pipeline research_and_code "your topic"
  python hybrid_engine_main.py health     # Check all client health
  python hybrid_engine_main.py status     # Show engine status
  python hybrid_engine_main.py overlay    # Launch Windows overlay only

Environment variables (see .env.example for full list):
  OPENCLAW_URL        = http://localhost:8080
  BLACKBOX_URL        = http://localhost:3000
  OLLAMA_URL          = http://localhost:11434
  OLLAMA_MODEL        = llama3:8b
  PERPLEXITY_API_KEY  = pplx-...
  GITHUB_TOKEN        = ghp_...
  ENGINE_PORT         = 8765
  ENABLE_OVERLAY      = false
"""

from __future__ import annotations

import asyncio
import json
import sys

from hybrid_engine.deployment.engine_builder import EngineBuilder, EngineConfig


async def cmd_serve(config: EngineConfig):
    engine = EngineBuilder(config)
    await engine.serve()


async def cmd_cli(config: EngineConfig):
    engine = EngineBuilder(config)
    await engine.run_cli()


async def cmd_route(config: EngineConfig, prompt: str):
    engine = EngineBuilder(config)
    await engine.build()
    result = await engine.router.route(prompt)
    print(json.dumps(result, indent=2, default=str))
    await engine.shutdown()


async def cmd_pipeline(config: EngineConfig, pipeline_name: str, prompt: str):
    engine = EngineBuilder(config)
    await engine.build()
    result = await engine.router.run_pipeline(pipeline_name, prompt)
    print(json.dumps(result, indent=2, default=str))
    await engine.shutdown()


async def cmd_health(config: EngineConfig):
    engine = EngineBuilder(config)
    await engine.build()
    checks = await engine.bridge.health_check_all()
    print("\nHybrid Engine — Client Health")
    print("=" * 40)
    for name, ok in checks.items():
        icon = "✓" if ok else "✗"
        print(f"  {icon}  {name}")
    print()
    await engine.shutdown()


async def cmd_status(config: EngineConfig):
    engine = EngineBuilder(config)
    await engine.build()
    status = engine.router.get_status()
    print(json.dumps(status, indent=2))
    await engine.shutdown()


def cmd_overlay():
    from hybrid_engine.deployment.windows_overlay import OverlayWindow
    overlay = OverlayWindow()
    overlay.run()


def main():
    args = sys.argv[1:]
    config = EngineConfig.from_env()

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "serve":
        asyncio.run(cmd_serve(config))

    elif cmd == "cli":
        asyncio.run(cmd_cli(config))

    elif cmd == "route":
        prompt = " ".join(args[1:]) if len(args) > 1 else "Hello, hybrid engine!"
        asyncio.run(cmd_route(config, prompt))

    elif cmd == "pipeline":
        pipeline_name = args[1] if len(args) > 1 else "research_and_code"
        prompt = " ".join(args[2:]) if len(args) > 2 else "Explain AI"
        asyncio.run(cmd_pipeline(config, pipeline_name, prompt))

    elif cmd == "health":
        asyncio.run(cmd_health(config))

    elif cmd == "status":
        asyncio.run(cmd_status(config))

    elif cmd == "overlay":
        cmd_overlay()

    else:
        print(f"Unknown command: {cmd}")
        print("Run with --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
