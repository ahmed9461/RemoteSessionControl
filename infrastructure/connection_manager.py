from __future__ import annotations

import asyncio

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, device_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            old = self._connections.get(device_id)
            self._connections[device_id] = websocket
        if old and old is not websocket:
            try:
                await old.close(code=4001, reason="replaced by newer connection")
            except Exception:
                pass

    async def disconnect(self, device_id: str, websocket: WebSocket | None = None) -> None:
        async with self._lock:
            current = self._connections.get(device_id)
            if current is not None and (websocket is None or current is websocket):
                self._connections.pop(device_id, None)

    async def send_json(self, device_id: str, payload: dict) -> bool:
        async with self._lock:
            websocket = self._connections.get(device_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except Exception:
            await self.disconnect(device_id, websocket)
            return False

    async def close_device(self, device_id: str, *, code: int = 4000, reason: str = "session ended") -> None:
        async with self._lock:
            websocket = self._connections.pop(device_id, None)
        if websocket:
            try:
                await websocket.send_json({"type": "session_ended", "reason": reason})
                await websocket.close(code=code, reason=reason)
            except Exception:
                pass


manager = ConnectionManager()
