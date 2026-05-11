import json
import secrets
import threading
import time
from typing import Any, Optional

from fastapi import WebSocket


class TicketStore:
    """One-time WebSocket tickets carrying authenticated user context."""

    def __init__(self, ttl: int = 30) -> None:
        self._tickets: dict[str, tuple[float, dict[str, Any]]] = {}
        self._ttl = ttl
        self._lock = threading.Lock()

    def issue(self, user_info: dict[str, Any]) -> str:
        with self._lock:
            self._cleanup_locked()
            ticket = secrets.token_hex(32)
            self._tickets[ticket] = (time.time() + self._ttl, dict(user_info))
            return ticket

    def consume(self, ticket: str) -> Optional[dict[str, Any]]:
        with self._lock:
            self._cleanup_locked()
            data = self._tickets.pop(ticket, None)
            if data is None:
                return None
            expiry, user_info = data
            if time.time() >= expiry:
                return None
            return user_info

    def _cleanup_locked(self) -> None:
        now = time.time()
        self._tickets = {
            ticket: data
            for ticket, data in self._tickets.items()
            if data[0] > now
        }


class ConnectionManager:
    """Role-aware and user-aware WebSocket connection manager."""

    def __init__(self) -> None:
        self._connections: list[tuple[WebSocket, dict[str, Any]]] = []

    async def connect(self, websocket: WebSocket, user_info: dict[str, Any]) -> None:
        await websocket.accept()
        self._connections.append((websocket, dict(user_info)))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections = [
            (ws, info) for ws, info in self._connections if ws != websocket
        ]

    async def broadcast(self, message: dict[str, Any]) -> None:
        await self._send_to(
            message,
            lambda _info: True,
        )

    async def broadcast_to_role(self, role: str, message: dict[str, Any]) -> None:
        await self._send_to(
            message,
            lambda info: info.get("role") == role,
        )

    async def broadcast_to_roles(self, roles: list[str], message: dict[str, Any]) -> None:
        role_set = set(roles)
        await self._send_to(
            message,
            lambda info: info.get("role") in role_set,
        )

    async def broadcast_to_user(self, user_id: int, message: dict[str, Any]) -> None:
        await self._send_to(
            message,
            lambda info: int(info.get("user_id") or 0) == int(user_id),
        )

    async def _send_to(self, message: dict[str, Any], predicate) -> None:
        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for websocket, info in self._connections.copy():
            if not predicate(info):
                continue
            try:
                await websocket.send_text(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(websocket)

    @property
    def active_count(self) -> int:
        return len(self._connections)
