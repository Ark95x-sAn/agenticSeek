from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
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


def setup_logging(log_level: str, logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("ark95x")
    logger.setLevel(getattr(logging, (log_level or "INFO").upper(), logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    file_handler = RotatingFileHandler(
        logs_dir / "ark95x.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def validate_json_schema(data: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for key in required:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    type_map: dict[str, Any] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }

    for key, rules in properties.items():
        if key not in data:
            continue

        expected = rules.get("type")
        if not expected:
            continue

        accepted_types = expected if isinstance(expected, list) else [expected]
        if not any(
            t in type_map and isinstance(data[key], type_map[t]) for t in accepted_types
        ):
            errors.append(
                f"Key '{key}' expected type {accepted_types}, got {type(data[key]).__name__}"
            )

    return (len(errors) == 0, errors)


def validate_simple_schema(payload: dict[str, Any], schema: dict[str, Any]) -> tuple[bool, list[str]]:
    return validate_json_schema(payload, schema)


def safe_serialize(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, Path):
        return str(obj)

    if is_dataclass(obj):
        return safe_serialize(asdict(obj))

    if isinstance(obj, dict):
        return {str(k): safe_serialize(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [safe_serialize(item) for item in obj]

    return str(obj)
