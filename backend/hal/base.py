"""
hal/base.py
===========
Abstract base classes for all hardware sources.

Rule: NO pipeline code (AI, DB, API) may import cv2 or pyaudio directly.
      All hardware access MUST go through these interfaces.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class VideoFrame:
    """A single captured video frame with metadata."""
    frame_id: int               # Monotonically increasing counter
    timestamp: float            # Unix epoch seconds (time.time())
    image: np.ndarray           # BGR image array (H, W, 3)
    source_id: str              # Identifier for the camera / stream
    width: int = 0
    height: int = 0

    def __post_init__(self):
        if self.image is not None:
            self.height, self.width = self.image.shape[:2]


@dataclass
class AudioChunk:
    """A chunk of raw PCM audio data with metadata."""
    chunk_id: int               # Monotonically increasing counter
    timestamp: float            # Unix epoch seconds (time.time())
    samples: np.ndarray         # float32 mono PCM samples, range [-1, 1]
    sample_rate: int            # e.g. 16000
    source_id: str              # Identifier for mic / stream
    duration_ms: float = field(init=False)

    def __post_init__(self):
        self.duration_ms = (len(self.samples) / self.sample_rate) * 1000.0


# ---------------------------------------------------------------------------
# Abstract Video Source
# ---------------------------------------------------------------------------

class VideoSourceBase(ABC):
    """
    Abstract interface for any video input.

    Simulation Mode  → WebcamVideoSource  (cv2.VideoCapture(0))
    Production Mode  → RTSPVideoSource    (cv2.VideoCapture("rtsp://..."))
    Test/CI Mode     → MockVideoSource    (static image or synthetic frames)
    """

    @abstractmethod
    def open(self) -> bool:
        """Open / initialise the video source. Returns True on success."""
        ...

    @abstractmethod
    def read_frame(self) -> Optional[VideoFrame]:
        """
        Read the next frame.
        Returns None when the source is exhausted or unavailable.
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Release all resources held by this source."""
        ...

    @abstractmethod
    def is_open(self) -> bool:
        """Return True if the source is currently active and readable."""
        ...

    @property
    @abstractmethod
    def fps(self) -> float:
        """Reported frames-per-second of the source."""
        ...

    # Context manager support so callers can use `with VideoSource() as src:`
    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.release()


# ---------------------------------------------------------------------------
# Abstract Audio Source
# ---------------------------------------------------------------------------

class AudioSourceBase(ABC):
    """
    Abstract interface for any audio input.

    Simulation Mode  → MicrophoneAudioSource  (PyAudio / sounddevice default mic)
    Production Mode  → RTSPAudioSource        (ambient classroom mics)
    Test/CI Mode     → MockAudioSource        (wav file playback)
    """

    @abstractmethod
    def open(self) -> bool:
        """Open / initialise the audio source. Returns True on success."""
        ...

    @abstractmethod
    def read_chunk(self) -> Optional[AudioChunk]:
        """
        Read the next audio chunk.
        Returns None when source is unavailable.
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """Release all resources held by this source."""
        ...

    @abstractmethod
    def is_open(self) -> bool:
        """Return True if the source is currently active."""
        ...

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Sample rate (Hz) of the audio stream."""
        ...

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *_):
        self.release()
