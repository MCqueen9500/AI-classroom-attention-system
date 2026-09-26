"""
scripts/download_models.py
===========================
Downloads all AI model files required by Phase 3.
Run this ONCE before running the vision pipeline.

Models downloaded:
  - face_landmarker.task         (~7MB)  MediaPipe FaceLandmarker (Tasks API)
  - blaze_face_short_range.tflite (~460KB) MediaPipe Face Detector (Tasks API)
  - face_detection_yunet_2023mar.onnx (~1MB) OpenCV YuNet face detector

Usage:
    python scripts/download_models.py
"""

import sys, os, urllib.request

MODELS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "models")
)
os.makedirs(MODELS_DIR, exist_ok=True)


MODELS = [
    {
        "name": "face_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "desc": "MediaPipe FaceLandmarker (468 landmarks, ~7MB)",
    },
    {
        "name": "blaze_face_short_range.tflite",
        "url": "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
        "desc": "MediaPipe BlazeFace Detector (~460KB)",
    },
    {
        "name": "face_detection_yunet_2023mar.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "desc": "OpenCV YuNet Face Detector (~1MB)",
    },
    {
        "name": "face_recognition_sface_2021dec.onnx",
        "url": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "desc": "OpenCV SFace Recognizer (~13MB)",
    },
]


def download(url: str, dest: str, desc: str):
    if os.path.exists(dest):
        print(f"  [SKIP] {os.path.basename(dest)} already exists.")
        return
    print(f"  [DOWN] {desc}")
    print(f"         -> {os.path.basename(dest)}")
    try:
        urllib.request.urlretrieve(url, dest)
        size_kb = os.path.getsize(dest) // 1024
        print(f"         Done! ({size_kb} KB)")
    except Exception as e:
        print(f"  [FAIL] {e}")


def main():
    print("=" * 55)
    print("   Classroom Attention Monitor — Model Downloader")
    print(f"   Models directory: {MODELS_DIR}")
    print("=" * 55)
    for m in MODELS:
        dest = os.path.join(MODELS_DIR, m["name"])
        download(m["url"], dest, m["desc"])
    print()
    print("All models ready. You can now run:")
    print("   python scripts\\run_vision_debug.py --source webcam")


if __name__ == "__main__":
    main()
