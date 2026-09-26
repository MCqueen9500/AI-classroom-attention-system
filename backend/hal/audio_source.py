"""
hal/audio_source.py
===================
Concrete audio source implementations.

MicrophoneAudioSource  → Simulation mode (system default microphone via sounddevice)
MockAudioSource        → Unit-testing (synthetic noise, no hardware)

Production note: Swap in RTSPAudioSource or any external mic feed here.
"""

import time
import logging
import numpy as np
from typing import Optional

from .base import AudioSourceBase, AudioChunk

logger = logging.getLogger(__name__)

# Attempt to import sounddevice; degrade gracefully if not installed
try:
    import sounddevice as sd
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False


# ---------------------------------------------------------------------------
# Simulation Mode – System Default Microphone
# ---------------------------------------------------------------------------

class MicrophoneAudioSource(AudioSourceBase):
    """
    Reads audio chunks from the system default microphone using sounddevice.

    Args:
        sample_rate      (int):   Target sample rate in Hz. Models expect 16000.
        chunk_duration_ms(float): Size of each audio chunk in milliseconds.
        device           (int|None): sounddevice device index. None = system default.
        source_id        (str):   Human-readable label.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: float = 100.0,      # 100 ms per chunk = 1600 samples
        device: Optional[int] = None,
        source_id: str = "mic-default",
    ):
        if not _SD_AVAILABLE:
            raise ImportError(
                "sounddevice is required for MicrophoneAudioSource. "
                "Run: pip install sounddevice"
            )
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_duration_ms
        self._device = device
        self._source_id = source_id

        self._chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self._stream: Optional[sd.InputStream] = None
        self._chunk_counter = 0
        self._buffer: list[np.ndarray] = []

    # ------------------------------------------------------------------
    # AudioSourceBase interface
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """Open the microphone stream."""
        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self._chunk_size,
                device=self._device,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info(
                "MicrophoneAudioSource: Opened  sr=%d  chunk=%dms  device=%s",
                self._sample_rate, self._chunk_ms, self._device or "default",
            )
            return True
        except Exception as exc:
            logger.error("MicrophoneAudioSource: Failed to open – %s", exc)
            return False

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """Internal sounddevice callback; appends chunk to internal buffer."""
        if status:
            logger.warning("MicrophoneAudioSource stream status: %s", status)
        # indata shape is (frames, channels); flatten to mono 1-D array
        self._buffer.append(indata[:, 0].copy())

    def read_chunk(self) -> Optional[AudioChunk]:
        """
        Return the oldest buffered chunk, or None if buffer is empty.
        The caller should sleep briefly (e.g., 10 ms) when None is returned
        to avoid busy-waiting.
        """
        if not self._buffer:
            return None
        samples = self._buffer.pop(0)
        self._chunk_counter += 1
        return AudioChunk(
            chunk_id=self._chunk_counter,
            timestamp=time.time(),
            samples=samples,
            sample_rate=self._sample_rate,
            source_id=self._source_id,
        )

    def release(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("MicrophoneAudioSource: Released.")

    def is_open(self) -> bool:
        return self._stream is not None and self._stream.active

    @property
    def sample_rate(self) -> int:
        return self._sample_rate


# ---------------------------------------------------------------------------
# Test / CI Mode – Mock (No hardware required)
# ---------------------------------------------------------------------------

class MockAudioSource(AudioSourceBase):
    """
    Generates synthetic Gaussian noise chunks for unit-testing.
    No microphone or sounddevice required.

    Args:
        sample_rate      (int):   Sample rate in Hz.
        chunk_duration_ms(float): Chunk size in milliseconds.
        total_chunks     (int):   Stop after this many chunks (-1 = infinite).
        source_id        (str):   Label.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_duration_ms: float = 100.0,
        total_chunks: int = -1,
        source_id: str = "mock-audio",
    ):
        self._sample_rate = sample_rate
        self._chunk_ms = chunk_duration_ms
        self._total_chunks = total_chunks
        self._source_id = source_id
        self._chunk_size = int(sample_rate * chunk_duration_ms / 1000)
        self._chunk_counter = 0
        self._open = False

    def open(self) -> bool:
        self._open = True
        logger.info("MockAudioSource: Opened (synthetic %d Hz)", self._sample_rate)
        return True

    def read_chunk(self) -> Optional[AudioChunk]:
        if not self._open:
            return None
        if self._total_chunks != -1 and self._chunk_counter >= self._total_chunks:
            return None
        # Generate low-amplitude random noise
        samples = np.random.randn(self._chunk_size).astype(np.float32) * 0.01
        self._chunk_counter += 1
        return AudioChunk(
            chunk_id=self._chunk_counter,
            timestamp=time.time(),
            samples=samples,
            sample_rate=self._sample_rate,
            source_id=self._source_id,
        )

    def release(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    @property
    def sample_rate(self) -> int:
        return self._sample_rate
