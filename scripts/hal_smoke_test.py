"""
hal_smoke_test.py
=================
Quick sanity check for the Hardware Abstraction Layer.
Run this BEFORE setting up any AI models to verify your webcam and mic work.

Usage:
    python scripts/hal_smoke_test.py                   # webcam + mic
    python scripts/hal_smoke_test.py --source mock     # no hardware needed
"""

import sys
import time
import argparse
import logging

# Add backend to path so imports resolve
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "backend"))

from hal.video_source import WebcamVideoSource, MockVideoSource
from hal.audio_source import MicrophoneAudioSource, MockAudioSource
from hal.manager import VideoSourceManager, AudioSourceManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hal_smoke_test")


def test_video(use_mock: bool, duration_s: float = 5.0):
    """Capture frames for `duration_s` seconds and report statistics."""
    logger.info("=== VIDEO SOURCE TEST ===")
    source = MockVideoSource(total_frames=100) if use_mock else WebcamVideoSource()
    manager = VideoSourceManager(source)

    if not manager.start():
        logger.error("Failed to start VideoSourceManager")
        return False

    frame_count = 0
    start = time.time()
    while time.time() - start < duration_s:
        frame = manager.get_frame(timeout=0.2)
        if frame:
            frame_count += 1
            if frame_count % 10 == 0:
                logger.info(
                    "  Frame #%d  |  ts=%.3f  |  size=%dx%d  |  source=%s",
                    frame.frame_id, frame.timestamp,
                    frame.width, frame.height, frame.source_id,
                )

    manager.stop()
    elapsed = time.time() - start
    logger.info(
        "VIDEO RESULT: Captured %d frames in %.1f s  (%.1f fps)",
        frame_count, elapsed, frame_count / elapsed,
    )
    return frame_count > 0


def test_audio(use_mock: bool, duration_s: float = 5.0):
    """Capture audio chunks for `duration_s` seconds and report statistics."""
    logger.info("=== AUDIO SOURCE TEST ===")
    source = MockAudioSource(total_chunks=200) if use_mock else MicrophoneAudioSource()
    manager = AudioSourceManager(source)

    if not manager.start():
        logger.error("Failed to start AudioSourceManager")
        return False

    chunk_count = 0
    total_samples = 0
    start = time.time()
    while time.time() - start < duration_s:
        chunk = manager.get_chunk(timeout=0.05)
        if chunk:
            chunk_count += 1
            total_samples += len(chunk.samples)
            if chunk_count % 20 == 0:
                rms = float((chunk.samples ** 2).mean() ** 0.5)
                logger.info(
                    "  Chunk #%d  |  ts=%.3f  |  samples=%d  |  RMS=%.5f  |  source=%s",
                    chunk.chunk_id, chunk.timestamp,
                    len(chunk.samples), rms, chunk.source_id,
                )

    manager.stop()
    elapsed = time.time() - start
    logger.info(
        "AUDIO RESULT: Captured %d chunks / %d samples in %.1f s  (%.0f Hz effective)",
        chunk_count, total_samples, elapsed,
        total_samples / elapsed if elapsed > 0 else 0,
    )
    return chunk_count > 0


def main():
    parser = argparse.ArgumentParser(description="HAL Smoke Test")
    parser.add_argument(
        "--source", choices=["webcam", "mock"], default="webcam",
        help="'webcam' uses real hardware; 'mock' requires no hardware (CI-safe)."
    )
    parser.add_argument("--duration", type=float, default=5.0, help="Test duration seconds")
    args = parser.parse_args()

    use_mock = (args.source == "mock")
    mode = "MOCK (no hardware)" if use_mock else "REAL HARDWARE"
    logger.info("Starting HAL smoke test in %s mode for %.0fs...", mode, args.duration)

    video_ok = test_video(use_mock, args.duration)
    audio_ok = test_audio(use_mock, args.duration)

    print()
    print("=" * 42)
    print("        HAL SMOKE TEST RESULTS")
    print("=" * 42)
    print(f"  Video Source : {'PASS' if video_ok else 'FAIL'}")
    print(f"  Audio Source : {'PASS' if audio_ok else 'FAIL'}")
    print("=" * 42)

    sys.exit(0 if (video_ok and audio_ok) else 1)


if __name__ == "__main__":
    main()
