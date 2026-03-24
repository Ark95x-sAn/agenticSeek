"""ARK95X Master Engine — production-grade multi-agent orchestration."""
__version__ = '0.3.0'
from .config import AppConfig as ARK95XConfig
from .ark95x_omni import Ark95xOmniOrchestrator as ARK95XOrchestrator, CometBridge
from .task_runner import AsyncTaskRunner as TaskRunner
from .emerald_sync import EmeraldSyncEngine as EmeraldSync
from .n95_revenue import RevenueIntelligence as N95RevenueTracker
__all__ = ['ARK95XConfig', 'ARK95XOrchestrator', 'TaskRunner', 'EmeraldSync', 'N95RevenueTracker', 'CometBridge', '__version__']