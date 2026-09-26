"""
core/config.py
==============
Central configuration loaded from environment variables (or .env file).
All tunable parameters live here – no magic numbers scattered in code.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """
    Application settings. Override any value by setting the corresponding
    environment variable (prefixed with CLASSMON_).

    Example:
        CLASSMON_VIDEO_SOURCE=rtsp  CLASSMON_RTSP_URL=rtsp://192.168.1.10/live
    """

    # ── App Meta ───────────────────────────────────────────────────────
    app_name: str = "Classroom Attention Monitor"
    debug: bool = False
    log_level: str = "INFO"

    # ── Hardware Abstraction ────────────────────────────────────────────
    video_source: Literal["webcam", "rtsp", "mock"] = "webcam"
    webcam_device_index: int = 0
    webcam_fps: int = 15
    webcam_width: int = 640
    webcam_height: int = 480
    rtsp_url: str = "rtsp://user:pass@camera-ip/live"

    audio_source: Literal["mic", "mock"] = "mic"
    audio_sample_rate: int = 16000
    audio_chunk_ms: float = 100.0

    # ── Vision Pipeline ─────────────────────────────────────────────────
    yolo_model_path: str = "yolov8n-face.pt"        # download on first run
    yolo_confidence: float = 0.5
    mediapipe_min_detection_confidence: float = 0.5
    mediapipe_min_tracking_confidence: float = 0.5

    # Frame scoring weights (Formula 1)
    weight_head_pose: float = 0.30
    weight_eye_gaze: float = 0.50
    weight_posture: float = 0.20

    # EAR threshold for drowsiness
    ear_drowsy_threshold: float = 0.21
    ear_closed_frames_threshold: int = 3     # consecutive frames below EAR before flag

    # Head pose angle thresholds (degrees)
    head_yaw_threshold: float = 30.0         # beyond ±30° = looking away
    head_pitch_threshold: float = 25.0       # beyond ±25° = looking down / up

    # ── Final Score Weights (Formula 3) ────────────────────────────────
    weight_punctuality: float = 0.20
    weight_attention_avg: float = 0.70
    weight_qa: float = 0.10

    # ── Audio / Q&A Pipeline (Phase 4) ──────────────────────────────────
    whisper_model_size: str   = "base"       # tiny | base | small
    whisper_language:   str   = "en"

    vad_energy_threshold:   float = 0.015    # RMS threshold for speech detection
    vad_speech_min_frames:  int   = 3        # consecutive frames to confirm speech
    vad_silence_pad_frames: int   = 8        # silence frames before flushing segment

    qa_response_window_s:        float = 15.0   # seconds student has to respond
    teacher_silence_threshold_s: float = 2.0    # teacher quiet ≥ 2s = student window

    # ── Ollama Local LLM (Phase 4) ────────────────────────────────────────
    ollama_url:     str  = "http://localhost:11434"
    ollama_model:   str  = "phi3.5:mini"
    ollama_enabled: bool = True              # set False to use keyword fallback only
    ollama_timeout_s: int = 15               # max seconds to wait for LLM response

    # ── Intermission / Collective Anomaly ──────────────────────────────
    collective_distraction_threshold: float = 0.85   # ≥85 % of class distracted
    collective_distraction_duration_s: float = 90.0  # for ≥90 consecutive seconds
    intermission_teacher_silence_required: bool = True

    # ── Database ────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./classmon.db"
    # For PostgreSQL+TimescaleDB use:
    # database_url: str = "postgresql+asyncpg://user:pass@localhost/classmon"

    # ── API / WebSocket ─────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    ws_broadcast_interval_ms: int = 500      # push telemetry every 500 ms

    # ── Confidence / Uncertainty ─────────────────────────────────────────
    low_confidence_threshold: float = 0.50   # below → show "requires review" flag

    class Config:
        env_prefix = "CLASSMON_"
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance used across the application
settings = Settings()
