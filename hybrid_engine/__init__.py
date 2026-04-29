"""
HYBRID ENGINE — ARK95X Integration Layer
=========================================
Connects: OpenClaw · BlackBox Desktop · Ollama · Comet (Perplexity) · GitHub Copilot
Routing: Intelligent bottleneck bridge with load balancing, failover, and comms layer
Wrapper: Windows OS / Copilot shell overlay
"""

from hybrid_engine.routing.router import HybridRouter
from hybrid_engine.routing.bottleneck import BottleneckBridge
from hybrid_engine.comms.hub import CommsHub
from hybrid_engine.deployment.engine_builder import EngineBuilder

__all__ = ["HybridRouter", "BottleneckBridge", "CommsHub", "EngineBuilder"]
__version__ = "1.0.0"
