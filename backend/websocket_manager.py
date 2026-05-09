import json
import secrets
import threading
import time
from typing import Any

from fastapi import WebSocket


class TicketStore:
    """One-time use tickets for WebSocket auth so JWTs never appear in server logs.
    Thread-safe: FastAPI threadpool (issue/consume) and the asyncio event loop
    may access this concurrently, so all mutations hold a Lock."""

    def __init__(self, ttl: int = 30) -> None:
        self._tickets: dict[str, float] = {}
        self._ttl = ttl
        self._lock = threading.Lock()

    def issue(self) -> str:
        with self._lock:
            self._cleanup_locked()
            ticket = secrets.token_hex(32)
            self._tickets[ticket] = time.time() + self._ttl
            return ticket

    def consume(self, ticket: str) -> bool:
        with self._lock:
            expiry = self._tickets.pop(ticket, None)
            return expiry is not None and time.time() < expiry

    def _cleanup_locked(self) -> None:
        """Prune expired tickets. Must be called while holding self._lock."""
        now = time.time()
        self._tickets = {t: e for t, e in self._tickets.items() if e > now}


class ConnectionManager:

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        payload = json.dumps(message, default=str)
        for conn in self._connections.copy():
            try:
                await conn.send_text(payload)
            except Exception:
                self.disconnect(conn)

    @property
    def active_count(self) -> int:
        return len(self._connections)
