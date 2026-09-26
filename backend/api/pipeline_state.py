"""
backend/api/pipeline_state.py
================================
Shared in-memory state between Vision/Audio pipelines and the FastAPI server.

The pipelines write into this state each frame.
The WebSocket broadcaster reads from it every 500ms and sends to all clients.

Think of this as the "live dashboard data buffer" — a single source of truth
for what is happening in the classroom RIGHT NOW.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class LiveFaceState:
    roll_no:    int
    slot:       int
    h_i:        float = 0.0
    g_i:        float = 0.0
    p_i:        float = 0.0
    a_i:        float = 0.0
    is_drowsy:  bool  = False
    is_speaking: bool = False
    confidence: float = 0.0
    bbox:       List[int] = field(default_factory=lambda: [0, 0, 0, 0])


@dataclass
class LiveQAState:
    active:            bool  = False
    asked_roll:        Optional[int] = None
    question_text:     Optional[str] = None
    seconds_remaining: float = 0.0
    speaker_roll:      Optional[int] = None
    wrong_student:     bool  = False


class PipelineState:
    """
    Thread-safe shared state.

    Vision pipeline writes:   update_faces(), update_qa_window()
    Audio pipeline writes:    update_qa_window(), add_alert()
    WebSocket reads:          snapshot()
    """

    def __init__(self):
        self._lock = threading.Lock()

        # Live classroom state
        self._session_id:          str            = ""
        self._faces:               List[LiveFaceState] = []
        self._class_attention_pct: float          = 0.0
        self._is_paused:           bool           = False
        self._qa:                  LiveQAState    = LiveQAState()
        self._alerts:              List[str]      = []
        self._last_update:         float          = time.time()

    # ------------------------------------------------------------------
    # Write methods (called by pipelines)
    # ------------------------------------------------------------------

    def set_session(self, session_id: str):
        with self._lock:
            self._session_id = session_id

    def update_faces(
        self,
        faces: List[LiveFaceState],
        class_attention_pct: float,
    ):
        with self._lock:
            self._faces               = faces
            self._class_attention_pct = class_attention_pct
            self._last_update         = time.time()

    def update_qa_window(self, qa: LiveQAState):
        with self._lock:
            self._qa = qa

    def set_paused(self, paused: bool):
        with self._lock:
            self._is_paused = paused

    def add_alert(self, alert: str):
        with self._lock:
            self._alerts.append(alert)
            # Keep only last 10 alerts in buffer
            if len(self._alerts) > 10:
                self._alerts.pop(0)

    def clear_alerts(self):
        with self._lock:
            self._alerts.clear()

    # ------------------------------------------------------------------
    # Read methods (called by WebSocket broadcaster)
    # ------------------------------------------------------------------

    def snapshot(self) -> dict:
        """Return a complete snapshot of current state as a dict."""
        with self._lock:
            alerts = list(self._alerts)
            self._alerts.clear()   # consume alerts after reading

            return {
                "session_id":          self._session_id,
                "class_attention_pct": round(self._class_attention_pct, 2),
                "face_count":          len(self._faces),
                "is_paused":           self._is_paused,
                "faces": [
                    {
                        "roll_no":     f.roll_no,
                        "slot":        f.slot,
                        "h_i":         round(f.h_i, 3),
                        "g_i":         round(f.g_i, 3),
                        "p_i":         round(f.p_i, 3),
                        "a_i":         round(f.a_i, 3),
                        "is_drowsy":   f.is_drowsy,
                        "is_speaking": f.is_speaking,
                        "confidence":  round(f.confidence, 3),
                        "bbox":        f.bbox,
                    }
                    for f in self._faces
                ],
                "qa_window": {
                    "active":            self._qa.active,
                    "asked_roll":        self._qa.asked_roll,
                    "question_text":     self._qa.question_text,
                    "seconds_remaining": round(self._qa.seconds_remaining, 1),
                    "speaker_roll":      self._qa.speaker_roll,
                    "wrong_student":     self._qa.wrong_student,
                },
                "alerts": alerts,
            }


# Singleton — import this everywhere
pipeline_state = PipelineState()
