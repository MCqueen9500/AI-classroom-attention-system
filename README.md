# Classroom Attention Monitor

> An AI-powered classroom attention monitoring system with HAL-abstracted hardware,
> Computer Vision (YOLOv8 + MediaPipe), Audio Q&A detection (Whisper/Vosk), and a
> live React teacher dashboard.

## Project Structure

```
classroom-attention-monitor/
├── backend/
│   ├── hal/                    ← Hardware Abstraction Layer (Phase 1)
│   │   ├── base.py             ← Abstract interfaces (VideoSourceBase, AudioSourceBase)
│   │   ├── video_source.py     ← WebcamVideoSource | RTSPVideoSource | MockVideoSource
│   │   ├── audio_source.py     ← MicrophoneAudioSource | MockAudioSource
│   │   └── manager.py          ← VideoSourceManager, AudioSourceManager (thread-safe queues)
│   ├── core/
│   │   ├── config.py           ← All settings via env vars (pydantic-settings)
│   │   └── logging_config.py   ← Structured logging setup
│   ├── db/                     ← (Phase 2) SQLAlchemy models + Alembic migrations
│   ├── pipelines/
│   │   ├── vision/             ← (Phase 3) YOLOv8 + MediaPipe + frame scoring
│   │   └── audio/              ← (Phase 4) VAD + STT + NLP Q&A detector
│   ├── api/                    ← (Phase 5) FastAPI routes + WebSocket handlers
│   └── tests/
│       └── test_hal.py         ← HAL unit tests (no hardware required)
├── frontend/                   ← (Phase 6) React.js Teacher Dashboard
├── scripts/
│   └── hal_smoke_test.py       ← Quick webcam + mic verification script
├── .env.example                ← Environment variable template
├── pyproject.toml              ← pytest config
└── requirements-phase1.txt     ← Python dependencies
```

## Quick Start

### 1. Set up the virtual environment
```powershell
cd classroom-attention-monitor
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-phase1.txt
```

### 2. Configure environment
```powershell
Copy-Item .env.example .env
# Edit .env if needed (defaults work for laptop/webcam setup)
```

### 3. Test your hardware (Phase 1)
```powershell
# Real webcam + mic:
python scripts/hal_smoke_test.py --source webcam --duration 5

# No hardware (CI-safe mock):
python scripts/hal_smoke_test.py --source mock --duration 5
```

### 4. Run unit tests
```powershell
pytest -v
```

## Phase Build Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project Setup + Hardware Abstraction Layer | ✅ Complete |
| 2 | Database Schema + Migrations | 🔲 Next |
| 3 | Computer Vision Pipeline | 🔲 Pending |
| 4 | Audio Q&A Pipeline | 🔲 Pending |
| 5 | FastAPI Backend + WebSockets | 🔲 Pending |
| 6 | React Teacher Dashboard | 🔲 Pending |

## HAL Mode Switching

Switch between Simulation ↔ Production by changing ONE env variable:

```bash
# Simulation (laptop webcam)
CLASSMON_VIDEO_SOURCE=webcam

# Production (IP camera)
CLASSMON_VIDEO_SOURCE=rtsp
CLASSMON_RTSP_URL=rtsp://user:pass@192.168.1.10/live
```

No AI pipeline, database, or API code changes required.
