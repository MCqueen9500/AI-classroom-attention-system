"""
pipelines/vision/face_detector.py
===================================
Multi-face detection with 3-tier fallback strategy (updated for OpenCV 5 + MediaPipe 1.x):

Tier 1: MediaPipe Tasks FaceDetector  (new Tasks API — works with mediapipe 0.10+ / 1.0+)
Tier 2: OpenCV YuNet FaceDetector     (cv2.FaceDetectorYN — built into OpenCV 4.7+/5.0)
Tier 3: OpenCV DNN (readNet/ONNX)     (generic fallback)
"""

import os
import logging
import numpy as np
from typing import List, Optional, Tuple
import cv2
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Central models directory (sibling of backend/)
_MODELS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "models")
)


@dataclass
class FaceDetection:
    """A single detected face in a frame."""
    bbox: Tuple[int, int, int, int]   # (x, y, w, h) pixels
    confidence: float                  # [0.0, 1.0]
    face_crop: np.ndarray              # cropped BGR image

    @property
    def center(self) -> Tuple[int, int]:
        x, y, w, h = self.bbox
        return (x + w // 2, y + h // 2)


class FaceDetectorBase:
    def detect(self, bgr_frame: np.ndarray) -> List[FaceDetection]:
        raise NotImplementedError
    def close(self): pass


# ---------------------------------------------------------------------------
# Tier 1: MediaPipe Tasks API  (mediapipe >= 0.10 / 1.0)
# ---------------------------------------------------------------------------
class MediaPipeTasksFaceDetector(FaceDetectorBase):
    """
    Uses the new mediapipe.tasks.python.vision.FaceDetector API.
    Compatible with mediapipe 0.10.x and 1.0.x (solutions API removed in 1.x).
    """
    def __init__(self, model_path: str, min_detection_confidence: float = 0.5):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=min_detection_confidence,
        )
        self._detector = mp_vision.FaceDetector.create_from_options(options)
        self._mp = mp
        logger.info("FaceDetector: Using MediaPipe Tasks API")

    def detect(self, bgr_frame: np.ndarray) -> List[FaceDetection]:
        h, w = bgr_frame.shape[:2]
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=rgb,
        )
        result = self._detector.detect(mp_image)

        detections: List[FaceDetection] = []
        if not result.detections:
            return detections

        for det in result.detections:
            bb = det.bounding_box
            x  = max(0, bb.origin_x)
            y  = max(0, bb.origin_y)
            bw = min(bb.width,  w - x)
            bh = min(bb.height, h - y)
            if bw <= 0 or bh <= 0:
                continue
            conf = det.categories[0].score if det.categories else 0.5
            crop = bgr_frame[y:y+bh, x:x+bw].copy()
            detections.append(FaceDetection(bbox=(x, y, bw, bh), confidence=float(conf), face_crop=crop))
        return detections

    def close(self):
        if self._detector:
            self._detector.close()


# ---------------------------------------------------------------------------
# Tier 2: OpenCV YuNet (FaceDetectorYN — available in OpenCV 4.7+/5.0)
# ---------------------------------------------------------------------------
class YuNetFaceDetector(FaceDetectorBase):
    """
    Uses OpenCV's built-in YuNet-based face detector (cv2.FaceDetectorYN).
    Works in OpenCV 4.7+ and OpenCV 5.0. No Caffe/DNN-Caffe required.
    """
    def __init__(self, model_path: str, score_threshold: float = 0.6):
        self._detector = cv2.FaceDetectorYN.create(
            model=model_path,
            config="",
            input_size=(320, 320),
            score_threshold=score_threshold,
            nms_threshold=0.3,
            top_k=10,
        )
        self._score_thresh = score_threshold
        logger.info("FaceDetector: Using OpenCV YuNet (FaceDetectorYN)")

    def detect(self, bgr_frame: np.ndarray) -> List[FaceDetection]:
        h, w = bgr_frame.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(bgr_frame)
        detections: List[FaceDetection] = []
        if faces is None:
            return detections
        for face in faces:
            # YuNet output: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rcm, y_rcm, x_lcm, y_lcm, score]
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            score = float(face[-1])
            x  = max(0, x)
            y  = max(0, y)
            fw = min(fw, w - x)
            fh = min(fh, h - y)
            if fw <= 0 or fh <= 0:
                continue
            crop = bgr_frame[y:y+fh, x:x+fw].copy()
            det = FaceDetection(bbox=(x, y, fw, fh), confidence=score, face_crop=crop)
            det.yunet_face_row = face
            detections.append(det)
        return detections


# ---------------------------------------------------------------------------
# Factory: auto-select best available detector
# ---------------------------------------------------------------------------
def build_face_detector(
    prefer: str = "mediapipe",
    min_detection_confidence: float = 0.5,
) -> FaceDetectorBase:
    """
    Build the best available face detector automatically.
    Downloads model files from models/ directory.
    """
    mp_model   = os.path.join(_MODELS_DIR, "blaze_face_short_range.tflite")
    yunet_model = os.path.join(_MODELS_DIR, "face_detection_yunet_2023mar.onnx")

    tiers = [
        ("mediapipe_tasks", mp_model),
        ("yunet",           yunet_model),
    ]

    for tier_name, model_path in tiers:
        if not os.path.exists(model_path):
            logger.warning("FaceDetector: model not found for tier '%s' (%s). Run: python scripts/download_models.py", tier_name, model_path)
            continue
        try:
            if tier_name == "mediapipe_tasks":
                return MediaPipeTasksFaceDetector(model_path, min_detection_confidence)
            elif tier_name == "yunet":
                return YuNetFaceDetector(model_path, score_threshold=min_detection_confidence)
        except Exception as e:
            logger.warning("FaceDetector tier '%s' failed: %s", tier_name, e)

    # Last resort: simple DNN-based detector using face_detection_yunet via readNet
    logger.error(
        "No face detector could be initialized. "
        "Run 'python scripts/download_models.py' to download model files."
    )
    raise RuntimeError(
        "No face detector models found. Run: python scripts\\download_models.py"
    )
