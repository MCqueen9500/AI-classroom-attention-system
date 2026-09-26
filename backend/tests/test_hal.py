"""
tests/test_hal.py
=================
Unit tests for the Hardware Abstraction Layer using Mock sources only.
No real webcam or microphone is required.

Run with:
    pytest tests/test_hal.py -v
"""

import sys
import time
import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from hal.video_source import MockVideoSource
from hal.audio_source import MockAudioSource
from hal.manager import VideoSourceManager, AudioSourceManager
from hal.base import VideoFrame, AudioChunk


# ---------------------------------------------------------------------------
# VideoFrame dataclass
# ---------------------------------------------------------------------------

class TestVideoFrame:
    def test_dimensions_populated(self):
        import numpy as np
        frame = VideoFrame(
            frame_id=1,
            timestamp=time.time(),
            image=np.zeros((480, 640, 3), dtype=np.uint8),
            source_id="test",
        )
        assert frame.width == 640
        assert frame.height == 480


# ---------------------------------------------------------------------------
# AudioChunk dataclass
# ---------------------------------------------------------------------------

class TestAudioChunk:
    def test_duration_ms(self):
        import numpy as np
        samples = np.zeros(1600, dtype=np.float32)
        chunk = AudioChunk(
            chunk_id=1,
            timestamp=time.time(),
            samples=samples,
            sample_rate=16000,
            source_id="test",
        )
        assert abs(chunk.duration_ms - 100.0) < 1e-6


# ---------------------------------------------------------------------------
# MockVideoSource
# ---------------------------------------------------------------------------

class TestMockVideoSource:
    def test_open_close(self):
        src = MockVideoSource(total_frames=10)
        assert src.open() is True
        assert src.is_open() is True
        src.release()
        assert src.is_open() is False

    def test_reads_correct_number_of_frames(self):
        src = MockVideoSource(total_frames=5)
        src.open()
        frames = []
        for _ in range(10):  # try to read more than total
            f = src.read_frame()
            if f is not None:
                frames.append(f)
        src.release()
        assert len(frames) == 5

    def test_frame_ids_monotonic(self):
        src = MockVideoSource(total_frames=20)
        src.open()
        ids = [src.read_frame().frame_id for _ in range(20)]
        src.release()
        assert ids == list(range(1, 21))

    def test_context_manager(self):
        with MockVideoSource(total_frames=3) as src:
            frames = []
            for _ in range(5):
                f = src.read_frame()
                if f:
                    frames.append(f)
        assert len(frames) == 3


# ---------------------------------------------------------------------------
# MockAudioSource
# ---------------------------------------------------------------------------

class TestMockAudioSource:
    def test_open_close(self):
        src = MockAudioSource(total_chunks=10)
        assert src.open() is True
        assert src.is_open() is True
        src.release()
        assert src.is_open() is False

    def test_reads_correct_number_of_chunks(self):
        src = MockAudioSource(total_chunks=5, chunk_duration_ms=100)
        src.open()
        chunks = []
        for _ in range(10):
            c = src.read_chunk()
            if c is not None:
                chunks.append(c)
        src.release()
        assert len(chunks) == 5

    def test_chunk_sample_length(self):
        sr = 16000
        ms = 100
        src = MockAudioSource(sample_rate=sr, chunk_duration_ms=ms, total_chunks=1)
        src.open()
        chunk = src.read_chunk()
        src.release()
        assert len(chunk.samples) == int(sr * ms / 1000)

    def test_sample_rate_property(self):
        src = MockAudioSource(sample_rate=8000)
        assert src.sample_rate == 8000


# ---------------------------------------------------------------------------
# VideoSourceManager
# ---------------------------------------------------------------------------

class TestVideoSourceManager:
    def test_start_stop(self):
        mgr = VideoSourceManager(MockVideoSource(total_frames=50))
        assert mgr.start() is True
        assert mgr.is_running is True
        time.sleep(0.1)
        mgr.stop()
        assert mgr.is_running is False

    def test_get_frame_returns_video_frame(self):
        mgr = VideoSourceManager(MockVideoSource(total_frames=30))
        mgr.start()
        frame = mgr.get_frame(timeout=1.0)
        mgr.stop()
        assert isinstance(frame, VideoFrame)
        assert frame.frame_id >= 1

    def test_source_hotswap(self):
        src1 = MockVideoSource(total_frames=100, source_id="src1")
        src2 = MockVideoSource(total_frames=100, source_id="src2")
        mgr = VideoSourceManager(src1)
        mgr.start()
        f1 = mgr.get_frame(timeout=1.0)
        assert f1.source_id == "src1"
        mgr.set_source(src2)
        time.sleep(0.2)
        f2 = mgr.get_frame(timeout=1.0)
        mgr.stop()
        assert f2.source_id == "src2"


# ---------------------------------------------------------------------------
# AudioSourceManager
# ---------------------------------------------------------------------------

class TestAudioSourceManager:
    def test_start_stop(self):
        mgr = AudioSourceManager(MockAudioSource(total_chunks=100))
        assert mgr.start() is True
        assert mgr.is_running is True
        time.sleep(0.1)
        mgr.stop()
        assert mgr.is_running is False

    def test_get_chunk_returns_audio_chunk(self):
        mgr = AudioSourceManager(MockAudioSource(total_chunks=50))
        mgr.start()
        chunk = mgr.get_chunk(timeout=1.0)
        mgr.stop()
        assert isinstance(chunk, AudioChunk)

    def test_sample_rate_passthrough(self):
        mgr = AudioSourceManager(MockAudioSource(sample_rate=22050))
        assert mgr.sample_rate == 22050
