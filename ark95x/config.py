from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(slots=True)
class AppConfig:
    environment: str
    data_root: Path
    state_dir: Path
    logs_dir: Path
    sync_state_file: Path
    revenue_state_file: Path
    openai_api_key: str
    anthropic_api_key: str
    perplexity_api_key: str
    omni_webhook_ingest_url: str
    omni_webhook_secret: str

    @property
    def provider_key_map(self) -> dict[str, str]:
        return {
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "perplexity": self.perplexity_api_key,
        }

    @property
    def configured_providers(self) -> list[str]:
        return [name for name, key in self.provider_key_map.items() if key]


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default
    return Path(value).expanduser().resolve()


def load_config(dotenv_path: str | None = None) -> AppConfig:
    load_dotenv(dotenv_path=dotenv_path)

    project_root = Path(__file__).resolve().parents[1]
    env = os.getenv("ARK95X_ENV", "cloud").strip().lower()
    default_data_root = project_root if env == "cloud" else Path.home() / "ark95x"

    data_root = _resolve_path(os.getenv("ARK95X_DATA_ROOT", ""), default_data_root)
    state_dir = _resolve_path(os.getenv("ARK95X_STATE_DIR", ""), data_root / "state")
    logs_dir = _resolve_path(os.getenv("ARK95X_LOGS_DIR", ""), data_root / "logs")

    state_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    sync_state_file = _resolve_path(
        os.getenv("ARK95X_SYNC_STATE_FILE", ""), state_dir / "emerald_sync_state.json"
    )
    revenue_state_file = _resolve_path(
        os.getenv("ARK95X_REVENUE_STATE_FILE", ""), state_dir / "revenue_state.json"
    )

    return AppConfig(
        environment=env,
        data_root=data_root,
        state_dir=state_dir,
        logs_dir=logs_dir,
        sync_state_file=sync_state_file,
        revenue_state_file=revenue_state_file,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", "").strip(),
        omni_webhook_ingest_url=os.getenv("OMNI_WEBHOOK_INGEST_URL", "").strip(),
        omni_webhook_secret=os.getenv("OMNI_WEBHOOK_SECRET", "").strip(),
    )
