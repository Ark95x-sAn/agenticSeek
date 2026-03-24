from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .utils import read_json, sha256_file, utc_timestamp, write_json


@dataclass(slots=True)
class SyncResult:
    scanned_files: int
    added: int
    modified: int
    deleted: int
    state_file: str


class EmeraldSyncEngine:
    def __init__(self, config: AppConfig, include_globs: list[str] | None = None) -> None:
        self.config = config
        self.include_globs = include_globs or ["**/*.py", "**/*.md", "**/*.json", "**/*.yaml", "**/*.yml"]

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        root = self.config.data_root
        snapshot: dict[str, dict[str, Any]] = {}

        for pattern in self.include_globs:
            for p in root.glob(pattern):
                if not p.is_file():
                    continue
                if self.config.state_dir in p.parents:
                    continue
                rel = str(p.relative_to(root))
                stat = p.stat()
                snapshot[rel] = {
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                    "sha256": sha256_file(p),
                }
        return snapshot

    def sync(self) -> dict[str, Any]:
        old_state = read_json(self.config.sync_state_file, default={"files": {}})
        old_files = old_state.get("files", {})
        new_files = self._snapshot()

        old_keys = set(old_files.keys())
        new_keys = set(new_files.keys())

        added = sorted(new_keys - old_keys)
        deleted = sorted(old_keys - new_keys)
        modified = sorted(
            k for k in (old_keys & new_keys) if old_files[k].get("sha256") != new_files[k].get("sha256")
        )

        state_payload = {
            "updated_at": utc_timestamp(),
            "root": str(self.config.data_root),
            "files": new_files,
            "delta": {
                "added": added,
                "modified": modified,
                "deleted": deleted,
            },
        }
        write_json(self.config.sync_state_file, state_payload)

        return {
            "scanned_files": len(new_files),
            "added": len(added),
            "modified": len(modified),
            "deleted": len(deleted),
            "delta": state_payload["delta"],
            "state_file": str(self.config.sync_state_file),
        }
