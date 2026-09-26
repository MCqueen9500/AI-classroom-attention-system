"""
pipelines/audio/audio_pipeline.py
=====================================
Main Audio Pipeline Orchestrator — Phase 4.

Connects all audio components end-to-end:
  AudioSourceManager (HAL)
    → EnergyVAD       (speech detection)
    → WhisperTranscriber (speech-to-text)
    → RollDetector    (who is the teacher addressing?)
    → QAWindowManager (15s response window state machine)
    → LLMAnswerScorer (local Ollama quality score)
    → DB log          (log_qa_interaction in crud.py)

Speaker classification (single microphone):
  - Default state  = TEACHER_LISTEN (teacher is speaking)
  - After roll detected → switch to STUDENT_LISTEN for 15 seconds
  - After window closes → back to TEACHER_LISTEN

Runs as a daemon background thread.
"""

import time
import logging
import threading
import asyncio
from typing import Optional, Callable, List

import numpy as np

from hal.manager   import AudioSourceManager
from pipelines.audio.vad          import EnergyVAD
from pipelines.audio.transcriber  import WhisperTranscriber
from pipelines.audio.roll_detector import RollDetector
from pipelines.audio.llm_scorer   import LLMAnswerScorer
from pipelines.audio.qa_window    import QAWindowManager, QAInteractionRecord
from core.config   import settings

logger = logging.getLogger(__name__)


class AudioPipeline:
    """
    Runs the complete audio Q&A pipeline in a background thread.

    Args:
        audio_manager    : AudioSourceManager providing mic chunks (HAL)
        session_id       : Active DB session UUID
        known_students   : List[{"roll_no": int, "name": str}]
        on_qa_complete   : Callback(QAInteractionRecord) fired when Q_i computed
        db_write_fn      : Async coroutine to write Q_i to database
    """

    def __init__(
        self,
        audio_manager:  AudioSourceManager,
        session_id:     str,
        known_students: List[dict] = None,
        on_qa_complete: Optional[Callable[[QAInteractionRecord], None]] = None,
        db_write_fn=None,
    ):
        self._audio     = audio_manager
        self._session   = session_id
        self._on_qa     = on_qa_complete
        self._db_write  = db_write_fn

        # --- AI Components ---
        self._vad        = EnergyVAD(
            sample_rate=16000,
            energy_threshold=settings.vad_energy_threshold,
        )
        self._transcriber = WhisperTranscriber(
            model_size=settings.whisper_model_size,
            language=settings.whisper_language,
        )
        self._roll_detector = RollDetector(known_students or [])
        self._llm_scorer    = LLMAnswerScorer(
            ollama_url=settings.ollama_url,
            model=settings.ollama_model,
        ) if settings.ollama_enabled else None

        self._qa_window = QAWindowManager(
            window_duration=settings.qa_response_window_s,
            on_complete=self._handle_qa_complete,
            llm_scorer=self._llm_scorer,
        )

        # --- State ---
        self._running   = False
        self._paused    = False
        self._thread: Optional[threading.Thread] = None

        # Speaker mode: True = listening for teacher, False = listening for student
        self._teacher_mode = True

        # Latest transcript for dashboard display
        self._last_transcript: str = ""
        self._last_roll_detected: Optional[int] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._run_loop, daemon=True, name="AudioPipeline"
        )
        self._thread.start()
        logger.info("AudioPipeline: Started (session=%s)", self._session)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("AudioPipeline: Stopped.")

    def pause(self):
        self._paused = True
        logger.info("AudioPipeline: Paused.")

    def resume(self):
        self._paused = False
        self._vad.reset()
        logger.info("AudioPipeline: Resumed.")

    @property
    def is_waiting_for_student(self) -> bool:
        return self._qa_window.is_waiting

    @property
    def seconds_remaining(self) -> float:
        return self._qa_window.seconds_remaining

    def get_last_transcript(self) -> str:
        with self._lock:
            return self._last_transcript

    # ------------------------------------------------------------------
    # Core Loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        logger.info("AudioPipeline: Loop started.")
        while self._running:
            # Tick the QA window timeout checker
            self._qa_window.tick()

            if self._paused:
                time.sleep(0.05)
                continue

            # Get audio chunk from HAL
            chunk = self._audio.get_chunk(timeout=0.1)
            if chunk is None:
                continue

            samples = chunk.samples   # int16 numpy array

            # Feed into VAD → get segment when speech ends
            segment = self._vad.process_chunk(samples, chunk.timestamp)
            if segment is None:
                continue   # still accumulating speech

            # We have a complete speech segment → transcribe
            if segment.duration_s < 0.3:
                continue   # too short, ignore noise

            result = self._transcriber.transcribe(segment.audio)
            if result is None or not result.text:
                continue

            text = result.text

            with self._lock:
                self._last_transcript = text

            logger.debug("AudioPipeline: [%s] '%s'",
                         "TEACHER" if self._teacher_mode else "STUDENT", text)

            # --- Route transcript based on current speaker mode ---
            if self._teacher_mode:
                self._handle_teacher_speech(text)
            else:
                self._handle_student_speech(text)

    # ------------------------------------------------------------------
    # Speech handlers
    # ------------------------------------------------------------------

    def _handle_teacher_speech(self, text: str):
        """Process teacher utterance — look for roll number + question."""

        # If QA window is open and teacher speaks → interruption safeguard
        if self._qa_window.is_waiting:
            self._qa_window.on_speech_segment(text, is_teacher=True)
            return

        # Detect roll number + question
        roll_no, utterance = self._roll_detector.detect(text)

        if roll_no is not None:
            # ── STEP 1: Intent Classification ────────────────────────────
            # Ask LLM (or keyword fallback): is this a question or casual talk?
            if self._llm_scorer:
                intent_result = self._llm_scorer.classify_intent(utterance)
            else:
                # No scorer at all — keyword-only fallback
                from pipelines.audio.llm_scorer import LLMAnswerScorer
                _tmp = LLMAnswerScorer(ollama_url="http://localhost:1", model="none")
                intent_result = _tmp._keyword_classify_intent(utterance)

            intent = intent_result.get("intent", "question")
            reason = intent_result.get("reason", "")
            method = intent_result.get("method", "keyword")

            logger.info(
                "AudioPipeline: Roll %d | intent='%s' (%s) | '%s'",
                roll_no, intent, method, reason
            )

            if intent == "casual":
                # Teacher is just talking to student — no QA window
                logger.info(
                    "AudioPipeline: Skipping QA window — casual interaction with Roll %d",
                    roll_no
                )
                return   # ← do NOT open QA window

            # ── STEP 2: It IS a question → open 15s window ───────────────
            with self._lock:
                self._last_roll_detected = roll_no

            self._teacher_mode = False
            self._qa_window.on_question_detected(roll_no, utterance)

    def _handle_student_speech(self, text: str):
        """Process student utterance — feed into QA window."""
        if self._qa_window.is_waiting:
            self._qa_window.on_speech_segment(text, is_teacher=False)

        # If window just closed (state == DONE or IDLE), switch back to teacher mode
        if not self._qa_window.is_waiting:
            self._teacher_mode = True

    # ------------------------------------------------------------------
    # QA Complete Callback
    # ------------------------------------------------------------------

    def _handle_qa_complete(self, record: QAInteractionRecord):
        """
        Fired when the QA window closes with a final Q_i score.
        Writes to DB and fires user callback.
        """
        logger.info(
            "AudioPipeline: Q&A complete — Roll %d | Q_i=%.2f | %s",
            record.roll_no, record.Q_i, record.score_reason
        )

        # Write to database
        if self._db_write:
            try:
                self._db_write(record, self._session)
            except Exception as e:
                logger.warning("AudioPipeline: DB write failed: %s", e)

        # Switch back to teacher mode
        self._teacher_mode = True

        # Fire user callback (e.g. update dashboard)
        if self._on_qa:
            try:
                self._on_qa(record)
            except Exception as e:
                logger.warning("AudioPipeline: on_qa_complete error: %s", e)
