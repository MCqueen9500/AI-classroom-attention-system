"""
hal/manager.py
==============
VideoSourceManager  – owns and controls the active VideoSourceBase instance.
AudioSourceManager  – owns and controls the active AudioSourceBase instance.

These managers are the ONLY objects the rest of the system talks to.
Swap the underlying source (webcam ↔ RTSP ↔ mock) by calling
`manager.set_source(new_source)` without touching any pipeline code.
"""

import logging
import threading
import queue
import time
from typing import Optional

from .base import VideoSourceBase, AudioSourceBase, VideoFrame, AudioChunk

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# VideoSourceManager
# ---------------------------------------------------------------------------

class VideoSourceManager:
    """
    Wraps a VideoSourceBase and exposes a thread-safe frame queue.

    The manager runs a background capture thread that continuously reads
    frames from the source and pushes them into a bounded queue.
    Downstream pipelines consume from the queue via `get_frame()`.

    Args:
        source      (VideoSourceBase): The concrete source to use.
        max_queue   (int): Maximum frames to buffer (older frames are dropped).
    """

    def __init__(self, source: VideoSourceBase, max_queue: int = 5):
        self._source = source
        self._queue: queue.Queue[VideoFrame] = queue.Queue(maxsize=max_queue)
        self._thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Source hot-swap support
    # ------------------------------------------------------------------

    def set_source(self, new_source: VideoSourceBase) -> None:
        """
        Hot-swap the underlying source.
        Stops the capture thread, releases the old source, starts new one.
        Thread-safe (but causes a brief capture gap).
        """
        was_running = self._running
        if was_running:
            self.stop()
        self._source.release()
        self._source = new_source
        if was_running:
            self.start()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Open the source and start background capture thread."""
        if not self._source.open():
            logger.error("VideoSourceManager: Source failed to open.")
            return False
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="VideoCapture"
        )
        self._thread.start()
        logger.info("VideoSourceManager: Started (source=%s)", type(self._source).__name__)
        return True

    def stop(self) -> None:
        """Stop capture thread and release source."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        self._source.release()
        logger.info("VideoSourceManager: Stopped.")

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self, timeout: float = 0.1) -> Optional[VideoFrame]:
        """
        Retrieve the next available frame from the queue.
        Returns None if no frame arrives within `timeout` seconds.
        """
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_loop(self):
        while self._running:
            frame = self._source.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            # Drop oldest frame if queue is full (real-time priority)
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put(frame)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def fps(self) -> float:
        return self._source.fps

    @property
    def is_running(self) -> bool:
        return self._running


# ---------------------------------------------------------------------------
# AudioSourceManager
# ---------------------------------------------------------------------------

class AudioSourceManager:
    """
    Wraps an AudioSourceBase and exposes a thread-safe chunk queue.

    Same design pattern as VideoSourceManager.

    Args:
        source    (AudioSourceBase): The concrete audio source.
        max_queue (int): Maximum chunks to buffer.
    """

    def __init__(self, source: AudioSourceBase, max_queue: int = 50):
        self._source = source
        self._queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=max_queue)
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def set_source(self, new_source: AudioSourceBase) -> None:
        was_running = self._running
        if was_running:
            self.stop()
        self._source.release()
        self._source = new_source
        if was_running:
            self.start()

    def start(self) -> bool:
        if not self._source.open():
            logger.error("AudioSourceManager: Source failed to open.")
            return False
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="AudioCapture"
        )
        self._thread.start()
        logger.info("AudioSourceManager: Started (source=%s)", type(self._source).__name__)
        return True

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        self._source.release()
        logger.info("AudioSourceManager: Stopped.")

    def get_chunk(self, timeout: float = 0.05) -> Optional[AudioChunk]:
        """Retrieve the next buffered audio chunk, or None on timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        while self._running:
            chunk = self._source.read_chunk()
            if chunk is None:
                time.sleep(0.005)
                continue
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
            self._queue.put(chunk)

    @property
    def sample_rate(self) -> int:
        return self._source.sample_rate

    @property
    def is_running(self) -> bool:
        return self._running
