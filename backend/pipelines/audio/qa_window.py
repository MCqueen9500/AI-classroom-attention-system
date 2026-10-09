"""
pipelines/audio/qa_window.py
==============================
15-Second Q&A Response Window State Machine.

States:
  IDLE              → waiting for teacher to address a student
  QUESTION_CAPTURED → teacher said a roll number + question
  WAITING           → 15-second countdown for student response
  SCORING           → student spoke; LLM scoring in progress
  DONE              → window closed, Q_i written to DB

Transitions:
  IDLE        → QUESTION_CAPTURED  : roll number detected in teacher speech
  WAITING     → SCORING            : student speech detected within 15s
  WAITING     → DONE (Q_i=1.0)    : teacher interrupts (safeguard)
  WAITING     → DONE (Q_i=0.0)    : 15s timeout with no response
  SCORING     → DONE               : LLM returns Q_i score
"""

import time
import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class WindowState(Enum):
    IDLE              = auto()
    QUESTION_CAPTURED = auto()
    WAITING           = auto()
    SCORING           = auto()
    DONE              = auto()


@dataclass
class QAInteractionRecord:
    """Complete record of one Q&A interaction."""
    roll_no:           int
    question_text:     str
    student_answer:    str  = ""
    teacher_reaction:  str  = ""
    Q_i:               float = 0.0
    score_reason:      str  = ""
    score_method:      str  = ""  # "llm" | "keyword" | "timeout" | "interrupted"
    window_open_time:  float = 0.0
    window_close_time: float = 0.0

    @property
    def response_latency_s(self) -> float:
        if self.window_open_time and self.window_close_time:
            return round(self.window_close_time - self.window_open_time, 2)
        return 0.0


class QAWindowManager:
    """
    Manages the 15-second response window lifecycle.

    Usage:
        mgr = QAWindowManager(window_duration=15.0, on_complete=my_callback)
        mgr.on_question_detected(roll_no=14, question="what is EAR?")
        mgr.on_speech_segment(text, is_teacher=False)   # call every new transcription
        mgr.tick()   # call every loop iteration to check timeout
    """

    def __init__(
        self,
        window_duration: float = 15.0,
        on_complete: Optional[Callable[[QAInteractionRecord], None]] = None,
        llm_scorer=None,
    ):
        self._duration    = window_duration
        self._on_complete = on_complete
        self._llm         = llm_scorer

        self._state:   WindowState = WindowState.IDLE
        self._record:  Optional[QAInteractionRecord] = None
        self._open_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public API — called by AudioPipeline
    # ------------------------------------------------------------------

    def on_question_detected(self, roll_no: int, question: str):
        """Teacher addressed a student. Open the response window."""
        if self._state != WindowState.IDLE:
            logger.warning(
                "QAWindow: New question while window is %s — resetting.", self._state
            )

        self._record = QAInteractionRecord(
            roll_no=roll_no,
            question_text=question,
            window_open_time=time.time(),
        )
        self._open_ts = time.time()
        self._state   = WindowState.WAITING

        logger.info(
            "QAWindow: OPEN — Roll %d | Q: '%s' | Waiting %.0fs...",
            roll_no, question, self._duration
        )

    def on_speech_segment(self, text: str, is_teacher: bool):
        """
        Feed a new transcribed speech segment.

        Args:
            text       : transcribed text
            is_teacher : True if this is teacher speech, False if student
        """
        if self._state == WindowState.IDLE:
            return   # window not open, ignore

        if self._state == WindowState.WAITING:
            if is_teacher:
                # Teacher interrupted → safeguard → auto Q_i = 1.0
                if self._record:
                    self._record.teacher_reaction  = text
                    self._record.Q_i              = 1.0
                    self._record.score_reason     = "teacher interrupted before window closed"
                    self._record.score_method     = "interrupted"
                    roll = self._record.roll_no
                    self._close()
                    logger.info("QAWindow: TEACHER INTERRUPTED — Roll %d auto Q_i=1.0", roll)
            else:
                # Student responded — capture answer, move to scoring
                self._record.student_answer     = text
                self._record.window_close_time  = time.time()
                self._state = WindowState.SCORING
                logger.info(
                    "QAWindow: Student answered: '%s'", text[:80]
                )
                self._score_answer()

        elif self._state == WindowState.SCORING:
            # Teacher reaction comes after student answer
            if is_teacher:
                self._record.teacher_reaction = text
                logger.info("QAWindow: Teacher reaction captured: '%s'", text[:60])

    def tick(self):
        """
        Call this every loop iteration.
        Checks if the 15-second window has expired with no response.
        """
        if self._state != WindowState.WAITING:
            return

        elapsed = time.time() - self._open_ts
        remaining = self._duration - elapsed

        # Periodically push remaining seconds to dashboard (every ~1s)
        if int(remaining) != getattr(self, '_last_pushed_second', -1):
            self._last_pushed_second = int(remaining)
            self._push_telemetry(
                active=True,
                roll=self._record.roll_no if self._record else None,
                question=self._record.question_text if self._record else None,
                seconds=max(0.0, remaining),
            )

        if elapsed >= self._duration:
            self._record.Q_i          = 0.0
            self._record.score_reason = f"no response in {self._duration:.0f}s"
            self._record.score_method = "timeout"
            self._record.window_close_time = time.time()
            logger.info(
                "QAWindow: TIMEOUT — Roll %d no response → Q_i=0.0",
                self._record.roll_no
            )
            self._close()

    def _push_telemetry(self, active: bool, roll=None, question=None, seconds=0.0):
        """Fire-and-forget HTTP push to dashboard."""
        import threading
        import requests as req
        def _post():
            try:
                req.post(
                    "http://127.0.0.1:8000/api/telemetry/audio",
                    json={"qa_active": active, "qa_asked_roll": roll,
                          "qa_question": question, "qa_seconds": seconds},
                    timeout=1,
                )
            except Exception:
                pass
        threading.Thread(target=_post, daemon=True).start()



    @property
    def state(self) -> WindowState:
        return self._state

    @property
    def is_waiting(self) -> bool:
        return self._state == WindowState.WAITING

    @property
    def seconds_remaining(self) -> float:
        if self._state != WindowState.WAITING:
            return 0.0
        return max(0.0, self._duration - (time.time() - self._open_ts))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _score_answer(self):
        """Run LLM scoring (or fallback) and then close window."""
        if self._llm and self._record:
            score, reason, method = self._llm.score(
                question=self._record.question_text,
                student_answer=self._record.student_answer,
                teacher_reaction=self._record.teacher_reaction,
            )
            self._record.Q_i          = score
            self._record.score_reason = reason
            self._record.score_method = method
        else:
            # No LLM — binary: answered = 1.0
            self._record.Q_i          = 1.0
            self._record.score_reason = "answered (no LLM scorer)"
            self._record.score_method = "binary"

        self._close()

    def _close(self):
        """Finalize the window and fire the on_complete callback."""
        if self._record.window_close_time == 0.0:
            self._record.window_close_time = time.time()

        record = self._record
        self._state  = WindowState.DONE

        logger.info(
            "QAWindow: CLOSED — Roll %d | Q_i=%.2f | method=%s | '%s'",
            record.roll_no, record.Q_i, record.score_method, record.score_reason
        )

        if self._on_complete:
            try:
                self._on_complete(record)
            except Exception as e:
                logger.warning("QAWindow: on_complete callback error: %s", e)

        # Clear Q&A panel on dashboard
        self._push_telemetry(active=False)

        self._state  = WindowState.IDLE
        self._record = None
