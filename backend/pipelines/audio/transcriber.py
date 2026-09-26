"""
pipelines/audio/transcriber.py
================================
Offline Speech-to-Text using faster-whisper.

faster-whisper is 4x faster than openai-whisper because it uses
CTranslate2 backend instead of PyTorch — runs well on CPU.

Model sizes (auto-downloaded on first run):
  tiny  →  39 MB  — fastest, decent for short phrases
  base  →  74 MB  — best balance for classroom (default)
  small → 244 MB  — higher accuracy, slower

Returns: transcribed text + word-level timestamps
"""

import logging
import time
import numpy as np
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Output of Whisper transcription."""
    text:       str               # full transcribed text (lowercased)
    language:   str               # detected language code
    duration_s: float             # audio duration in seconds
    latency_s:  float             # time taken to transcribe
    words:      List[dict]        # [{word, start, end, probability}]
    confidence: float             # mean word probability [0,1]


class WhisperTranscriber:
    """
    Wraps faster-whisper for offline speech-to-text.
    Thread-safe: process() can be called from any thread.
    Model is loaded once and reused.
    """

    def __init__(
        self,
        model_size:  str   = "base",
        language:    str   = "en",
        device:      str   = "cpu",
        compute_type: str  = "int8",   # int8 = fastest on CPU
    ):
        self._model_size   = model_size
        self._language     = language
        self._device       = device
        self._compute_type = compute_type
        self._model        = None
        self._load()

    def _load(self):
        try:
            from faster_whisper import WhisperModel
            logger.info(
                "Transcriber: Loading faster-whisper '%s' on %s...",
                self._model_size, self._device
            )
            t0 = time.time()
            self._model = WhisperModel(
                self._model_size,
                device=self._device,
                compute_type=self._compute_type,
            )
            logger.info(
                "Transcriber: Model ready in %.1fs", time.time() - t0
            )
        except Exception as e:
            logger.error("Transcriber: Failed to load Whisper: %s", e)
            self._model = None

    def transcribe(self, audio: np.ndarray) -> Optional[TranscriptionResult]:
        """
        Transcribe a speech segment.

        Args:
            audio: int16 numpy array at 16000 Hz sample rate
        Returns:
            TranscriptionResult or None if model unavailable
        """
        if self._model is None:
            return None

        # faster-whisper needs float32 normalized [-1, 1]
        float_audio = audio.astype(np.float32) / 32768.0

        t0 = time.time()
        segments, info = self._model.transcribe(
            float_audio,
            language=self._language,
            word_timestamps=True,
            vad_filter=False,         # we already did VAD upstream
            beam_size=3,              # lower = faster
            best_of=3,
            temperature=0.0,
        )

        # Collect words and build full text
        all_words = []
        full_text = ""
        for seg in segments:
            full_text += seg.text
            if seg.words:
                for w in seg.words:
                    all_words.append({
                        "word":        w.word.strip(),
                        "start":       round(w.start, 3),
                        "end":         round(w.end, 3),
                        "probability": round(w.probability, 3),
                    })

        latency = round(time.time() - t0, 3)
        confidence = (
            float(np.mean([w["probability"] for w in all_words]))
            if all_words else 0.0
        )

        result = TranscriptionResult(
            text=full_text.strip().lower(),
            language=info.language,
            duration_s=round(len(audio) / 16000, 2),
            latency_s=latency,
            words=all_words,
            confidence=round(confidence, 3),
        )

        logger.info(
            'Transcriber: "%s" (%.2fs audio, %.2fs latency, conf=%.2f)',
            result.text, result.duration_s, result.latency_s, result.confidence
        )
        return result
