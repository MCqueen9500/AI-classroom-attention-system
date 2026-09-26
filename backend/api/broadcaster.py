"""
backend/api/broadcaster.py
=============================
WebSocket Connection Manager + Broadcaster.

Manages all connected WebSocket clients (teacher dashboard tabs).
Broadcasts the live telemetry snapshot every 500ms to all clients.

Connection management:
  - connect(ws)    → adds client
  - disconnect(ws) → removes client
  - broadcast(msg) → sends JSON to ALL connected clients safely

Broadcasting runs in a background asyncio task.
Dead connections are silently removed.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Set

from fastapi import WebSocket
from api.pipeline_state import pipeline_state
from core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts telemetry."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info(
            "WebSocket: Client connected. Total: %d", len(self._connections)
        )

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections.discard(ws)
        logger.info(
            "WebSocket: Client disconnected. Total: %d", len(self._connections)
        )

    async def broadcast(self, message: dict):
        """Send JSON message to all connected clients. Dead connections auto-removed."""
        if not self._connections:
            return

        payload = json.dumps(message)
        dead    = set()

        async with self._lock:
            clients = set(self._connections)

        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead
            logger.info(
                "WebSocket: Removed %d dead connections.", len(dead)
            )

    async def send_alert(self, alert_type: str, roll_no: int = None, detail: str = ""):
        """Send an immediate alert message to all clients (not waiting for next tick)."""
        msg = {
            "type":       "alert",
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "alert_type": alert_type,
            "roll_no":    roll_no,
            "detail":     detail,
        }
        await self.broadcast(msg)

    @property
    def client_count(self) -> int:
        return len(self._connections)


# Singleton
manager = ConnectionManager()


async def broadcast_loop():
    """
    Background asyncio task.
    Reads pipeline_state snapshot every 500ms → broadcasts to all WebSocket clients.

    This is the "heartbeat" of the real-time dashboard.
    """
    interval = settings.ws_broadcast_interval_ms / 1000.0   # 500ms → 0.5s
    logger.info("WebSocket: Broadcast loop started (%.0fms interval)", interval * 1000)

    while True:
        await asyncio.sleep(interval)

        if manager.client_count == 0:
            continue   # no clients → skip snapshot

        try:
            snapshot = pipeline_state.snapshot()
            snapshot["type"]      = "telemetry"
            snapshot["timestamp"] = datetime.now(timezone.utc).isoformat()
            await manager.broadcast(snapshot)
        except Exception as e:
            logger.warning("WebSocket: Broadcast error: %s", e)
