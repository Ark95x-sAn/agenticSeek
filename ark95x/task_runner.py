from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .utils import utc_timestamp

TaskCallable = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class TaskResult:
    task_name: str
    success: bool
    attempts: int
    started_at: str
    finished_at: str
    result: Any = None
    error: str = ""


class AsyncTaskRunner:
    def __init__(self, retries: int = 3, backoff_seconds: float = 0.5) -> None:
        self.retries = max(1, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)

    async def run(self, task_name: str, fn: TaskCallable, *args: Any, **kwargs: Any) -> TaskResult:
        started_at = utc_timestamp()
        last_err = ""

        for attempt in range(1, self.retries + 1):
            try:
                value = await fn(*args, **kwargs)
                return TaskResult(
                    task_name=task_name,
                    success=True,
                    attempts=attempt,
                    started_at=started_at,
                    finished_at=utc_timestamp(),
                    result=value,
                )
            except Exception as exc:
                last_err = str(exc)
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff_seconds * attempt)

        return TaskResult(
            task_name=task_name,
            success=False,
            attempts=self.retries,
            started_at=started_at,
            finished_at=utc_timestamp(),
            error=last_err,
        )
