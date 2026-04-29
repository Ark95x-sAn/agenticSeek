"""Client adapters for each AI tool in the hybrid stack."""
from hybrid_engine.clients.openclaw_client import OpenClawClient
from hybrid_engine.clients.blackbox_client import BlackBoxDesktopClient
from hybrid_engine.clients.ollama_client import OllamaClient
from hybrid_engine.clients.comet_client import CometPerplexityClient
from hybrid_engine.clients.copilot_client import CopilotClient

__all__ = [
    "OpenClawClient",
    "BlackBoxDesktopClient",
    "OllamaClient",
    "CometPerplexityClient",
    "CopilotClient",
]
