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

BUG FIX: Added verbose print() diagnostics at every stage so that
         any failure is immediately visible in the terminal.
BUG FIX: Replaced strict regex with a flexible NUMBER_MAP extractor
         that catches Whisper mis-transcriptions like "one", "role",
         "row", etc.
"""

import os
import re
import time
import logging
import threading
from typing import Optional, Callable, List

import numpy as np
import requests

from hal.manager import AudioSourceManager
from pipelines.audio.vad import EnergyVAD
from pipelines.audio.transcriber import WhisperTranscriber
from pipelines.audio.roll_detector import RollDetector
from pipelines.audio.llm_scorer import LLMAnswerScorer
from pipelines.audio.qa_window import QAWindowManager, QAInteractionRecord
from core.config import settings

logger = logging.getLogger(__name__)

# REPAIR 3B: Dynamic API base — reads CLASSMON_API_URL env var
_API_BASE = os.getenv("CLASSMON_API_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# BUG FIX 1: Flexible roll-number extractor with word-to-digit map
# Catches Whisper mis-transcriptions: "role one", "row 3", "rull number two"
# ---------------------------------------------------------------------------
NUMBER_MAP = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}

_ROLL_RE = re.compile(
    r"(?:roll|role|rule|row|rall|rol|rull|no|number)[\s.]*"
    r"(?:no\.?|number|num|#)?\s*"
    r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten"
    r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen"
    r"|seventeen|eighteen|nineteen|twenty)\b",
    re.IGNORECASE,
)


def extract_roll_number(text: str) -> Optional[int]:
    """
    Extract a roll number from transcribed teacher speech.
    Handles digit strings AND spoken words (e.g. 'roll three').
    Returns int or None.
    """
    match = _ROLL_RE.search(text.lower())
    if match:
        val = match.group(1).lower()
        return int(val) if val.isdigit() else NUMBER_MAP.get(val)
    return None


class AudioPipeline:
    """
    Runs the complete audio Q&A pipeline in a background thread.

    Args:
        audio_manager    : AudioSourceManager providing mic chunks (HAL)
        session_id       : Active DB session UUID
        known_students   : List[{"roll_no": int, "name": str}]
        on_qa_complete   : Callback(QAInteractionRecord) fired when Q_i computed
        db_write_fn      : Async coroutine to write Q_i to database
        api_base_url     : Override for backend API URL (default: CLASSMON_API_URL env)
    """

    def __init__(
        self,
        audio_manager: AudioSourceManager,
        session_id: str,
        known_students: List[dict] = None,
        on_qa_complete: Optional[Callable[[QAInteractionRecord], None]] = None,
        db_write_fn=None,
        api_base_url: Optional[str] = None,
    ):
        self._audio = audio_manager
        self._session = session_id
        self._on_qa = on_qa_complete
        self._db_write = db_write_fn
        self._api_base = (api_base_url or _API_BASE).rstrip("/")

        print(f"[AUDIO] Pipeline init — session={session_id}, api={self._api_base}")

        # --- AI Components ---
        self._vad = EnergyVAD(
            sample_rate=16000,
            energy_threshold=settings.vad_energy_threshold,
        )
        self._transcriber = WhisperTranscriber(
            model_size=settings.whisper_model_size,
            language=settings.whisper_language,
        )
        self._roll_detector = RollDetector(known_students or [])
        self._llm_scorer = LLMAnswerScorer(
            ollama_url=settings.ollama_url,
            model=settings.ollama_model,
        ) if settings.ollama_enabled else None

        self._qa_window = QAWindowManager(
            window_duration=settings.qa_response_window_s,
            on_complete=self._handle_qa_complete,
            llm_scorer=self._llm_scorer,
        )

        # --- State ---
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._teacher_mode = True
        self._last_transcript: str = ""
        self._last_roll_detected: Optional[int] = None
        self._lock = threading.Lock()

        print(f"[AUDIO] Whisper model={settings.whisper_model_size}, "
              f"VAD threshold={settings.vad_energy_threshold}, "
              f"Ollama enabled={settings.ollama_enabled}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="AudioPipeline"
        )
        self._thread.start()
        print(f"[AUDIO] ✅ Pipeline STARTED — listening on microphone (session={self._session})")
        logger.info("AudioPipeline: Started (session=%s)", self._session)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        print("[AUDIO] Pipeline STOPPED.")
        logger.info("AudioPipeline: Stopped.")

    def pause(self):
        self._paused = True
        print("[AUDIO] Pipeline PAUSED.")
        logger.info("AudioPipeline: Paused.")

    def resume(self):
        self._paused = False
        self._vad.reset()
        print("[AUDIO] Pipeline RESUMED.")
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
    # Core Loop — with verbose print diagnostics at every step
    # ------------------------------------------------------------------

    def _run_loop(self):
        print("[AUDIO] 🔁 Main loop started — waiting for speech...")
        logger.info("AudioPipeline: Loop started.")
        chunk_count = 0

        while self._running:
            try:
                # Tick the QA window timeout checker
                self._qa_window.tick()

                if self._paused:
                    time.sleep(0.05)
                    continue

                # Get audio chunk from HAL
                chunk = self._audio.get_chunk(timeout=0.1)
                if chunk is None:
                    continue

                chunk_count += 1
                # Print heartbeat every 100 chunks (~10s) so we know mic is alive
                if chunk_count % 100 == 0:
                    print(f"[AUDIO] 💓 Mic alive — {chunk_count} chunks processed, "
                          f"mode={'TEACHER' if self._teacher_mode else 'STUDENT'}")

                samples = chunk.samples

                # MicrophoneAudioSource delivers float32 [-1, 1]; VAD+Whisper need int16
                if samples.dtype != np.int16:
                    samples = (samples * 32767).clip(-32768, 32767).astype(np.int16)

                # Feed into VAD → get segment when speech ends
                segment = self._vad.process_chunk(samples, chunk.timestamp)
            
                # --- DEBUG: Print live mic RMS every ~1 second ---
                if chunk_count % 10 == 0:
                    rms = float(np.sqrt(np.mean((samples.astype(np.float32) / 32768.0)**2)))
                    is_speech = "🔊" if rms > self._vad._threshold else "🔈"
                    print(f"[AUDIO] Mic Level: {rms:.4f} {is_speech} (Threshold: {self._vad._threshold})")

                if segment is None:
                    continue  # still accumulating speech

                print(f"[AUDIO] 🎙️ Speech segment detected — duration={segment.duration_s:.2f}s")

                # We have a complete speech segment → transcribe
                if segment.duration_s < 0.3:
                    print("[AUDIO] ⏭️  Segment too short (<0.3s) — ignored as noise")
                    continue

                print("[AUDIO] 🤖 Sending to Whisper for transcription...")
                result = self._transcriber.transcribe(segment.audio)
                if result is None or not result.text:
                    print("[AUDIO] ❌ Whisper returned empty result — no speech detected")
                    continue

                text = result.text.strip()
                print(f"[AUDIO] 🗣️  Whisper heard: \"{text}\"")
                logger.info("AudioPipeline: [%s] '%s'",
                            "TEACHER" if self._teacher_mode else "STUDENT", text)

                with self._lock:
                    self._last_transcript = text

                # --- Route transcript based on current speaker mode ---
                if self._teacher_mode:
                    self._handle_teacher_speech(text)
                else:
                    self._handle_student_speech(text)

        # ------------------------------------------------------------------
        # Speech handlers
        # ------------------------------------------------------------------

            except Exception as e:
                print(f"\n[CRITICAL ERROR IN AUDIO LOOP] {e}\n")
                import traceback; traceback.print_exc()
                import time; time.sleep(1)
    def _handle_teacher_speech(self, text: str):
        """Process teacher utterance — look for roll number + question."""

        # If QA window is open and teacher speaks → interruption safeguard
        if self._qa_window.is_waiting:
            print(f"[AUDIO] ⚠️  Teacher interrupted Q&A window — treating as student interruption")
            self._qa_window.on_speech_segment(text, is_teacher=True)
            return

        # BUG FIX 1: Use flexible NUMBER_MAP extractor instead of strict regex
        roll_no = extract_roll_number(text)
        print(f"[AUDIO] 🔍 Roll detector → roll_no={roll_no} (from: \"{text}\")")

        if roll_no is None:
            # Also try the original RollDetector as fallback (catches name-based addressing)
            roll_no_rd, utterance_rd = self._roll_detector.detect(text)
            if roll_no_rd is not None:
                roll_no = roll_no_rd
                utterance = utterance_rd
                print(f"[AUDIO] ✅ Name-based detection → Roll {roll_no}")
            else:
                print(f"[AUDIO]    No roll number found — treating as background speech")
                return
        else:
            # Extract question part = everything after the roll trigger
            match = _ROLL_RE.search(text.lower())
            utterance = text[match.end():].strip() if match else text
            utterance = utterance.lstrip(".,- ") or "question"

        print(f"[AUDIO] ✅ Roll {roll_no} detected | Question: \"{utterance}\"")

        # ── Intent Classification ────────────────────────────────────
        if self._llm_scorer and self._llm_scorer._available:
            intent_result = self._llm_scorer.classify_intent(utterance)
            print(f"[AUDIO] 🧠 LLM intent: {intent_result.get('intent')} ({intent_result.get('reason','')})")
        else:
            from pipelines.audio.llm_scorer import _keyword_classify_intent_fn
            intent_result = _keyword_classify_intent_fn(utterance)
            print(f"[AUDIO] 🔑 Keyword intent: {intent_result.get('intent')} ({intent_result.get('reason','')})")

        intent = intent_result.get("intent", "question")
        reason = intent_result.get("reason", "")
        method = intent_result.get("method", "keyword")

        logger.info("AudioPipeline: Roll %d | intent='%s' (%s) | '%s'",
                    roll_no, intent, method, reason)

        if intent == "casual":
            print(f"[AUDIO] 💬 Casual interaction with Roll {roll_no} — skipping Q&A window")
            logger.info("AudioPipeline: Skipping QA window — casual interaction with Roll %d", roll_no)
            return

        # ── Open 15s Q&A window ──────────────────────────────────────
        print(f"[AUDIO] 🚀 Opening Q&A window for Roll {roll_no} — {settings.qa_response_window_s}s window")
        with self._lock:
            self._last_roll_detected = roll_no

        self._teacher_mode = False
        self._qa_window.on_question_detected(roll_no, utterance)

        # Push to dashboard immediately so Q&A panel lights up
        self._push_qa_telemetry(
            active=True,
            roll=roll_no,
            question=utterance,
            seconds=self._qa_window.seconds_remaining,
        )

    def _handle_student_speech(self, text: str):
        """Process student utterance — feed into QA window."""
        print(f"[AUDIO] 👨‍🎓 Student speech: \"{text}\"")
        if self._qa_window.is_waiting:
            self._qa_window.on_speech_segment(text, is_teacher=False)

        # If window just closed (state == DONE or IDLE), switch back to teacher mode
        if not self._qa_window.is_waiting:
            print("[AUDIO] Q&A window closed — switching back to TEACHER mode")
            self._teacher_mode = True

    def _push_qa_telemetry(self, active: bool, roll=None, question=None, seconds=0.0):
        """Non-blocking HTTP push to /api/telemetry/audio so the dashboard updates."""

        def _post():
            url = f"{self._api_base}/api/telemetry/audio"
            print(f"[AUDIO] 📡 Pushing Q&A telemetry → {url} (active={active}, roll={roll})")
            try:
                resp = requests.post(
                    url,
                    json={
                        "qa_active": active,
                        "qa_asked_roll": roll,
                        "qa_question": question,
                        "qa_seconds": seconds,
                    },
                    timeout=2,
                )
                if resp.ok:
                    print(f"[AUDIO] ✅ Telemetry push OK (HTTP {resp.status_code})")
                else:
                    print(f"[AUDIO] ❌ Telemetry push HTTP {resp.status_code}: {resp.text[:200]}")
                    logger.error("[AUDIO] Telemetry push to %s returned HTTP %d: %s",
                                 url, resp.status_code, resp.text[:200])
            except requests.exceptions.ConnectionError:
                print(f"[AUDIO] ❌ CANNOT REACH BACKEND at {url} — is run_server.py running?")
                logger.error("[AUDIO] Cannot reach backend at %s — is run_server.py running?", url)
            except Exception as e:
                print(f"[AUDIO] ❌ Telemetry push FAILED: {e}")
                logger.error("[AUDIO] Telemetry push FAILED (%s): %s", url, e)

        threading.Thread(target=_post, daemon=True).start()

    # ------------------------------------------------------------------
    # REPAIR 4: MAR Lip-Sync verification
    # ------------------------------------------------------------------

    def _check_mar_for_roll(self, roll_no: int) -> Optional[float]:
        """
        Query the backend's live pipeline state to get the current
        Mouth Aspect Ratio for a specific student.
        Returns the MAR float, or None if unreachable / student not in frame.
        """
        url = f"{self._api_base}/api/telemetry/state"
        try:
            resp = requests.get(url, timeout=2)
            if not resp.ok:
                logger.warning("[AUDIO] MAR check: state endpoint returned %d", resp.status_code)
                return None
            data = resp.json()
            for face in data.get("faces", []):
                if face.get("roll_no") == roll_no:
                    mar = face.get("mar")
                    logger.debug("[AUDIO] MAR for Roll %d = %s", roll_no, mar)
                    return float(mar) if mar is not None else None
            logger.info("[AUDIO] Roll %d not visible in frame during Q&A window.", roll_no)
            return None
        except requests.exceptions.ConnectionError:
            logger.warning("[AUDIO] MAR check: cannot reach %s", url)
            return None
        except Exception as e:
            logger.warning("[AUDIO] MAR check failed: %s", e)
            return None

    def _push_qa_result(self, record: QAInteractionRecord):
        """
        When the QA window fully closes:
        1. Check MAR to verify student was speaking (lip-sync).
        2. Append a warning to llm_feedback if lips were closed.
        3. Push complete result to /api/telemetry/audio for DB write.
        """
        mar = self._check_mar_for_roll(record.roll_no)
        feedback = record.score_reason or ""

        if mar is None:
            feedback = (
                f"[WARNING: Student Roll {record.roll_no} not detected in frame during Q&A] "
                + feedback
            )
            print(f"[AUDIO] ⚠️  Roll {record.roll_no} NOT in camera frame during Q&A")
        elif mar < 0.02:
            feedback = (
                f"[WARNING: Lips closed during answer (MAR={mar:.3f}) — possible background noise] "
                + feedback
            )
            print(f"[AUDIO] ⚠️  Roll {record.roll_no} MAR={mar:.3f} < 0.02 — lips closed!")
        else:
            print(f"[AUDIO] ✅ Roll {record.roll_no} MAR={mar:.3f} — lip-sync OK")

        def _post():
            url = f"{self._api_base}/api/telemetry/audio"
            print(f"[AUDIO] 💾 Saving Q&A result → {url} (Roll={record.roll_no}, Q_i={record.Q_i:.2f})")
            try:
                resp = requests.post(
                    url,
                    json={
                        "qa_active": False,
                        "qa_asked_roll": record.roll_no,
                        "qa_question": record.question_text,
                        "qa_seconds": 0.0,
                        "qa_score": round(record.Q_i, 3),
                        "session_id": self._session,
                        "student_response_text": record.student_answer or None,
                        "llm_feedback": feedback or None,
                    },
                    timeout=5,
                )
                if resp.ok:
                    print(f"[AUDIO] ✅ Q&A result saved to DB (HTTP {resp.status_code})")
                    logger.info("[AUDIO] Q&A result saved to DB via %s", url)
                else:
                    print(f"[AUDIO] ❌ Q&A result push HTTP {resp.status_code}: {resp.text[:200]}")
                    logger.error("[AUDIO] Q&A result push to %s returned HTTP %d: %s",
                                 url, resp.status_code, resp.text[:200])
            except requests.exceptions.ConnectionError:
                print(f"[AUDIO] ❌ BACKEND UNREACHABLE at {url} — Q&A result NOT saved!")
                logger.error("[AUDIO] Q&A result push FAILED — backend unreachable at %s", url)
            except Exception as e:
                print(f"[AUDIO] ❌ Q&A result push FAILED: {e}")
                logger.error("[AUDIO] Q&A result push FAILED: %s", e)

        threading.Thread(target=_post, daemon=True).start()

    # ------------------------------------------------------------------
    # QA Complete Callback
    # ------------------------------------------------------------------

    def _handle_qa_complete(self, record: QAInteractionRecord):
        """
        Fired when the QA window closes with a final Q_i score.
        Runs MAR lip-sync check, pushes full result (including transcribed
        text) to the telemetry endpoint which writes it to the DB.
        """
        print(f"\n[AUDIO] ═══════════════════════════════════════")
        print(f"[AUDIO] Q&A COMPLETE — Roll {record.roll_no}")
        print(f"[AUDIO]   Question : {record.question_text}")
        print(f"[AUDIO]   Answer   : {record.student_answer}")
        print(f"[AUDIO]   Score    : Q_i={record.Q_i:.2f} ({record.score_reason})")
        print(f"[AUDIO] ═══════════════════════════════════════\n")

        logger.info("AudioPipeline: Q&A complete -- Roll %d | Q_i=%.2f | %s",
                    record.roll_no, record.Q_i, record.score_reason)

        # Push full result to backend with MAR verification → DB write
        self._push_qa_result(record)

        # Switch back to teacher mode
        self._teacher_mode = True
        print("[AUDIO] ✅ Switched back to TEACHER mode")

        # Fire user callback (e.g. update dashboard)
        if self._on_qa:
            try:
                self._on_qa(record)
            except Exception as e:
                logger.warning("AudioPipeline: on_qa_complete error: %s", e)
