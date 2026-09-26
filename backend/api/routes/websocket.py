"""
backend/api/routes/websocket.py
=================================
WebSocket endpoint — /ws/{session_id}

The teacher dashboard connects here to receive live telemetry every 500ms.

Message format sent to dashboard:
{
  "type": "telemetry",
  "timestamp": "2026-09-26T21:51:00Z",
  "session_id": "abc-123",
  "class_attention_pct": 78.5,
  "face_count": 12,
  "is_paused": false,
  "faces": [
    {"roll_no": 14, "slot": 0, "h_i": 0.8, "g_i": 1.0, "p_i": 0.9,
     "a_i": 0.92, "is_drowsy": false, "is_speaking": false,
     "confidence": 0.95, "bbox": [120, 80, 100, 120]}
  ],
  "qa_window": {
    "active": true,
    "asked_roll": 14,
    "question_text": "what is EAR formula",
    "seconds_remaining": 8.3,
    "speaker_roll": 7,
    "wrong_student": true
  },
  "alerts": ["WRONG_STUDENT: Roll 7 answering for Roll 14"]
}
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.broadcaster import manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    """
    Teacher dashboard connects here.
    Connection stays alive — telemetry is pushed every 500ms by the broadcast_loop.
    """
    await manager.connect(ws)
    logger.info("WebSocket: Dashboard connected for session %s", session_id)
    try:
        # Keep connection alive — wait for client to disconnect
        while True:
            # Optionally receive commands from dashboard (pause, resume, etc.)
            data = await ws.receive_text()
            logger.debug("WebSocket: Received from client: %s", data)
    except WebSocketDisconnect:
        logger.info("WebSocket: Dashboard disconnected (session %s)", session_id)
    finally:
        await manager.disconnect(ws)
