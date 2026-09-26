"""
hal/video_source.py
===================
Concrete video source implementations.

WebcamVideoSource    → Simulation mode (cv2.VideoCapture(0) or any device index)
RTSPVideoSource      → Production mode (RTSP IP camera URL)
MockVideoSource      → Unit-testing (synthetic coloured frames, no hardware)
"""

import time
import logging
import numpy as np
from typing import Optional

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False

from .base import VideoSourceBase, VideoFrame

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulation Mode – Laptop Webcam
# ---------------------------------------------------------------------------

class WebcamVideoSource(VideoSourceBase):
    """
    Reads frames from a local webcam (or any integer device index).

    Args:
        device_index (int): OpenCV device index. 0 = default/built-in webcam.
        target_fps   (int): Requested frames-per-second. The actual FPS
                            is capped by what the hardware delivers.
        width        (int): Requested capture width  (pixels). 0 = device default.
        height       (int): Requested capture height (pixels). 0 = device default.
        source_id    (str): Human-readable label used in VideoFrame metadata.
    """

    def __init__(
        self,
        device_index: int = 0,
        target_fps: int = 15,
        width: int = 640,
        height: int = 480,
        source_id: str = "webcam-0",
    ):
        if not _CV2_AVAILABLE:
            raise ImportError(
                "opencv-python is required for WebcamVideoSource. "
                "Run: pip install opencv-python"
            )
        self._device_index = device_index
        self._target_fps = target_fps
        self._req_width = width
        self._req_height = height
        self._source_id = source_id

        self._cap = None           # cv2.VideoCapture instance
        self._frame_counter = 0
        self._actual_fps: float = float(target_fps)

    # ------------------------------------------------------------------
    # VideoSourceBase interface
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """Open the webcam. Returns True if successfully opened."""
        self._cap = cv2.VideoCapture(self._device_index)
        if not self._cap.isOpened():
            logger.error(
                "WebcamVideoSource: Failed to open device %s", self._device_index
            )
            return False

        # Apply requested resolution (best-effort; hardware may ignore)
        if self._req_width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._req_width)
        if self._req_height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._req_height)
        if self._target_fps:
            self._cap.set(cv2.CAP_PROP_FPS, self._target_fps)

        # Read back what the device actually settled on
        self._actual_fps = self._cap.get(cv2.CAP_PROP_FPS) or float(self._target_fps)

        logger.info(
            "WebcamVideoSource: Opened device=%s  res=%dx%d  fps=%.1f",
            self._device_index,
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            self._actual_fps,
        )
        return True

    def read_frame(self) -> Optional[VideoFrame]:
        """Capture and return the next frame, or None on failure."""
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, bgr = self._cap.read()
        if not ret or bgr is None:
            logger.warning("WebcamVideoSource: Failed to read frame.")
            return None

        self._frame_counter += 1
        return VideoFrame(
            frame_id=self._frame_counter,
            timestamp=time.time(),
            image=bgr,
            source_id=self._source_id,
        )

    def release(self) -> None:
        """Release the capture device."""
        if self._cap:
            self._cap.release()
            self._cap = None
        logger.info("WebcamVideoSource: Released device %s", self._device_index)

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def fps(self) -> float:
        return self._actual_fps


# ---------------------------------------------------------------------------
# Production Mode – RTSP IP Camera
# ---------------------------------------------------------------------------

class RTSPVideoSource(VideoSourceBase):
    """
    Reads frames from an RTSP IP camera stream.

    Drop-in replacement for WebcamVideoSource in production.

    Args:
        rtsp_url  (str): Full RTSP URL, e.g. "rtsp://user:pass@192.168.1.10/live"
        source_id (str): Human-readable label.
        reconnect_delay_s (float): Seconds to wait before re-connecting on error.
    """

    def __init__(
        self,
        rtsp_url: str,
        source_id: str = "rtsp-cam",
        reconnect_delay_s: float = 3.0,
    ):
        if not _CV2_AVAILABLE:
            raise ImportError("opencv-python is required for RTSPVideoSource.")

        self._url = rtsp_url
        self._source_id = source_id
        self._reconnect_delay = reconnect_delay_s
        self._cap = None
        self._frame_counter = 0
        self._actual_fps: float = 15.0

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self._url)
        if not self._cap.isOpened():
            logger.error("RTSPVideoSource: Cannot connect to %s", self._url)
            return False
        self._actual_fps = self._cap.get(cv2.CAP_PROP_FPS) or 15.0
        logger.info("RTSPVideoSource: Connected to %s  fps=%.1f", self._url, self._actual_fps)
        return True

    def read_frame(self) -> Optional[VideoFrame]:
        if self._cap is None or not self._cap.isOpened():
            return None
        ret, bgr = self._cap.read()
        if not ret or bgr is None:
            logger.warning("RTSPVideoSource: Frame read failed – attempting reconnect")
            time.sleep(self._reconnect_delay)
            self.open()
            return None
        self._frame_counter += 1
        return VideoFrame(
            frame_id=self._frame_counter,
            timestamp=time.time(),
            image=bgr,
            source_id=self._source_id,
        )

    def release(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    @property
    def fps(self) -> float:
        return self._actual_fps


# ---------------------------------------------------------------------------
# Test / CI Mode – Mock (No hardware required)
# ---------------------------------------------------------------------------

class MockVideoSource(VideoSourceBase):
    """
    Generates synthetic coloured frames for unit-testing.
    Does NOT require a webcam or OpenCV install (uses NumPy only).

    Args:
        width, height (int): Frame dimensions.
        total_frames  (int): Stop after this many frames (-1 = infinite).
        fps           (float): Simulated frame rate (affects reported fps only).
        source_id     (str): Label.
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        total_frames: int = -1,
        fps: float = 15.0,
        source_id: str = "mock",
    ):
        self._width = width
        self._height = height
        self._total_frames = total_frames
        self._fps = fps
        self._source_id = source_id
        self._frame_counter = 0
        self._open = False

    def open(self) -> bool:
        self._open = True
        self._frame_counter = 0
        logger.info("MockVideoSource: Opened (synthetic %dx%d @ %.1f fps)", self._width, self._height, self._fps)
        return True

    def read_frame(self) -> Optional[VideoFrame]:
        if not self._open:
            return None
        if self._total_frames != -1 and self._frame_counter >= self._total_frames:
            return None

        # Cycle through hue values to produce visually distinct frames
        hue = int((self._frame_counter * 3) % 180)
        hsv = np.full((self._height, self._width, 3), [hue, 200, 200], dtype=np.uint8)
        if _CV2_AVAILABLE:
            bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        else:
            bgr = hsv  # fallback: just return HSV as a stand-in

        self._frame_counter += 1
        return VideoFrame(
            frame_id=self._frame_counter,
            timestamp=time.time(),
            image=bgr,
            source_id=self._source_id,
        )

    def release(self) -> None:
        self._open = False

    def is_open(self) -> bool:
        return self._open

    @property
    def fps(self) -> float:
        return self._fps
