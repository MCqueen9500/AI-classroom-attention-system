"""
pipelines/audio/vad.py
========================
Voice Activity Detection (VAD) — Energy-based, zero extra dependencies.

How it works:
  - Calculates RMS (Root Mean Square) energy of each audio chunk
  - RMS above threshold → speech detected
  - Buffers speech chunks together into a single segment
  - When silence follows speech (padding applied) → flush segment

Output: complete speech segments ready for Whisper transcription.

No PyTorch, no WebRTC, no extra packages — uses only numpy.
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List
import time

logger = logging.getLogger(__name__)


@dataclass
class SpeechSegment:
    """A complete buffered speech segment ready for transcription."""
    audio:      np.ndarray    # int16 samples at 16000 Hz
    start_time: float         # Unix timestamp when speech started
    end_time:   float         # Unix timestamp when speech ended
    duration_s: float         # duration in seconds

    @property
    def sample_rate(self) -> int:
        return 16000


class EnergyVAD:
    """
    Simple energy-based Voice Activity Detector.

    Works by monitoring audio chunk RMS energy level.
    Transitions between SILENCE and SPEECH states.

    State machine:
        SILENCE → (energy > threshold for min_frames) → SPEECH
        SPEECH  → (energy < threshold for pad_frames)  → flush → SILENCE
    """

    def __init__(
        self,
        sample_rate:       int   = 16000,
        energy_threshold:  float = 0.015,   # RMS ratio threshold
        min_speech_frames: int   = 3,        # consecutive frames to confirm speech start
        silence_pad_frames: int  = 8,        # silence frames before flushing segment
    ):
        self._rate        = sample_rate
        self._threshold   = energy_threshold
        self._min_speech  = min_speech_frames
        self._silence_pad = silence_pad_frames

        # Internal state
        self._buffer:        List[np.ndarray] = []
        self._speech_frames: int  = 0
        self._silence_frames: int = 0
        self._in_speech:     bool = False
        self._speech_start:  float = 0.0

    def process_chunk(
        self,
        samples: np.ndarray,
        timestamp: float,
    ) -> Optional[SpeechSegment]:
        """
        Feed one audio chunk. Returns a SpeechSegment when speech ends, else None.

        Args:
            samples   : int16 numpy array of audio samples
            timestamp : Unix timestamp of this chunk
        Returns:
            SpeechSegment if a complete utterance just ended, else None
        """
        rms = self._compute_rms(samples)
        is_speech = rms > self._threshold

        if is_speech:
            self._silence_frames = 0
            self._speech_frames += 1
            self._buffer.append(samples.copy())

            if not self._in_speech and self._speech_frames >= self._min_speech:
                self._in_speech  = True
                self._speech_start = timestamp
                logger.debug("VAD: Speech started (rms=%.4f)", rms)

        else:
            # Silence
            if self._in_speech:
                self._silence_frames += 1
                self._buffer.append(samples.copy())  # pad with silence

                if self._silence_frames >= self._silence_pad:
                    return self._flush(end_time=timestamp)
            else:
                self._speech_frames = max(0, self._speech_frames - 1)

        return None

    def _flush(self, end_time: float) -> Optional[SpeechSegment]:
        """Finalize and return the buffered speech segment."""
        if not self._buffer:
            return None

        audio = np.concatenate(self._buffer)
        duration = len(audio) / self._rate

        segment = SpeechSegment(
            audio=audio,
            start_time=self._speech_start,
            end_time=end_time,
            duration_s=round(duration, 3),
        )

        logger.debug(
            "VAD: Speech segment flushed (%.2fs, %d samples)",
            duration, len(audio)
        )

        # Reset state
        self._buffer        = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech     = False

        return segment

    def _compute_rms(self, samples: np.ndarray) -> float:
        """Normalized RMS energy [0.0 – 1.0]."""
        if len(samples) == 0:
            return 0.0
        floats = samples.astype(np.float32) / 32768.0   # normalize int16 → [-1, 1]
        return float(np.sqrt(np.mean(floats ** 2)))

    def reset(self):
        """Reset internal state (call on session resume)."""
        self._buffer        = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._in_speech     = False
