"""
Bridge adapters — protocol translation between AI tools.
Each bridge handles the impedance mismatch between two specific tools.
"""
from hybrid_engine.bridges.ollama_openclaw_bridge import OllamaOpenClawBridge
from hybrid_engine.bridges.copilot_blackbox_bridge import CopilotBlackBoxBridge
from hybrid_engine.bridges.comet_ollama_bridge import CometOllamaBridge

__all__ = ["OllamaOpenClawBridge", "CopilotBlackBoxBridge", "CometOllamaBridge"]
