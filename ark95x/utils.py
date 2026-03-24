from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_timestamp(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now().strftime(fmt)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return {} if default is None else default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def validate_simple_schema(payload: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for key in required:
        if key not in payload:
            errors.append(f"Missing required key: {key}")

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    for key, rules in properties.items():
        if key not in payload:
            continue
        expected = rules.get("type")
        if expected and expected in type_map and not isinstance(payload[key], type_map[expected]):
            errors.append(f"Key '{key}' expected {expected}, got {type(payload[key]).__name__}")

    return (len(errors) == 0, errors)
