"""Diffusion temps réel (WebSocket) vers l'interface web."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

log = logging.getLogger("localsms.events")


class Hub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def count(self) -> int:
        return len(self._clients)

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, event: dict[str, Any]) -> None:
        if not self._clients:
            return
        payload = json.dumps(event, ensure_ascii=False)
        results = await asyncio.gather(
            *(self._send(ws, payload) for ws in list(self._clients)), return_exceptions=True
        )
        for ws, res in zip(list(self._clients), results):
            if res is not None:
                self._clients.discard(ws)

    @staticmethod
    async def _send(ws: WebSocket, payload: str) -> None:
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=5)
        except Exception as exc:  # client déconnecté ou trop lent
            return exc  # type: ignore[return-value]
        return None
