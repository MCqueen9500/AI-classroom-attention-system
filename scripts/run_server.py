"""
scripts/run_server.py
=======================
Launch the ClassMon FastAPI server.

Usage:
  cd classroom-attention-monitor
  .venv\Scripts\activate
  python scripts/run_server.py

Then open:
  REST API docs  → http://localhost:8000/docs
  Health check   → http://localhost:8000/health
  WebSocket      → ws://localhost:8000/ws/{session_id}
"""

import sys
import os

# Add backend to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import uvicorn
from core.config import settings

if __name__ == "__main__":
    print("=" * 60)
    print("  ClassMon API Server")
    print("=" * 60)
    print(f"  REST API : http://{settings.api_host}:{settings.api_port}/docs")
    print(f"  Health   : http://{settings.api_host}:{settings.api_port}/health")
    print(f"  WebSocket: ws://{settings.api_host}:{settings.api_port}/ws/<session_id>")
    print("=" * 60)

    uvicorn.run(
        "api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower(),
        app_dir=os.path.join(os.path.dirname(__file__), "..", "backend"),
    )
