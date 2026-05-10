import time
from collections import defaultdict, deque
from typing import DefaultDict, Deque

from fastapi import HTTPException


class RateLimiter:
    """Small in-memory limiter for the packaged single-process app."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._attempts: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        attempts = self._attempts[key]
        while attempts and now - attempts[0] > self._window_seconds:
            attempts.popleft()
        if len(attempts) >= self._max_attempts:
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please wait and try again.",
            )

    def record_failure(self, key: str) -> None:
        self._attempts[key].append(time.monotonic())

    def clear(self, key: str) -> None:
        self._attempts.pop(key, None)

